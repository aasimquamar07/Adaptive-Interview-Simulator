"""Database schema (SQLAlchemy ORM). Mirrors backend/schema.sql for PostgreSQL.

Isolation rule: every row that holds candidate data carries `user_id` (directly or via its
session), and every query in the routers filters on the authenticated user's id.
"""
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profile: Mapped["CandidateProfile"] = relationship(back_populates="user", uselist=False,
                                                       cascade="all, delete-orphan")


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    target_role: Mapped[str] = mapped_column(String(120), default="")
    experience_level: Mapped[str] = mapped_column(String(40), default="")
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")
    resume_text: Mapped[str] = mapped_column(Text, default="")
    resume_skills: Mapped[list] = mapped_column(JSON, default=list)
    # Explicit opt-in. Interview data is NEVER exported for model training unless this is true.
    training_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    training_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="profile")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(120))
    custom_role: Mapped[str] = mapped_column(String(120), default="")
    interview_type: Mapped[str] = mapped_column(String(30))
    difficulty_mode: Mapped[str] = mapped_column(String(20))  # beginner|intermediate|advanced|adaptive
    current_level: Mapped[int] = mapped_column(Integer, default=2)  # 1..3
    duration_minutes: Mapped[int] = mapped_column(Integer, default=20)
    max_questions: Mapped[int] = mapped_column(Integer, default=8)
    language: Mapped[str] = mapped_column(String(10), default="en")
    mode: Mapped[str] = mapped_column(String(10), default="text")  # text|voice
    resume_text: Mapped[str] = mapped_column(Text, default="")
    job_description: Mapped[str] = mapped_column(Text, default="")
    jd_skills: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|completed|expired
    ai_provider: Mapped[str] = mapped_column(String(30), default="demo")
    # Working memory for the adaptive engine (focus topics carried over from history, counters)
    engine_state: Mapped[dict] = mapped_column(JSON, default=dict)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="InterviewQuestion.seq")
    events: Mapped[list["InterviewEvent"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="InterviewEvent.id")


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(80))
    level: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))  # core|followup|diagnostic|scenario|behavioral|project|coding
    text: Mapped[str] = mapped_column(Text)
    bank_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    parent_question_id: Mapped[int | None] = mapped_column(ForeignKey("interview_questions.id"), nullable=True)
    key_concepts: Mapped[list] = mapped_column(JSON, default=list)  # rubric, never shown before answering
    hint: Mapped[str] = mapped_column(Text, default="")
    rationale: Mapped[str] = mapped_column(Text, default="")  # why the engine chose this question
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    repeats: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|answered|skipped
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[InterviewSession] = relationship(back_populates="questions")
    answer: Mapped["CandidateAnswer"] = relationship(back_populates="question", uselist=False,
                                                     cascade="all, delete-orphan")


class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("interview_questions.id", ondelete="CASCADE"), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    input_mode: Mapped[str] = mapped_column(String(10), default="text")
    response_seconds: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    question: Mapped[InterviewQuestion] = relationship(back_populates="answer")
    evaluation: Mapped["AnswerEvaluation"] = relationship(back_populates="answer", uselist=False,
                                                          cascade="all, delete-orphan")


class AnswerEvaluation(Base):
    __tablename__ = "answer_evaluations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    answer_id: Mapped[int] = mapped_column(ForeignKey("candidate_answers.id", ondelete="CASCADE"), unique=True)
    correctness: Mapped[float] = mapped_column(Float)   # 0..10
    relevance: Mapped[float] = mapped_column(Float)     # 0..10
    depth: Mapped[float] = mapped_column(Float)         # 0..10
    clarity: Mapped[float] = mapped_column(Float)       # 0..10 (communication, NOT technical ability)
    confidence: Mapped[float] = mapped_column(Float)    # 0..1, evaluator's confidence in its own judgement
    score: Mapped[float] = mapped_column(Float)         # 0..10 overall
    mastery_estimate: Mapped[float] = mapped_column(Float)  # 0..1 topic mastery after this answer
    verdict: Mapped[str] = mapped_column(String(20))    # correct|partial|incorrect|off_topic
    did_well: Mapped[str] = mapped_column(Text, default="")
    missing: Mapped[str] = mapped_column(Text, default="")
    improvement: Mapped[str] = mapped_column(Text, default="")
    missing_concepts: Mapped[list] = mapped_column(JSON, default=list)
    evaluator: Mapped[str] = mapped_column(String(30), default="demo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    answer: Mapped[CandidateAnswer] = relationship(back_populates="evaluation")


class InterviewEvent(Base):
    """Hint / repeat / skip / end actions, kept as part of the interview context."""
    __tablename__ = "interview_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[InterviewSession] = relationship(back_populates="events")


class TopicMastery(Base):
    """Long-term, per-candidate memory of how well each topic is understood."""
    __tablename__ = "topic_mastery"
    __table_args__ = (UniqueConstraint("user_id", "topic", name="uq_mastery_user_topic"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(80))
    mastery: Mapped[float] = mapped_column(Float, default=0.5)  # 0..1
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    struggle_count: Mapped[int] = mapped_column(Integer, default=0)
    last_level: Mapped[int] = mapped_column(Integer, default=2)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LearningRecommendation(Base):
    __tablename__ = "learning_recommendations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=True)
    topic: Mapped[str] = mapped_column(String(80))
    priority: Mapped[int] = mapped_column(Integer, default=2)  # 1 = highest
    reason: Mapped[str] = mapped_column(Text, default="")
    actions: Mapped[list] = mapped_column(JSON, default=list)
    practice_questions: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|done
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
