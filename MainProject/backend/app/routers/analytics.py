from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..engine.interviewer import as_utc
from ..engine.mastery import mastery_label
from ..engine.policy import category
from ..engine.question_bank import ROLE_LABELS, topic_name
from ..engine.report import role_label
from ..models import InterviewSession, LearningRecommendation, TopicMastery, User
from ..schemas import RecommendationUpdate
from ..security import current_user

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/meta")
def meta():
    s = get_settings()
    return {
        "demo_mode": s.demo_mode,
        "provider": "demo" if s.demo_mode else s.llm_provider,
        "model": None if s.demo_mode else (s.anthropic_model if s.llm_provider == "anthropic" else s.openai_model),
        "roles": [{"value": k, "label": v} for k, v in ROLE_LABELS.items()],
        "interview_types": [{"value": "technical", "label": "Technical"}, {"value": "hr", "label": "HR / Behavioural"},
                            {"value": "project", "label": "Project-based"}, {"value": "coding", "label": "Coding"},
                            {"value": "mixed", "label": "Mixed"}],
        "difficulties": [{"value": "beginner", "label": "Beginner"}, {"value": "intermediate", "label": "Intermediate"},
                         {"value": "advanced", "label": "Advanced"}, {"value": "adaptive", "label": "Adaptive"}],
        "durations": [10, 20, 30, 45],
        "languages": [{"value": "en", "label": "English"}, {"value": "hi", "label": "हिन्दी (Hindi)"}],
    }


def mastery_rows(db: Session, user_id: int) -> list[dict]:
    rows = db.scalars(select(TopicMastery).where(TopicMastery.user_id == user_id).order_by(TopicMastery.mastery)).all()
    return [{"topic": r.topic, "name": topic_name(r.topic), "category": category(r.topic), "mastery": r.mastery,
             "label": mastery_label(r.mastery), "attempts": r.attempts, "correct": r.correct_count,
             "struggles": r.struggle_count, "last_seen_at": as_utc(r.last_seen_at).isoformat()} for r in rows]


@router.get("/analytics/overview")
def overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    sessions = db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id)
                          .order_by(InterviewSession.started_at)).all()
    done = [s for s in sessions if s.status == "completed" and s.overall_score is not None]
    trend = [{"session_id": s.id, "date": as_utc(s.started_at).isoformat(), "score": s.overall_score,
              "role": role_label(s), **{k: v for k, v in ((s.report or {}).get("dimensions") or {}).items()}} for s in done]
    mastery = mastery_rows(db, user.id)
    active = next((s for s in reversed(sessions) if s.status == "active"), None)
    recs = db.scalars(select(LearningRecommendation).where(LearningRecommendation.user_id == user.id,
                                                           LearningRecommendation.status == "open")
                      .order_by(LearningRecommendation.priority, LearningRecommendation.created_at.desc()).limit(3)).all()
    last5 = [s.overall_score for s in done[-5:]]
    prev5 = [s.overall_score for s in done[-10:-5]]
    return {
        "total_sessions": len(done),
        "average_score": round(sum(s.overall_score for s in done) / len(done), 1) if done else None,
        "best_score": max((s.overall_score for s in done), default=None),
        "recent_average": round(sum(last5) / len(last5), 1) if last5 else None,
        "previous_average": round(sum(prev5) / len(prev5), 1) if prev5 else None,
        "questions_answered": sum(sum(1 for q in s.questions if q.status == "answered") for s in sessions),
        "trend": trend,
        "mastery": mastery,
        "weak_topics": [m for m in mastery if m["mastery"] < 0.5][:5],
        "strong_topics": [m for m in reversed(mastery) if m["mastery"] >= 0.75][:5],
        "active_session_id": active.id if active else None,
        "top_recommendations": [rec_out(r) for r in recs],
        "recent_sessions": [{"id": s.id, "role_label": role_label(s), "interview_type": s.interview_type,
                             "overall_score": s.overall_score, "status": s.status,
                             "started_at": as_utc(s.started_at).isoformat()} for s in reversed(sessions[-5:])],
    }


def rec_out(r: LearningRecommendation) -> dict:
    return {"id": r.id, "topic": r.topic, "name": topic_name(r.topic) if r.topic != "next_level" else "Raise the difficulty",
            "priority": r.priority, "reason": r.reason, "actions": r.actions, "practice_questions": r.practice_questions,
            "status": r.status, "session_id": r.session_id, "created_at": as_utc(r.created_at).isoformat()}


@router.get("/roadmap")
def roadmap(user: User = Depends(current_user), db: Session = Depends(get_db)):
    recs = db.scalars(select(LearningRecommendation).where(LearningRecommendation.user_id == user.id)
                      .order_by(LearningRecommendation.status.desc(), LearningRecommendation.priority,
                                LearningRecommendation.created_at.desc())).all()
    return {"recommendations": [rec_out(r) for r in recs], "mastery": mastery_rows(db, user.id)}


@router.patch("/roadmap/{rec_id}")
def update_rec(rec_id: int, body: RecommendationUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.scalar(select(LearningRecommendation).where(LearningRecommendation.id == rec_id,
                                                       LearningRecommendation.user_id == user.id))
    if r is None:
        raise HTTPException(404, "Recommendation not found")
    r.status = body.status
    db.commit()
    return rec_out(r)
