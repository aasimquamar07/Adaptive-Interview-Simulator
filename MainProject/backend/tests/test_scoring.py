"""Scoring validation, heuristic evaluator behaviour, mastery maths and LLM fallback."""
import pytest

from app.config import Settings
from app.engine import demo_evaluator
from app.engine.composer import compose
from app.engine.llm import LLMClient, LLMError
from app.engine.mastery import update_mastery
from app.engine.policy import Decision
from app.engine.question_bank import T
from app.engine.scoring import EvaluationError, normalize_evaluation, overall_score

GOOD = {"correctness": 8, "relevance": 9, "depth": 7, "clarity": 6, "confidence": 0.8,
        "did_well": "x", "missing": "y", "improvement": "z", "missing_concepts": []}


def test_valid_evaluation_passes_and_score_is_weighted():
    ev = normalize_evaluation(GOOD, "llm")
    assert ev.score == overall_score(8, 9, 7, 6) == 7.7  # 3.2 + 1.8 + 1.75 + 0.9
    assert ev.verdict == "correct"


def test_out_of_range_values_are_clamped_or_rescaled():
    ev = normalize_evaluation({**GOOD, "correctness": 85, "relevance": -3, "depth": 14, "clarity": 7, "confidence": 80}, "llm")
    assert ev.correctness == 8.5 and ev.relevance == 0 and ev.depth == 1.4 and ev.confidence == 0.8


def test_verdict_is_derived_not_trusted():
    ev = normalize_evaluation({**GOOD, "correctness": 2, "verdict": "correct"}, "llm")
    assert ev.verdict == "incorrect"
    assert normalize_evaluation({**GOOD, "relevance": 1}, "llm").verdict == "off_topic"


@pytest.mark.parametrize("bad", [
    {k: v for k, v in GOOD.items() if k != "depth"},
    {**GOOD, "correctness": "great"},
    {**GOOD, "clarity": float("nan")},
    {**GOOD, "relevance": True},
    "not a dict",
])
def test_invalid_evaluations_are_rejected(bad):
    with pytest.raises(EvaluationError):
        normalize_evaluation(bad, "llm")


def _bank(topic, idx=0):
    return T[topic].questions[idx]


def test_heuristic_ranks_complete_partial_and_unknown_answers():
    bq = _bank("java_oop")
    full = ("Polymorphism means one interface, many forms. Compile-time polymorphism is method overloading; "
            "runtime polymorphism is overriding with dynamic dispatch. For example Animal a = new Dog(); a.speak().")
    part = "It means one thing can have many forms."
    scores = [demo_evaluator.evaluate(bq.text, list(bq.concepts), a).score for a in (full, part, "I don't know")]
    assert scores[0] > scores[1] > scores[2]
    assert demo_evaluator.evaluate(bq.text, list(bq.concepts), part).verdict == "partial"


def test_hesitant_tone_does_not_lower_technical_scores():
    bq = _bank("java_collections", 1)
    content = ("HashMap uses hashCode to find the bucket index. Collisions are chained in a linked list, "
               "and a tree since Java 8. equals compares keys. It resizes at load factor 0.75.")
    sure = demo_evaluator.evaluate(bq.text, list(bq.concepts), content)
    unsure = demo_evaluator.evaluate(bq.text, list(bq.concepts), "I think, maybe, " + content + " I'm not 100% sure though.")
    assert unsure.correctness == sure.correctness and unsure.depth >= sure.depth - 0.2


def test_fluent_but_wrong_answer_scores_low_on_correctness():
    bq = _bank("java_collections", 1)
    fluent = ("Great question. In short, HashMap is a sorted structure that stores every entry in insertion order. "
              "First, it keeps entries in a list. Then it scans that list. Finally, it returns the value.")
    ev = demo_evaluator.evaluate(bq.text, list(bq.concepts), fluent)
    assert ev.clarity >= 7 and ev.correctness <= 4.5


def test_mastery_uses_substance_confidence_hints_and_skips():
    hi = update_mastery(0.5, correctness=9, depth=9, confidence=0.9, level=2)
    lo_conf = update_mastery(0.5, correctness=9, depth=9, confidence=0.2, level=2)
    hinted = update_mastery(0.5, correctness=9, depth=9, confidence=0.9, level=2, hints_used=2)
    skipped = update_mastery(0.5, skipped=True)
    assert hi > lo_conf > 0.5 and hi > hinted and skipped < 0.5
    assert update_mastery(0.5, correctness=10, depth=10, confidence=1, level=3) > \
        update_mastery(0.5, correctness=10, depth=10, confidence=1, level=1)


def llm_with(monkeypatch, fn):
    client = LLMClient(Settings(llm_provider="anthropic", anthropic_api_key="test-key"))
    monkeypatch.setattr(client, "json_call", fn)
    return client


def test_llm_evaluation_rejects_malformed_output(monkeypatch):
    client = llm_with(monkeypatch, lambda *a, **k: {"correctness": "excellent"})
    with pytest.raises(LLMError):
        client.evaluate(role="Java Developer", question="Q?", answer="A", rubric=[], level=2, kind="core",
                        language="en", hints_used=0, thread=[])


def test_llm_question_that_repeats_is_rejected(monkeypatch):
    client = llm_with(monkeypatch, lambda *a, **k: {"question": "What is polymorphism in Java?",
                                                     "key_concepts": ["a"], "hint": "", "acknowledgement": ""})
    d = Decision("new_topic", "java_oop", 2, "core", "test")
    with pytest.raises(LLMError):
        client.generate_question(decision=d, role="Java Developer", interview_type="technical", language="en", thread=[],
                                 avoid=["What is polymorphism in Java?"], resume="", jd="", remaining_minutes=10, example=None)


def test_composer_fallback_always_produces_a_question():
    for action, kind in (("new_topic", "core"), ("followup", "followup"), ("diagnostic", "diagnostic"), ("scenario", "scenario")):
        c = compose(Decision(action, "java_oop", 2, kind, "t", ["runtime polymorphism (overriding)"]),
                    parent={"text": "What is polymorphism in Java?", "bank_id": "java_oop_1", "key_concepts": [],
                            "topic": "java_oop", "kind": "core", "level": 1},
                    session_ids={"java_oop_1"}, session_texts=["What is polymorphism in Java?"], history_texts=[],
                    used_templates=[], resume_skills=[])
        assert c.text and c.concepts and c.text != "What is polymorphism in Java?"
        # A follow-up must never paste the rubric (i.e. the answer) into the question.
        assert "overriding" not in c.text.lower() or action == "followup" and c.template_id.startswith("bank_fu")
