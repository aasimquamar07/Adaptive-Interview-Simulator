import os
import tempfile
import uuid

# Configure an isolated SQLite database and demo mode BEFORE the app is imported.
# Set TEST_DATABASE_URL to run the suite against PostgreSQL instead of a temp SQLite file.
_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_db}")
os.environ["LLM_PROVIDER"] = "demo"
os.environ["JWT_SECRET"] = "test-secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(client):
    def _make(name: str = "user"):
        email = f"{name}-{uuid.uuid4().hex[:8]}@example.com"
        r = client.post("/api/auth/signup", json={"email": email, "password": "password123", "full_name": name})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token']}"}
    return _make


@pytest.fixture
def start(client):
    def _start(headers, **cfg):
        body = {"role": "java_developer", "interview_type": "technical", "difficulty": "adaptive",
                "duration_minutes": 20, "num_questions": 6, **cfg}
        r = client.post("/api/interviews", json=body, headers=headers)
        assert r.status_code == 200, r.text
        return r.json()
    return _start


def strong_answer(question_id: int) -> str:
    """Builds an answer that covers the stored rubric (test helper only)."""
    from app.database import SessionLocal
    from app.models import InterviewQuestion
    db = SessionLocal()
    try:
        q = db.get(InterviewQuestion, question_id)
        labels = [c["label"] if isinstance(c, dict) else str(c) for c in q.key_concepts]
    finally:
        db.close()
    return ". ".join(labels) + ". For example, I used this in a project because of the trade-off."
