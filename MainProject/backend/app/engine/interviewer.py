"""Interview orchestration: connects the adaptive policy, evaluators, question composition, the
LLM and the database. All functions receive an already-authorised session object; ownership checks
happen in the router."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (AnswerEvaluation, CandidateAnswer, InterviewEvent, InterviewQuestion, InterviewSession,
                      LearningRecommendation, TopicMastery, User)
from ..schemas import InterviewCreate
from . import demo_evaluator
from .composer import ack_for, compose
from .llm import LLMClient, LLMError
from .mastery import update_mastery
from .policy import LEVEL_LABEL, AskedQ, Ctx, Decision, current_thread, decide_next, initial_level
from .question_bank import T, get_bank_question, topic_name, topics_for
from .report import build_report, role_label
from .scoring import Evaluation
from .text_utils import extract_skills, topics_for_skills

log = logging.getLogger("interviewer")
settings = get_settings()


def now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def ends_at(s: InterviewSession) -> datetime:
    return as_utc(s.started_at) + timedelta(minutes=s.duration_minutes)


def remaining_seconds(s: InterviewSession) -> float:
    return max(0.0, (ends_at(s) - now()).total_seconds())


def _state(s: InterviewSession) -> dict:
    return dict(s.engine_state or {})


def _set_state(s: InterviewSession, **kw) -> None:
    st = _state(s)
    st.update(kw)
    s.engine_state = st  # reassign so SQLAlchemy notices the JSON change


def mastery_map(db: Session, user_id: int) -> tuple[dict[str, float], dict[str, int]]:
    rows = db.scalars(select(TopicMastery).where(TopicMastery.user_id == user_id)).all()
    return {r.topic: r.mastery for r in rows}, {r.topic: r.attempts for r in rows}


def history_texts(db: Session, user_id: int, exclude_session: int | None = None, limit: int = 300) -> list[str]:
    stmt = (select(InterviewQuestion.text).join(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .order_by(InterviewQuestion.id.desc()).limit(limit))
    if exclude_session:
        stmt = stmt.where(InterviewSession.id != exclude_session)
    return list(db.scalars(stmt).all())


def asked_list(s: InterviewSession) -> list[AskedQ]:
    out = []
    for q in s.questions:
        ev = q.answer.evaluation if q.answer and q.answer.evaluation else None
        out.append(AskedQ(topic=q.topic, level=q.level, kind=q.kind, text=q.text, bank_id=q.bank_id,
                          score=ev.score if ev else None, correctness=ev.correctness if ev else None,
                          verdict=ev.verdict if ev else None, skipped=q.status == "skipped",
                          hints_used=q.hints_used, missing_concepts=list(ev.missing_concepts or []) if ev else []))
    return out


def build_ctx(db: Session, s: InterviewSession) -> Ctx:
    st = _state(s)
    mastery, attempts = mastery_map(db, s.user_id)
    return Ctx(topics=st.get("topics", []), interview_type=s.interview_type, difficulty_mode=s.difficulty_mode,
               current_level=s.current_level, asked=asked_list(s), history_texts=st.get("history_texts", []),
               mastery=mastery, attempts=attempts, focus_topics=st.get("focus_topics", []),
               skill_topics=st.get("skill_topics", []), remaining_seconds=remaining_seconds(s),
               remaining_questions=s.max_questions - len(s.questions),
               max_followups=settings.max_followups_per_topic, seed=s.id)


def thread_for_llm(s: InterviewSession) -> list[dict]:
    if not s.questions:
        return []
    topic = s.questions[-1].topic
    out = []
    for q in reversed(s.questions):
        if q.topic != topic:
            break
        out.append({"q": q.text, "a": q.answer.text if q.answer else "(skipped)" if q.status == "skipped" else ""})
    return list(reversed(out))


# --------------------------------------------------------------------------- lifecycle
def start_session(db: Session, user: User, cfg: InterviewCreate, llm: LLMClient) -> InterviewSession:
    profile = user.profile
    resume = cfg.resume_text or (profile.resume_text if (profile and cfg.use_profile_resume) else "")
    topics = topics_for(cfg.role, cfg.interview_type, cfg.custom_role)
    mastery, attempts = mastery_map(db, user.id)
    struggles = {r.topic: r.struggle_count for r in db.scalars(select(TopicMastery).where(TopicMastery.user_id == user.id))}
    focus = sorted([t for t in topics if attempts.get(t, 0) > 0 and (mastery.get(t, 1) < 0.5 or struggles.get(t, 0) >= 2)],
                   key=lambda t: mastery.get(t, 0.5))[:3]
    resume_skills = extract_skills(resume)
    jd_skills = extract_skills(cfg.job_description)
    skill_topics = topics_for_skills(jd_skills + resume_skills, topics)
    level = initial_level(cfg.difficulty, mastery, attempts, topics)
    hist = history_texts(db, user.id)

    s = InterviewSession(
        user_id=user.id, role=cfg.role, custom_role=cfg.custom_role, interview_type=cfg.interview_type,
        difficulty_mode=cfg.difficulty, current_level=level, duration_minutes=cfg.duration_minutes,
        max_questions=min(cfg.num_questions, settings.max_questions_hard_cap), language=cfg.language, mode=cfg.mode,
        resume_text=resume[:20000], job_description=cfg.job_description[:20000], jd_skills=jd_skills,
        ai_provider=llm.label,
        engine_state={"topics": topics, "focus_topics": focus, "skill_topics": skill_topics,
                      "resume_skills": resume_skills, "used_templates": [], "history_texts": hist,
                      "mastery_before": {t: mastery[t] for t in topics if t in mastery},
                      "start_level": level, "decisions": []},
    )
    db.add(s)
    db.flush()
    ctx = build_ctx(db, s)
    decision = decide_next(ctx)
    create_question(db, s, decision, llm, parent=None)
    db.commit()
    db.refresh(s)
    return s


def create_question(db: Session, s: InterviewSession, decision: Decision, llm: LLMClient,
                    parent: InterviewQuestion | None) -> InterviewQuestion:
    st = _state(s)
    session_ids = {q.bank_id for q in s.questions if q.bank_id}
    session_texts = [q.text for q in s.questions]
    hist = st.get("history_texts", [])
    composed = compose(decision, parent=({"text": parent.text, "bank_id": parent.bank_id, "key_concepts": parent.key_concepts,
                                          "topic": parent.topic, "kind": parent.kind, "level": parent.level} if parent else None),
                       session_ids=session_ids, session_texts=session_texts, history_texts=hist,
                       used_templates=st.get("used_templates", []), resume_skills=st.get("resume_skills", []))
    text, concepts, hint, bank_id, source = composed.text, composed.concepts, composed.hint, composed.bank_id, "bank"
    if composed.template_id:
        source = "template"
    ack = ack_for(decision.action, s.language, len(s.questions)) if s.questions else ""

    if llm.enabled:
        try:
            gen = llm.generate_question(
                decision=decision, role=role_label(s), interview_type=s.interview_type, language=s.language,
                thread=thread_for_llm(s) if decision.action != "new_topic" else [],
                avoid=session_texts + hist[:40], resume=s.resume_text, jd=s.job_description,
                remaining_minutes=remaining_seconds(s) / 60, example=composed.text)
            text, hint, ack, source = gen["text"], gen["hint"] or hint, gen["ack"] or ack, "llm"
            concepts = [{"label": c} for c in gen["concepts"]]
            bank_id = None
        except LLMError as e:
            log.warning("question generation fell back to bank: %s", e)
            source = "fallback"

    q = InterviewQuestion(session_id=s.id, seq=len(s.questions) + 1, topic=decision.topic, level=decision.level,
                          kind=decision.kind, text=text, bank_id=bank_id, parent_question_id=parent.id if parent else None,
                          key_concepts=concepts, hint=hint, rationale=decision.reason)
    s.questions.append(q)
    db.add(q)
    used = st.get("used_templates", []) + ([composed.template_id] if composed.template_id and source != "llm" else [])
    decisions = st.get("decisions", []) + [{"seq": q.seq, "action": decision.action, "reason": decision.reason,
                                            "level": decision.level, "topic": decision.topic, "source": source, "ack": ack}]
    _set_state(s, used_templates=used, decisions=decisions)
    s.current_level = decision.new_current_level
    db.flush()
    return q


def _evaluate(s: InterviewSession, q: InterviewQuestion, answer: str, llm: LLMClient) -> Evaluation:
    concepts = demo_evaluator.concepts_from_json(q.key_concepts)
    if llm.enabled:
        try:
            return llm.evaluate(role=role_label(s), question=q.text, answer=answer,
                                rubric=[c.label for c in concepts], level=q.level, kind=q.kind,
                                language=s.language, hints_used=q.hints_used, thread=thread_for_llm(s)[:-1])
        except LLMError as e:
            log.warning("evaluation fell back to heuristic: %s", e)
            ev = demo_evaluator.evaluate(q.text, concepts, answer, q.kind)
            return ev.model_copy(update={"evaluator": "fallback-heuristic"})
    return demo_evaluator.evaluate(q.text, concepts, answer, q.kind)


def _update_memory(db: Session, user_id: int, q: InterviewQuestion, ev: Evaluation | None, skipped: bool) -> float:
    row = db.scalar(select(TopicMastery).where(TopicMastery.user_id == user_id, TopicMastery.topic == q.topic))
    if row is None:
        row = TopicMastery(user_id=user_id, topic=q.topic, mastery=0.5, attempts=0, correct_count=0, struggle_count=0)
        db.add(row)
    row.mastery = update_mastery(row.mastery if row.attempts else None,
                                 correctness=ev.correctness if ev else 0, depth=ev.depth if ev else 0,
                                 confidence=ev.confidence if ev else 0.5, level=q.level,
                                 hints_used=q.hints_used, skipped=skipped)
    row.attempts += 1
    if ev and ev.verdict == "correct":
        row.correct_count += 1
    if skipped or (ev and ev.verdict in ("incorrect", "off_topic")):
        row.struggle_count += 1
    row.last_level = q.level
    row.last_seen_at = now()
    db.flush()
    return row.mastery


def _advance(db: Session, s: InterviewSession, q: InterviewQuestion, llm: LLMClient) -> InterviewQuestion | None:
    ctx = build_ctx(db, s)
    decision = decide_next(ctx)
    if decision.action == "finish":
        finalize(db, s, llm, reason="time" if "time" in decision.reason.lower() else "question_limit")
        return None
    return create_question(db, s, decision, llm, parent=q)


def _check_time(db: Session, s: InterviewSession, llm: LLMClient) -> bool:
    """Returns False (and closes the session) if the hard time limit has passed."""
    if now() > ends_at(s) + timedelta(seconds=settings.grace_seconds):
        finalize(db, s, llm, reason="time")
        db.commit()
        return False
    return True


def submit_answer(db: Session, s: InterviewSession, q: InterviewQuestion, text: str, seconds: float,
                  input_mode: str, llm: LLMClient) -> dict:
    if not _check_time(db, s, llm):
        return {"finished": True, "reason": "time", "evaluation": None, "next_question": None}
    ev = _evaluate(s, q, text, llm)
    ans = CandidateAnswer(question_id=q.id, user_id=s.user_id, text=text, input_mode=input_mode, response_seconds=seconds)
    q.answer = ans
    q.status = "answered"
    db.add(ans)
    db.flush()
    m = _update_memory(db, s.user_id, q, ev, skipped=False)
    row = AnswerEvaluation(answer_id=ans.id, mastery_estimate=m, **ev.model_dump(exclude={"evaluator"}), evaluator=ev.evaluator)
    ans.evaluation = row
    db.add(row)
    db.flush()
    nxt = _advance(db, s, q, llm)
    db.commit()
    return {"finished": nxt is None, "reason": None if nxt else (s.engine_state or {}).get("end_reason"),
            "evaluation": evaluation_out(row, q, held_back=is_probing(s, q)), "next_question": nxt}


def skip_question(db: Session, s: InterviewSession, q: InterviewQuestion, llm: LLMClient) -> dict:
    if not _check_time(db, s, llm):
        return {"finished": True, "reason": "time", "next_question": None}
    q.status = "skipped"
    db.add(InterviewEvent(session_id=s.id, question_id=q.id, kind="skip"))
    _update_memory(db, s.user_id, q, None, skipped=True)
    db.flush()
    nxt = _advance(db, s, q, llm)
    db.commit()
    return {"finished": nxt is None, "reason": None if nxt else (s.engine_state or {}).get("end_reason"), "next_question": nxt}


def give_hint(db: Session, s: InterviewSession, q: InterviewQuestion) -> dict:
    q.hints_used += 1
    db.add(InterviewEvent(session_id=s.id, question_id=q.id, kind="hint", detail=str(q.hints_used)))
    concepts = demo_evaluator.concepts_from_json(q.key_concepts)
    if q.hints_used == 1:
        hint = q.hint or "Start from a simple definition, then explain how it works and give one example."
    else:
        first = concepts[0].label if concepts else "the core idea"
        hint = f"One area a strong answer touches on: {first}. Explain it in your own words."
    db.commit()
    return {"hint": hint, "hints_used": q.hints_used,
            "note": "Hints are recorded and slightly reduce how much this answer counts toward topic mastery."}


def repeat_question(db: Session, s: InterviewSession, q: InterviewQuestion) -> dict:
    q.repeats += 1
    db.add(InterviewEvent(session_id=s.id, question_id=q.id, kind="repeat"))
    db.commit()
    return {"text": q.text, "repeats": q.repeats}


def finalize(db: Session, s: InterviewSession, llm: LLMClient | None, reason: str = "completed") -> dict:
    if s.status != "active" and s.report:
        return s.report
    s.status = "completed"
    s.ended_at = now()
    _set_state(s, end_reason=reason)
    db.add(InterviewEvent(session_id=s.id, kind="end", detail=reason))
    # Drop an unanswered trailing question from scoring (it stays in the transcript as 'pending').
    db.flush()
    mastery, _ = mastery_map(db, s.user_id)
    previous = db.scalars(select(InterviewSession).where(
        InterviewSession.user_id == s.user_id, InterviewSession.id != s.id,
        InterviewSession.status == "completed").order_by(InterviewSession.started_at)).all()
    report = build_report(s, list(previous), mastery, llm)
    s.report = report
    s.overall_score = report["overall_score"]

    # Persist learning recommendations: replace open ones for the same topics, keep history of done ones.
    topics = [r["topic"] for r in report["roadmap"]]
    if topics:
        for old in db.scalars(select(LearningRecommendation).where(
                LearningRecommendation.user_id == s.user_id, LearningRecommendation.status == "open",
                LearningRecommendation.topic.in_(topics))).all():
            db.delete(old)
    extra = report.get("extra_practice", [])
    for r in report["roadmap"]:
        practice = list(r["practice_questions"]) + [p["question"] for p in extra
                                                   if p["topic"].lower() in r["name"].lower() or r["name"].lower() in p["topic"].lower()]
        db.add(LearningRecommendation(user_id=s.user_id, session_id=s.id, topic=r["topic"], priority=r["priority"],
                                      reason=r["reason"], actions=r["actions"], practice_questions=practice[:5]))
    db.flush()
    return report


def maybe_expire(db: Session, s: InterviewSession, llm: LLMClient) -> None:
    if s.status == "active" and now() > ends_at(s) + timedelta(seconds=settings.grace_seconds):
        finalize(db, s, llm, reason="time")
        db.commit()


# --------------------------------------------------------------------------- serialisation
def question_out(q: InterviewQuestion | None, s: InterviewSession) -> dict | None:
    """Public view of a question: never includes the rubric or hint before it's answered."""
    if q is None:
        return None
    dec = next((d for d in (s.engine_state or {}).get("decisions", []) if d.get("seq") == q.seq), {})
    return {"id": q.id, "seq": q.seq, "text": q.text, "topic": q.topic, "topic_name": topic_name(q.topic),
            "kind": q.kind, "level": q.level, "level_label": LEVEL_LABEL[q.level], "hints_used": q.hints_used,
            "status": q.status, "acknowledgement": dec.get("ack", ""), "why": q.rationale,
            "source": dec.get("source", "bank")}


