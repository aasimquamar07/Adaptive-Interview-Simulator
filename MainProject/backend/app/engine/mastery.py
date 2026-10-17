"""Topic-mastery estimation (long-term candidate memory).

Mastery is a 0..1 estimate updated with an exponential moving average. Deliberate choices:
  * Evidence comes from correctness and depth only. Communication clarity is excluded, so a fluent
    but wrong answer does not raise mastery, and a hesitant but correct one is not penalised.
  * The update weight scales with the evaluator's own confidence (heuristic evaluations move the
    estimate less than confident LLM evaluations).
  * Harder questions carry more weight; a perfect beginner answer alone cannot prove full mastery.
  * Hints reduce the evidence; skips count as weak evidence of a gap.
"""
from __future__ import annotations

LEVEL_WEIGHT = {1: 0.8, 2: 1.0, 3: 1.25}
LEVEL_CAP = {1: 0.8, 2: 0.95, 3: 1.0}


def update_mastery(old: float | None, *, correctness: float = 0, depth: float = 0, confidence: float = 0.5,
                   level: int = 2, hints_used: int = 0, skipped: bool = False) -> float:
    prior = 0.5 if old is None else old
    if skipped:
        evidence, weight = 0.1, 0.25
    else:
        evidence = (0.6 * correctness + 0.4 * depth) / 10
        evidence -= min(0.3, 0.1 * hints_used)
        evidence = min(max(evidence, 0.0), LEVEL_CAP.get(level, 1.0))
        weight = (0.2 + 0.25 * confidence) * LEVEL_WEIGHT.get(level, 1.0)
    new = prior + weight * (evidence - prior)
    return round(min(1.0, max(0.0, new)), 3)


def mastery_label(m: float | None) -> str:
    if m is None:
        return "Not assessed"
    if m >= 0.75:
        return "Strong"
    if m >= 0.5:
        return "Developing"
    return "Needs work"
