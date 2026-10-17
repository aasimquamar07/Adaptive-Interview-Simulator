import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..engine.text_utils import extract_skills
from ..models import (CandidateProfile, InterviewSession, LearningRecommendation, TopicMastery, User)
from ..schemas import ConsentIn, ProfileUpdate
from ..security import current_user

router = APIRouter(prefix="/api", tags=["profile"])
MAX_UPLOAD = 5 * 1024 * 1024


def profile_of(user: User, db: Session) -> CandidateProfile:
    if user.profile is None:
        user.profile = CandidateProfile()
        db.commit()
    return user.profile


def profile_out(user: User, p: CandidateProfile) -> dict:
    return {"email": user.email, "full_name": p.full_name, "target_role": p.target_role,
            "experience_level": p.experience_level, "preferred_language": p.preferred_language,
            "resume_text": p.resume_text, "resume_skills": p.resume_skills or [],
            "training_consent": p.training_consent,
            "training_consent_at": p.training_consent_at.isoformat() if p.training_consent_at else None}


@router.get("/profile")
def get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return profile_out(user, profile_of(user, db))


@router.put("/profile")
def update_profile(body: ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = profile_of(user, db)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v.strip() if isinstance(v, str) else v)
    if body.resume_text is not None:
        p.resume_skills = extract_skills(p.resume_text)
    db.commit()
    return profile_out(user, p)


@router.put("/profile/consent")
def set_consent(body: ConsentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = profile_of(user, db)
    p.training_consent = body.training_consent
    p.training_consent_at = datetime.now(timezone.utc) if body.training_consent else None
    db.commit()
    return profile_out(user, p)


@router.post("/uploads/extract")
async def extract(file: UploadFile = File(...), user: User = Depends(current_user)):
    """Extract plain text (and recognised skills) from a resume or job description. Nothing is
    stored here; the client decides whether to save it to the profile or use it for one interview."""
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File too large (max 5 MB)")
    name = (file.filename or "").lower()
    try:
        if name.endswith(".pdf") or data[:4] == b"%PDF":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:15])
        elif name.endswith((".txt", ".md", ".text")) or not name:
            text = data.decode("utf-8", errors="ignore")
        else:
            raise HTTPException(415, "Please upload a PDF, TXT or MD file (or paste the text)")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Could not read that file. Try another format or paste the text instead.")
    text = " ".join(text.split())[:20000]
    if not text:
        raise HTTPException(422, "No readable text found (scanned PDFs need OCR). Please paste the text instead.")
    return {"text": text, "skills": extract_skills(text), "characters": len(text)}


@router.get("/profile/export")
def export_data(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Everything stored about the current user, as JSON (data portability)."""
    p = profile_of(user, db)
    sessions = db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id)).all()
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile_out(user, p),
        "topic_mastery": [{"topic": m.topic, "mastery": m.mastery, "attempts": m.attempts}
                          for m in db.scalars(select(TopicMastery).where(TopicMastery.user_id == user.id))],
        "sessions": [{
            "id": s.id, "role": s.role, "custom_role": s.custom_role, "type": s.interview_type,
            "started_at": s.started_at.isoformat() if s.started_at else None, "status": s.status,
            "overall_score": s.overall_score, "report": s.report,
            "questions": [{"text": q.text, "topic": q.topic, "status": q.status,
                           "answer": q.answer.text if q.answer else None,
                           "score": q.answer.evaluation.score if q.answer and q.answer.evaluation else None}
                          for q in s.questions],
        } for s in sessions],
    }


@router.delete("/profile/history")
def delete_history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    for s in db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id)).all():
        db.delete(s)
    db.execute(delete(TopicMastery).where(TopicMastery.user_id == user.id))
    db.execute(delete(LearningRecommendation).where(LearningRecommendation.user_id == user.id))
    db.commit()
    return {"deleted": True}


@router.delete("/profile")
def delete_account(user: User = Depends(current_user), db: Session = Depends(get_db)):
    delete_history(user, db)
    db.delete(user)
    db.commit()
    return {"deleted": True}
