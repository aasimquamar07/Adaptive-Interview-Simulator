"""LLM mode end to end, with the Anthropic HTTP API faked at the transport layer."""
import httpx
import pytest

from app.config import Settings
from app.engine import llm as llm_mod
from app.engine.llm import LLMClient
from app.engine.scoring import overall_score
from app.main import app
from app.routers.interviews import get_llm


class FakeAnthropic:
    def __init__(self):
        self.calls, self.fail = [], False
        self.n = 0

    def __call__(self, url, headers=None, json=None, timeout=None):
        assert url == "https://api.anthropic.com/v1/messages"
        assert headers["x-api-key"] == "server-side-key"  # key is sent only from the server
        tool = json["tool_choice"]["name"]
        self.calls.append(tool)
        if self.fail:
            return httpx.Response(529, json={"error": "overloaded"})
        self.n += 1
        if tool == "next_question":
            qs = ["How would you explain garbage collection pauses to a product manager?",
                  "Walk me through designing a thread-safe in-memory cache for sessions.",
                  "Which collection would you choose for a leaderboard, and why?",
                  "Describe debugging a deadlock you encountered in production.",
                  "How does dependency injection change the way you write unit tests?"]
            out = {"acknowledgement": "Thanks, let's continue.", "question": qs[self.n % len(qs)],
                   "key_concepts": ["core idea", "trade-offs"], "hint": "Think about the trade-offs."}
        elif tool == "answer_evaluation":
            out = {"correctness": 8, "relevance": 9, "depth": 7, "clarity": 8, "confidence": 0.85,
                   "did_well": "Clear core idea.", "missing": "Trade-offs.", "improvement": "Discuss trade-offs.",
                   "missing_concepts": ["trade-offs"]}
        else:
            out = {"summary": "Solid session overall.", "strengths": ["Core ideas"], "weaknesses": ["Trade-offs"],
                   "practice_questions": [{"topic": "Java", "question": "Explain a trade-off you made recently."}]}
        return httpx.Response(200, json={"content": [{"type": "tool_use", "name": tool, "input": out}]})


@pytest.fixture
def fake(monkeypatch):
    f = FakeAnthropic()
    monkeypatch.setattr(llm_mod.httpx, "post", f)
    app.dependency_overrides[get_llm] = lambda: LLMClient(Settings(llm_provider="anthropic", anthropic_api_key="server-side-key"))
    yield f
    app.dependency_overrides.pop(get_llm, None)


def test_llm_generates_questions_and_evaluates(client, make_user, start, fake):
    h = make_user()
    s = start(h, num_questions=3)
    assert s["current_question"]["source"] == "llm" and s["ai_provider"].startswith("anthropic")
    sid, q = s["id"], s["current_question"]
    r = client.post(f"/api/interviews/{sid}/answer", json={"question_id": q["id"], "answer": "My answer"}, headers=h).json()
    assert r["evaluation"]["evaluator"].startswith("llm:")
    assert r["evaluation"]["score"] == overall_score(8, 9, 7, 8) and r["evaluation"]["verdict"] == "correct"
    assert r["next_question"]["source"] == "llm"
    rep = client.post(f"/api/interviews/{sid}/end", headers=h).json()["report"]
    assert rep["summary_source"] == "ai" and rep["summary"] == "Solid session overall."
    assert {"next_question", "answer_evaluation", "interview_report"} <= set(fake.calls)


def test_llm_outage_falls_back_without_breaking_the_interview(client, make_user, start, fake):
    h = make_user()
    s = start(h, num_questions=3)
    fake.fail = True  # provider goes down mid-interview
    q = s["current_question"]
    r = client.post(f"/api/interviews/{s['id']}/answer", json={"question_id": q["id"], "answer": "not sure"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["evaluation"]["evaluator"] == "fallback-heuristic"
    assert body["next_question"]["source"] == "fallback" and body["next_question"]["text"]
    rep = client.post(f"/api/interviews/{s['id']}/end", headers=h).json()["report"]
    assert rep["summary_source"] == "computed" and rep["overall_score"] is not None
