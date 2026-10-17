from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..engine import interviewer as svc
from ..engine.llm import LLMClient
from ..engine.report import role_label
from ..models import InterviewQuestion, InterviewSession, User
from ..schemas import AnswerIn, InterviewCreate, QuestionAction
from ..security import current_user

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


def get_llm() -> LLMClient:
    return LLMClient(get_settings())


def owned_session(session_id: int, user: User, db: Session) -> InterviewSession:
    """Session isolation: a session is only ever loaded together with its owner's id.
    Another user's session id yields 404 (not 403) so ids can't be probed."""
    s = db.scalar(select(InterviewSession).where(InterviewSession.id == session_id,
                                                 InterviewSession.user_id == user.id))
    if s is None:
        raise HTTPException(404, "Interview not found")
    return s


def pending_question(s: InterviewSession, question_id: int) -> InterviewQuestion:
    if s.status != "active":
        raise HTTPException(409, "This interview has already ended")
    q = next((q for q in s.questions if q.id == question_id), None)
    if q is None:
        raise HTTPException(404, "Question not found in this interview")
    if q.status != "pending":
        raise HTTPException(409, "This question has already been answered or skipped")
    latest = s.questions[-1]
    if q.id != latest.id:
        raise HTTPException(409, "Only the current question can be answered")
    return q


@router.post("")
def create_interview(body: InterviewCreate, user: User = Depends(current_user), db: Session = Depends(get_db),
                     llm: LLMClient = Depends(get_llm)):
    if body.role == "custom" and not body.custom_role:
        raise HTTPException(422, "Please enter the custom role name")
    # One active interview at a time: close any stale active session first.
    for old in db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id,
                                                         InterviewSession.status == "active")).all():
        svc.finalize(db, old, None, reason="abandoned")
    db.commit()
    s = svc.start_session(db, user, body, llm)
    return svc.session_out(s, llm.s.demo_mode)


@router.get("")
def list_interviews(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id)
                      .order_by(InterviewSession.started_at.desc())).all()
    return [{"id": s.id, "role_label": role_label(s), "interview_type": s.interview_type,
             "difficulty_mode": s.difficulty_mode, "status": s.status, "overall_score": s.overall_score,
             "started_at": svc.as_utc(s.started_at).isoformat(), "questions": len(s.questions),
             "dimensions": (s.report or {}).get("dimensions"), "ai_provider": s.ai_provider} for s in rows]


@router.get("/{session_id}")
def get_interview(session_id: int, user: User = Depends(current_user), db: Session = Depends(get_db),
                  llm: LLMClient = Depends(get_llm)):
    s = owned_session(session_id, user, db)
    svc.maybe_expire(db, s, llm)
    return svc.session_out(s, llm.s.demo_mode)


@router.post("/{session_id}/answer")
def answer(session_id: int, body: AnswerIn, user: User = Depends(current_user), db: Session = Depends(get_db),
           llm: LLMClient = Depends(get_llm)):
    s = owned_session(session_id, user, db)
    q = pending_question(s, body.question_id)
    text = body.answer.strip()
    if not text:
        raise HTTPException(422, "Answer cannot be empty")
    out = svc.submit_answer(db, s, q, text, body.response_seconds, body.input_mode, llm)
    return {**out, "next_question": svc.question_out(out["next_question"], s), "session": svc.session_out(s, llm.s.demo_mode)}


@router.post("/{session_id}/skip")
def skip(session_id: int, body: QuestionAction, user: User = Depends(current_user), db: Session = Depends(get_db),
         llm: LLMClient = Depends(get_llm)):
    s = owned_session(session_id, user, db)
    q = pending_question(s, body.question_id)
    out = svc.skip_question(db, s, q, llm)
    return {**out, "next_question": svc.question_out(out["next_question"], s), "session": svc.session_out(s, llm.s.demo_mode)}


@router.post("/{session_id}/hint")
def hint(session_id: int, body: QuestionAction, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = owned_session(session_id, user, db)
    q = pending_question(s, body.question_id)
    if q.hints_used >= 2:
        raise HTTPException(409, "You've used both hints for this question")
    return svc.give_hint(db, s, q)


@router.post("/{session_id}/repeat")
def repeat(session_id: int, body: QuestionAction, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = owned_session(session_id, user, db)
    q = pending_question(s, body.question_id)
    return svc.repeat_question(db, s, q)


@router.post("/{session_id}/end")
def end(session_id: int, user: User = Depends(current_user), db: Session = Depends(get_db),
        llm: LLMClient = Depends(get_llm)):
    s = owned_session(session_id, user, db)
    if s.status == "active":
        svc.finalize(db, s, llm, reason="ended_by_candidate")
        db.commit()
    return {"report": s.report, "session": svc.session_out(s, llm.s.demo_mode)}


@router.get("/{session_id}/report")
def report(session_id: int, user: User = Depends(current_user), db: Session = Depends(get_db),
           llm: LLMClient = Depends(get_llm)):
    s = owned_session(session_id, user, db)
    svc.maybe_expire(db, s, llm)
    if s.status == "active":
        raise HTTPException(409, "The interview is still in progress")
    return {"report": s.report, "session": svc.session_out(s, llm.s.demo_mode)}
