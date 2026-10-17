"""End-to-end API behaviour: actions, limits, reports and cross-session personalisation."""
from datetime import timedelta

from app.database import SessionLocal
from app.models import InterviewSession

from .conftest import strong_answer


def test_hint_repeat_skip_are_recorded_and_hints_are_limited(client, make_user, start):
    h = make_user()
    s = start(h)
    sid, q = s["id"], s["current_question"]
    assert "key_concepts" not in q and "hint" not in q  # rubric and hint never sent up front
    h1 = client.post(f"/api/interviews/{sid}/hint", json={"question_id": q["id"]}, headers=h).json()
    h2 = client.post(f"/api/interviews/{sid}/hint", json={"question_id": q["id"]}, headers=h).json()
    assert h1["hints_used"] == 1 and h2["hints_used"] == 2 and h1["hint"] != h2["hint"]
    assert client.post(f"/api/interviews/{sid}/hint", json={"question_id": q["id"]}, headers=h).status_code == 409
    rep = client.post(f"/api/interviews/{sid}/repeat", json={"question_id": q["id"]}, headers=h).json()
    assert rep["text"] == q["text"]
    r = client.post(f"/api/interviews/{sid}/skip", json={"question_id": q["id"]}, headers=h).json()
    assert r["next_question"]["topic"] != q["topic"]
    # The skipped question can't be answered any more.
    assert client.post(f"/api/interviews/{sid}/answer", json={"question_id": q["id"], "answer": "late"}, headers=h).status_code == 409
    report = client.post(f"/api/interviews/{sid}/end", headers=h).json()["report"]
    assert report["objective"]["hints_used"] == 2 and report["objective"]["skipped"] == 1
    assert report["objective"]["repeats_requested"] == 1


def test_question_limit_is_enforced(client, make_user, start):
    h = make_user()
    s = start(h, num_questions=3)
    sid, q = s["id"], s["current_question"]
    seen = 0
    while q:
        r = client.post(f"/api/interviews/{sid}/answer", json={"question_id": q["id"], "answer": "not sure"}, headers=h).json()
        seen += 1
        q = r["next_question"]
    assert seen == 3 and r["finished"] and r["reason"] == "question_limit"
    assert r["session"]["status"] == "completed"


def test_time_limit_is_enforced_server_side(client, make_user, start):
    h = make_user()
    s = start(h, duration_minutes=10)
    db = SessionLocal()
    row = db.get(InterviewSession, s["id"])
    row.started_at = row.started_at - timedelta(minutes=15)
    db.commit()
    db.close()
    r = client.post(f"/api/interviews/{s['id']}/answer", json={"question_id": s["current_question"]["id"], "answer": "x"}, headers=h)
    assert r.status_code == 200 and r.json()["finished"] and r.json()["reason"] == "time"
    assert client.get(f"/api/interviews/{s['id']}/report", headers=h).json()["report"]["ended_reason"] == "time"


def test_full_interview_report_has_required_sections(client, make_user, start):
    h = make_user()
    s = start(h, num_questions=4)
    sid, q = s["id"], s["current_question"]
    answers = [strong_answer, lambda _: "I'm not sure", strong_answer, lambda _: "not sure"]
    i = 0
    while q:
        r = client.post(f"/api/interviews/{sid}/answer", json={"question_id": q["id"], "answer": answers[i](q["id"]),
                                                               "response_seconds": 30}, headers=h).json()
        ev = r["evaluation"]
        assert 0 <= ev["score"] <= 10 and ev["did_well"] and ev["verdict"] in ("correct", "partial", "incorrect", "off_topic")
        q, i = r["next_question"], i + 1
    rep = client.get(f"/api/interviews/{sid}/report", headers=h).json()["report"]
    for key in ("overall_score", "dimensions", "objective", "topics", "strengths", "weaknesses", "needs_review",
                "roadmap", "comparison", "summary", "disclaimer"):
        assert key in rep
    assert set(rep["dimensions"]) >= {"technical_knowledge", "problem_solving", "communication"}
    assert "guarantee" in rep["disclaimer"]
    assert rep["needs_review"] and rep["needs_review"][0]["strong_answer_covers"]


def test_memory_personalises_the_next_session(client, make_user, start):
    """A topic the candidate struggled with is scheduled first in the next interview."""
    h = make_user()
    s = start(h, num_questions=3)
    sid, first = s["id"], s["current_question"]
    weak_topic = first["topic"]
    q = first
    while q:
        ans = "not sure" if q["topic"] == weak_topic else strong_answer(q["id"])
        q = client.post(f"/api/interviews/{sid}/answer", json={"question_id": q["id"], "answer": ans}, headers=h).json()["next_question"]
    mastery = {m["topic"]: m for m in client.get("/api/analytics/overview", headers=h).json()["mastery"]}
    assert mastery[weak_topic]["mastery"] < 0.5
    nxt = start(h, num_questions=3)
    assert nxt["current_question"]["topic"] == weak_topic
    assert mastery[weak_topic]["name"] in nxt["focus_topics"]
    assert "earlier sessions" in nxt["current_question"]["why"]
    rep_cmp = client.post(f"/api/interviews/{nxt['id']}/end", headers=h).json()["report"]["comparison"]
    assert rep_cmp["sessions_compared"] >= 1


def test_validation_and_uploads(client, make_user):
    h = make_user()
    assert client.post("/api/interviews", json={"role": "custom", "custom_role": ""}, headers=h).status_code == 422
    assert client.post("/api/interviews", json={"role": "astronaut"}, headers=h).status_code == 422
    r = client.post("/api/uploads/extract", files={"file": ("cv.txt", b"Python developer: Django, PostgreSQL, Docker", "text/plain")}, headers=h)
    assert r.status_code == 200 and {"Python", "Django", "SQL", "Docker"} <= set(r.json()["skills"])
    assert client.post("/api/uploads/extract", files={"file": ("cv.exe", b"MZ", "application/octet-stream")}, headers=h).status_code == 415


def test_privacy_controls(client, make_user, start):
    h = make_user()
    assert client.get("/api/profile", headers=h).json()["training_consent"] is False  # opt-in only
    assert client.put("/api/profile/consent", json={"training_consent": True}, headers=h).json()["training_consent"]
    start(h)
    export = client.get("/api/profile/export", headers=h).json()
    assert len(export["sessions"]) == 1
    client.delete("/api/profile/history", headers=h)
    assert client.get("/api/interviews", headers=h).json() == []
    assert client.delete("/api/profile", headers=h).json()["deleted"]
    assert client.get("/api/profile", headers=h).status_code == 401
