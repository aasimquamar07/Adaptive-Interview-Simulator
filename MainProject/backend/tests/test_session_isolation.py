"""One candidate's interviews, memory and recommendations are never visible to another."""
from app.database import SessionLocal
from app.engine.interviewer import history_texts
from app.models import InterviewSession

from .conftest import strong_answer


def test_other_users_cannot_read_or_act_on_a_session(client, make_user, start):
    alice, bob = make_user("alice"), make_user("bob")
    s = start(alice)
    sid, qid = s["id"], s["current_question"]["id"]
    for method, path, body in [
        ("get", f"/api/interviews/{sid}", None),
        ("get", f"/api/interviews/{sid}/report", None),
        ("post", f"/api/interviews/{sid}/answer", {"question_id": qid, "answer": "stolen"}),
        ("post", f"/api/interviews/{sid}/skip", {"question_id": qid}),
        ("post", f"/api/interviews/{sid}/hint", {"question_id": qid}),
        ("post", f"/api/interviews/{sid}/repeat", {"question_id": qid}),
        ("post", f"/api/interviews/{sid}/end", None),
    ]:
        r = getattr(client, method)(path, headers=bob, **({"json": body} if body else {}))
        assert r.status_code == 404, (path, r.status_code)
    # Alice's session is untouched by Bob's attempts.
    mine = client.get(f"/api/interviews/{sid}", headers=alice).json()
    assert mine["status"] == "active" and mine["current_question"]["hints_used"] == 0


def test_history_memory_and_roadmap_are_per_user(client, make_user, start):
    alice, bob = make_user("alice"), make_user("bob")
    s = start(alice, num_questions=3)
    sid = s["id"]
    q = s["current_question"]
    client.post(f"/api/interviews/{sid}/answer", json={"question_id": q["id"], "answer": "not sure"}, headers=alice)
    client.post(f"/api/interviews/{sid}/end", headers=alice)

    assert len(client.get("/api/interviews", headers=alice).json()) == 1
    assert client.get("/api/interviews", headers=bob).json() == []
    bob_over = client.get("/api/analytics/overview", headers=bob).json()
    assert bob_over["total_sessions"] == 0 and bob_over["mastery"] == []
    assert client.get("/api/roadmap", headers=bob).json()["recommendations"] == []

    alice_recs = client.get("/api/roadmap", headers=alice).json()["recommendations"]
    assert alice_recs
    r = client.patch(f"/api/roadmap/{alice_recs[0]['id']}", json={"status": "done"}, headers=bob)
    assert r.status_code == 404


def test_personalisation_history_only_uses_own_questions(client, make_user, start):
    alice, bob = make_user("alice"), make_user("bob")
    a = start(alice)
    client.post(f"/api/interviews/{a['id']}/skip", json={"question_id": a["current_question"]["id"]}, headers=alice)
    b = start(bob)
    db = SessionLocal()
    try:
        bob_id = db.get(InterviewSession, b["id"]).user_id
        alice_id = db.get(InterviewSession, a["id"]).user_id
        assert len(history_texts(db, bob_id)) == 1      # only Bob's single question
        assert len(history_texts(db, alice_id)) == 2    # Alice's two questions, none of Bob's
    finally:
        db.close()


def test_new_session_state_does_not_leak_between_sessions(client, make_user, start):
    alice = make_user("alice")
    s1 = start(alice)
    q = s1["current_question"]
    client.post(f"/api/interviews/{s1['id']}/answer", json={"question_id": q["id"], "answer": strong_answer(q["id"])}, headers=alice)
    s2 = start(alice)  # starting a new interview closes the previous one
    assert s2["id"] != s1["id"] and len(s2["transcript"]) == 1 and s2["answered_count"] == 0
    assert client.get(f"/api/interviews/{s1['id']}", headers=alice).json()["status"] == "completed"


def test_unauthenticated_requests_are_rejected(client):
    assert client.get("/api/interviews").status_code == 401
    assert client.get("/api/interviews", headers={"Authorization": "Bearer forged.token.value"}).status_code == 401
