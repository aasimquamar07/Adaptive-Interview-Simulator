"""End-of-interview report.

The report separates two kinds of numbers:
  * objective measurements: counted directly (questions, skips, hints, timings, words), and
  * AI estimates: scores and mastery produced by the evaluator (LLM or heuristic), which can be wrong.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from statistics import mean

from .mastery import mastery_label
from .policy import LEVEL_LABEL, category, pick_bank_question
from .question_bank import ROLE_LABELS, T, topic_name

log = logging.getLogger("report")

DISCLAIMER = ("Scores, dimension ratings and mastery levels are AI-generated estimates from a practice session. "
              "They can be wrong and are not a prediction or guarantee of the outcome of any real interview.")


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(mean(xs), 1) if xs else None


def role_label(session) -> str:
    if session.role == "custom" and session.custom_role:
        return session.custom_role
    return ROLE_LABELS.get(session.role, session.role)


def build_report(session, previous: list, mastery_now: dict[str, float], llm=None) -> dict:
    rows = []
    for q in session.questions:
        ev = q.answer.evaluation if q.answer and q.answer.evaluation else None
        if q.status == "pending" and not ev:
            continue
        rows.append({"q": q, "ev": ev, "skipped": q.status == "skipped", "cat": category(q.topic)})

    answered = [r for r in rows if r["ev"]]
    skipped = [r for r in rows if r["skipped"]]
    events = session.events
    duration = None
    if session.ended_at and session.started_at:
        a, b = session.started_at, session.ended_at
        if a.tzinfo is None or b.tzinfo is None:
            a, b = a.replace(tzinfo=None), b.replace(tzinfo=None)
        duration = int((b - a).total_seconds())

    objective = {
        "questions_asked": len(rows),
        "answered": len(answered),
        "skipped": len(skipped),
        "hints_used": sum(r["q"].hints_used for r in rows),
        "repeats_requested": sum(1 for e in events if e.kind == "repeat"),
        "duration_seconds": duration,
        "avg_response_seconds": _avg([r["q"].answer.response_seconds for r in answered if r["q"].answer.response_seconds]),
        "avg_answer_words": _avg([len(r["q"].answer.text.split()) for r in answered]),
        "topics_covered": len({r["q"].topic for r in rows}),
        "follow_ups_asked": sum(1 for r in rows if r["q"].kind in ("followup", "diagnostic", "scenario")),
    }

    scores = [r["ev"].score for r in answered] + [0.0 for _ in skipped]
    overall = _avg(scores)
    tech = [0.6 * r["ev"].correctness + 0.4 * r["ev"].depth for r in answered if r["cat"] in ("technical", "coding")]
    ps_rows = [r for r in answered if r["q"].kind in ("scenario", "coding", "followup", "diagnostic") or r["cat"] in ("coding", "project")]
    problem = [0.5 * r["ev"].correctness + 0.5 * r["ev"].depth for r in (ps_rows or answered)]
    comm = [r["ev"].clarity for r in answered]
    behav = [r["ev"].score for r in answered if r["cat"] == "hr"]
    dimensions = {
        "technical_knowledge": _avg(tech),
        "problem_solving": _avg(problem),
        "communication": _avg(comm),
    }
    if behav:
        dimensions["behavioral"] = _avg(behav)

    before = (session.engine_state or {}).get("mastery_before", {})
    by_topic = defaultdict(list)
    for r in rows:
        by_topic[r["q"].topic].append(r)
    topics = []
    for t, rs in by_topic.items():
        avg = _avg([r["ev"].score if r["ev"] else 0.0 for r in rs])
        missed = []
        for r in rs:
            if r["ev"]:
                missed += [m for m in (r["ev"].missing_concepts or []) if m not in missed]
        topics.append({
            "topic": t, "name": topic_name(t), "category": category(t), "avg_score": avg, "questions": len(rs),
            "skipped": sum(1 for r in rs if r["skipped"]),
            "mastery_before": before.get(t), "mastery_after": mastery_now.get(t),
            "status": mastery_label(mastery_now.get(t)), "missed_concepts": missed[:5],
        })
    topics.sort(key=lambda x: (x["avg_score"] if x["avg_score"] is not None else 0))

    strengths = [f"{x['name']}: averaged {x['avg_score']}/10" for x in topics if (x["avg_score"] or 0) >= 7.5][::-1]
    weaknesses = [f"{x['name']}: averaged {x['avg_score']}/10" + (f"; missed {', '.join(x['missed_concepts'][:2])}" if x["missed_concepts"] else "")
                  for x in topics if (x["avg_score"] or 0) < 5.5 or x["skipped"]]

    needs_review = []
    for r in rows:
        ev = r["ev"]
        if r["skipped"] or (ev and ev.verdict in ("partial", "incorrect", "off_topic")):
            q = r["q"]
            needs_review.append({
                "seq": q.seq, "question": q.text, "topic": topic_name(q.topic),
                "answer": (q.answer.text[:500] if q.answer else ""), "score": ev.score if ev else 0,
                "verdict": ev.verdict if ev else "skipped", "missing": ev.missing if ev else "Skipped.",
                "improvement": ev.improvement if ev else "Revisit this topic and attempt a structured answer.",
                "strong_answer_covers": [c.get("label") if isinstance(c, dict) else str(c) for c in (q.key_concepts or [])],
            })

    asked_ids = {q.bank_id for q in session.questions if q.bank_id}
    asked_texts = [q.text for q in session.questions]
    roadmap = []
    for x in topics:
        m_after = x["mastery_after"]
        weak = (x["avg_score"] or 0) < 6.5 or x["skipped"] or (m_after is not None and m_after < 0.5)
        if not weak:
            continue
        priority = 1 if ((x["avg_score"] or 0) < 4 or x["skipped"]) else 2
        practice = []
        for lvl in (1, 2, 3):
            bq = pick_bank_question(x["topic"], lvl, asked_ids | {p for p in practice}, asked_texts, [])
            if bq and bq.text not in practice:
                practice.append(bq.text)
            if len(practice) >= 2:
                break
        reason = f"Averaged {x['avg_score']}/10 over {x['questions']} question(s)"
        if x["missed_concepts"]:
            reason += "; gaps: " + ", ".join(x["missed_concepts"][:3])
        roadmap.append({
            "topic": x["topic"], "name": x["name"], "priority": priority, "reason": reason + ".",
            "actions": list(T[x["topic"]].actions) if x["topic"] in T else [],
            "practice_questions": practice,
        })
    if not roadmap and topics:
        stretch = max(1, min(3, session.current_level + (1 if session.current_level < 3 else 0)))
        roadmap.append({
            "topic": "next_level", "name": "Raise the difficulty", "priority": 3,
            "reason": "No weak topics this session. Keep momentum with harder material.",
            "actions": [f"Run your next session at {LEVEL_LABEL[stretch]} or Adaptive difficulty.",
                        "Add a job description so questions target a specific role.",
                        "Practise explaining your strongest topics in under two minutes."],
            "practice_questions": [],
        })
    roadmap.sort(key=lambda r: r["priority"])

    # Comparison with the candidate's OWN previous sessions only.
    prev = [p for p in previous if p.overall_score is not None]
    same_role = [p for p in prev if p.role == session.role]
    basis = same_role or prev
    last = basis[-1] if basis else None
    comparison = {
        "sessions_compared": len(basis),
        "basis": "same role" if same_role else ("all roles" if prev else "none"),
        "previous_average": _avg([p.overall_score for p in basis]),
        "last_score": last.overall_score if last else None,
        "delta_vs_last": round(overall - last.overall_score, 1) if (last and overall is not None) else None,
        "delta_vs_average": round(overall - _avg([p.overall_score for p in basis]), 1) if (basis and overall is not None) else None,
        "dimension_deltas": {},
        "trend": [{"session_id": p.id, "date": p.started_at.isoformat() if p.started_at else None,
                   "score": p.overall_score, "role": role_label(p)} for p in basis[-9:]]
        + [{"session_id": session.id, "date": session.started_at.isoformat() if session.started_at else None,
            "score": overall, "role": role_label(session), "current": True}],
    }
    if last and last.report:
        for k, v in dimensions.items():
            pv = (last.report.get("dimensions") or {}).get(k)
            if v is not None and pv is not None:
                comparison["dimension_deltas"][k] = round(v - pv, 1)

    if overall is None:
        summary = "No answers were submitted in this session, so there is nothing to score yet."
    else:
        best = strengths[0].split(":")[0] if strengths else None
        worst = weaknesses[0].split(":")[0] if weaknesses else None
        summary = f"You answered {len(answered)} of {len(rows)} questions with an estimated overall score of {overall}/10."
        if best:
            summary += f" Your strongest area was {best}."
        if worst:
            summary += f" The biggest opportunity is {worst}, which has been added to your learning roadmap."
        if comparison["delta_vs_last"] is not None:
            d = comparison["delta_vs_last"]
            summary += f" That is {abs(d)} points {'higher' if d >= 0 else 'lower'} than your previous comparable session."

    evaluators = sorted({r["ev"].evaluator for r in answered})
    report = {
        "session_id": session.id, "role": role_label(session), "interview_type": session.interview_type,
        "overall_score": overall, "dimensions": dimensions, "objective": objective, "topics": topics,
        "strengths": strengths, "weaknesses": weaknesses, "needs_review": needs_review, "roadmap": roadmap,
        "comparison": comparison, "summary": summary, "summary_source": "computed", "disclaimer": DISCLAIMER,
        "evaluators": evaluators, "ended_reason": (session.engine_state or {}).get("end_reason", "completed"),
        "extra_practice": [],
    }

    if llm is not None and llm.enabled and answered:
        digest = "\n".join(
            f"- [{topic_name(r['q'].topic)} | {r['q'].kind} | {LEVEL_LABEL.get(r['q'].level)}] Q: {r['q'].text[:200]} | "
            f"score {r['ev'].score if r['ev'] else 'skipped'} | missed: {', '.join((r['ev'].missing_concepts if r['ev'] else [])[:3])}"
            for r in rows)
        try:
            extra = llm.report_narrative(role=role_label(session), language=session.language, digest=digest)
            report["summary"] = str(extra["summary"])[:1200]
            report["summary_source"] = "ai"
            report["ai_strengths"] = [str(s)[:200] for s in extra.get("strengths", [])][:4]
            report["ai_weaknesses"] = [str(s)[:200] for s in extra.get("weaknesses", [])][:4]
            report["extra_practice"] = [{"topic": str(p.get("topic", ""))[:80], "question": str(p.get("question", ""))[:400]}
                                        for p in extra.get("practice_questions", []) if isinstance(p, dict)][:6]
        except Exception as e:  # report still complete without the narrative
            log.warning("report narrative failed: %s", e)
    return report