HELD_BACK = "I'm probing this with a follow-up first; the full breakdown appears once you've answered it."


def is_probing(s: InterviewSession, q: InterviewQuestion) -> bool:
    """True while the interviewer is still following up on this question's gaps. Revealing
    exactly what was missing at that point would hand the candidate the answer."""
    if s.status != "active":
        return False
    later = [x for x in s.questions if x.seq > q.seq]
    return bool(later) and all(x.topic == q.topic for x in later) and later[-1].status == "pending" \
        and later[-1].kind in ("followup", "diagnostic")


def evaluation_out(e: AnswerEvaluation, q: InterviewQuestion, held_back: bool = False) -> dict:
    return {"question_id": q.id, "score": e.score, "verdict": e.verdict, "correctness": e.correctness,
            "relevance": e.relevance, "depth": e.depth, "clarity": e.clarity, "confidence": e.confidence,
            "mastery_estimate": e.mastery_estimate, "did_well": e.did_well,
            "missing": HELD_BACK if held_back else e.missing,
            "improvement": "" if held_back else e.improvement,
            "missing_concepts": [] if held_back else e.missing_concepts, "held_back": held_back,
            "evaluator": e.evaluator, "topic_name": topic_name(q.topic)}


def session_out(s: InterviewSession, demo_mode: bool) -> dict:
    current = next((q for q in reversed(s.questions) if q.status == "pending"), None) if s.status == "active" else None
    transcript = []
    for q in s.questions:
        item = {"question": question_out(q, s), "answer": None, "evaluation": None}
        if q.answer:
            item["answer"] = {"text": q.answer.text, "input_mode": q.answer.input_mode, "response_seconds": q.answer.response_seconds}
            if q.answer.evaluation:
                item["evaluation"] = evaluation_out(q.answer.evaluation, q, held_back=is_probing(s, q))
        if q.status != "pending" and s.status != "active":
            item["question"]["strong_answer_covers"] = [c.get("label") if isinstance(c, dict) else str(c) for c in (q.key_concepts or [])]
        transcript.append(item)
    st = s.engine_state or {}
    return {
        "id": s.id, "role": s.role, "role_label": role_label(s), "interview_type": s.interview_type,
        "difficulty_mode": s.difficulty_mode, "current_level": s.current_level, "level_label": LEVEL_LABEL[s.current_level],
        "duration_minutes": s.duration_minutes, "max_questions": s.max_questions, "language": s.language, "mode": s.mode,
        "status": s.status, "ai_provider": s.ai_provider, "demo_mode": demo_mode,
        "started_at": as_utc(s.started_at).isoformat(), "ends_at": ends_at(s).isoformat(),
        "remaining_seconds": int(remaining_seconds(s)) if s.status == "active" else 0,
        "question_number": len(s.questions), "answered_count": sum(1 for q in s.questions if q.status == "answered"),
        "current_question": question_out(current, s), "transcript": transcript,
        "focus_topics": [topic_name(t) for t in st.get("focus_topics", [])],
        "skill_topics": [topic_name(t) for t in st.get("skill_topics", [])],
        "resume_skills": st.get("resume_skills", []), "overall_score": s.overall_score,
        "end_reason": st.get("end_reason"),
    }
