"""Export anonymised, CONSENTED interview data for future, carefully evaluated model improvement.

The running app never trains or fine-tunes a model. This script exists so a future version can
build a training/evaluation set responsibly:

  * Only users with candidate_profiles.training_consent = TRUE are included.
  * User ids are replaced by a salted one-way hash; emails, names and resumes are never exported.
  * Emails, phone numbers and URLs inside answers are redacted.
  * Output is JSONL for human review before any use.

Usage (from backend/):  python -m scripts.export_training_data --out consented.jsonl --salt "$EXPORT_SALT"
"""
import argparse
import hashlib
import json
import re

from sqlalchemy import select

from app.database import SessionLocal
from app.models import CandidateProfile, InterviewSession

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{8,}\d)")
URL = re.compile(r"https?://\S+")


def redact(text: str) -> str:
    return URL.sub("[url]", PHONE.sub("[phone]", EMAIL.sub("[email]", text or "")))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--salt", required=True, help="secret salt for pseudonymous ids")
    args = ap.parse_args()
    db = SessionLocal()
    n = 0
    with open(args.out, "w", encoding="utf-8") as f:
        consenting = db.scalars(select(CandidateProfile.user_id).where(CandidateProfile.training_consent.is_(True))).all()
        for s in db.scalars(select(InterviewSession).where(InterviewSession.user_id.in_(consenting),
                                                           InterviewSession.status == "completed")):
            pid = hashlib.sha256(f"{args.salt}:{s.user_id}".encode()).hexdigest()[:16]
            for q in s.questions:
                if not (q.answer and q.answer.evaluation):
                    continue
                e = q.answer.evaluation
                f.write(json.dumps({
                    "candidate": pid, "role": s.role, "interview_type": s.interview_type, "topic": q.topic,
                    "level": q.level, "kind": q.kind, "question": q.text, "answer": redact(q.answer.text),
                    "rubric": [c.get("label") if isinstance(c, dict) else c for c in q.key_concepts],
                    "scores": {k: getattr(e, k) for k in ("correctness", "relevance", "depth", "clarity", "score")},
                    "evaluator": e.evaluator,
                }, ensure_ascii=False) + "\n")
                n += 1
    db.close()
    print(f"Exported {n} answer records from {len(consenting)} consenting user(s) to {args.out}")


if __name__ == "__main__":
    main()
