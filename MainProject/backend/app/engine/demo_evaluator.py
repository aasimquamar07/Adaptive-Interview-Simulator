"""Heuristic evaluator used in DEMO MODE (no LLM key) and as a fallback if the LLM fails.

It scores an answer against the question's rubric concepts with keyword/synonym patterns. It is
transparent and deterministic, but it cannot truly *understand* an answer (it can't spot a
confidently-stated misconception, for example), so its self-reported confidence is capped low and
the UI labels these evaluations as heuristic.

Speaking confidence is deliberately ignored: hedges such as "I think" or "maybe" never lower the
correctness or depth scores.
"""
from __future__ import annotations

import re

from .question_bank import EXAMPLE, Concept
from .scoring import Evaluation, normalize_evaluation
from .text_utils import tokens

DONT_KNOW = re.compile(r"\b(i ?don'?t know|no idea|not sure|idk|i have no clue|can't remember|cannot remember|pata nahi|nahi pata|maloom nahi)\b", re.I)
FILLERS = re.compile(r"\b(um+|uh+|erm|you know|like,|basically|actually|sort of|kind of)\b", re.I)
CODEISH = re.compile(r"[{};=]|\bdef |\bclass |\breturn\b|=>|\bfor\b.*\bin\b|\bwhile\b")


def concepts_from_json(items: list) -> list[Concept]:
    """Rebuild Concept objects from stored JSON. LLM-generated rubrics only have labels, so derive
    patterns from the label's significant words."""
    out = []
    for it in items or []:
        if isinstance(it, dict) and it.get("patterns"):
            out.append(Concept(it.get("label", ""), tuple(it["patterns"])))
        else:
            label = it.get("label", "") if isinstance(it, dict) else str(it)
            words = [w for w in tokens(label) if len(w) > 3][:5]
            pats = tuple(re.escape(w[:max(4, len(w) - 2)]) for w in words) or (re.escape(label.lower()),)
            out.append(Concept(label, pats))
    return out


def _clarity(answer: str, words: int) -> float:
    sentences = [s for s in re.split(r"[.!?\n]+", answer) if s.strip()]
    avg_len = words / max(1, len(sentences))
    score = 6.0
    if 25 <= words <= 260:
        score += 1.5
    elif words < 10:
        score -= 3
    elif words < 25:
        score -= 1
    elif words > 400:
        score -= 1
    if 6 <= avg_len <= 30:
        score += 1
    elif avg_len > 45:
        score -= 1.5
    if re.search(r"\b(first|second|then|finally|for example|because|so that|in short|e\.g)\b", answer, re.I):
        score += 1
    filler_ratio = len(FILLERS.findall(answer)) / max(1, words)
    score -= min(2.5, filler_ratio * 40)
    return max(0.0, min(10.0, score))


def evaluate(question_text: str, concepts: list[Concept], answer: str, kind: str = "core") -> Evaluation:
    text = answer.strip()
    words = len(text.split())

    if words == 0 or (DONT_KNOW.search(text) and words < 15):
        return normalize_evaluation({
            "correctness": 0.5, "relevance": 3.5, "depth": 0.5, "clarity": 5 if words else 0,
            "confidence": 0.7,
            "did_well": "You were honest that you weren't sure, which is better than guessing in a real interview.",
            "missing": "The answer didn't cover the core ideas yet.",
            "improvement": "Try reasoning out loud from what you do know. Interviewers give credit for a structured partial answer.",
            "missing_concepts": [c.label for c in concepts][:4],
        }, "demo-heuristic")

    matched = [c for c in concepts if c.matches(text)]
    missing = [c for c in concepts if c not in matched]
    coverage = len(matched) / len(concepts) if concepts else 0.5
    has_example = EXAMPLE.matches(text) or len(CODEISH.findall(text)) >= 2

    q_tokens = tokens(question_text)
    overlap = len(q_tokens & tokens(text)) / max(1, len(q_tokens))

    # Anything correct earns at least "partial"; full coverage earns full marks.
    correctness = 2.5 + 7.5 * coverage if matched else 1.0
    if words < 8:
        correctness *= 0.6
    relevance = 3.0 + 7.0 * min(1.0, coverage * 1.4 + overlap * 0.8)
    if coverage == 0 and overlap < 0.12:
        relevance = 2.0
    depth = 1.0 + 5.5 * coverage + (1.5 if has_example else 0) + min(2.0, words / 90)
    if coverage < 0.25:
        depth = min(depth, 4.0)
    clarity = _clarity(text, words)
    confidence = 0.45 + (0.1 if words >= 30 else 0) + (0.05 if coverage in (0, 1) else 0)

    if matched:
        did_well = "You covered: " + "; ".join(c.label for c in matched[:3]) + "."
        if has_example:
            did_well += " Including a concrete example helped."
    elif has_example:
        did_well = "You tried to ground your answer in a concrete example."
    else:
        did_well = "You engaged with the question and gave a direct answer."

    if kind in ("behavioral",):
        improvement = ("Structure it with STAR: the situation, your specific actions (use 'I', not 'we'), "
                       "and a measurable result.")
    elif missing:
        improvement = f"Add a clear explanation of {missing[0].label}."
        if not has_example and kind not in ("coding",):
            improvement += " Back it up with a short, concrete example."
    elif not has_example and kind not in ("coding",):
        improvement = "Strong coverage. A concrete example from real code or a project would make it interview-ready."
    else:
        improvement = "Well rounded. Practise delivering it concisely in under two minutes."

    return normalize_evaluation({
        "correctness": correctness, "relevance": relevance, "depth": depth, "clarity": clarity,
        "confidence": min(confidence, 0.65),
        "did_well": did_well,
        "missing": ("; ".join(c.label for c in missing).capitalize() + ".") if missing else "Nothing major missing.",
        "improvement": improvement,
        "missing_concepts": [c.label for c in missing],
    }, "demo-heuristic")
