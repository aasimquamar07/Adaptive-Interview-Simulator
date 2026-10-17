"""Validation and normalisation of answer evaluations.

Whatever produced an evaluation (LLM or heuristic), it passes through `normalize_evaluation`, which:
  * coerces and clamps every metric to its valid range,
  * rescales obviously mis-scaled values (e.g. 85 on a 0-10 scale, 70 for a 0-1 confidence),
  * derives the overall score and verdict deterministically from the metrics, so a model cannot
    label a 2/10 answer as "correct",
  * bounds free-text fields.
If the required metrics are missing or non-numeric, EvaluationError is raised and the caller falls
back to the heuristic evaluator.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

METRICS = ("correctness", "relevance", "depth", "clarity")
WEIGHTS = {"correctness": 0.4, "relevance": 0.2, "depth": 0.25, "clarity": 0.15}


class EvaluationError(ValueError):
    pass


class Evaluation(BaseModel):
    correctness: float = Field(ge=0, le=10)
    relevance: float = Field(ge=0, le=10)
    depth: float = Field(ge=0, le=10)
    clarity: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=10)
    verdict: str
    did_well: str = ""
    missing: str = ""
    improvement: str = ""
    missing_concepts: list[str] = []
    evaluator: str = "demo"


def _num(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise EvaluationError(f"{name} must be numeric")
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise EvaluationError(f"{name} must be numeric, got {value!r}")
    if v != v:  # NaN
        raise EvaluationError(f"{name} is NaN")
    return v


def _scale10(v: float) -> float:
    if 10 < v <= 100:  # model answered on a 0-100 scale
        v = v / 10
    return round(min(10.0, max(0.0, v)), 1)


def _scale1(v: float) -> float:
    if 1 < v <= 10:
        v = v / 10
    elif 10 < v <= 100:
        v = v / 100
    return round(min(1.0, max(0.0, v)), 2)


def overall_score(c: float, r: float, d: float, cl: float) -> float:
    return round(c * WEIGHTS["correctness"] + r * WEIGHTS["relevance"] + d * WEIGHTS["depth"] + cl * WEIGHTS["clarity"], 1)


def derive_verdict(correctness: float, relevance: float) -> str:
    if relevance < 3:
        return "off_topic"
    if correctness >= 7.5:
        return "correct"
    if correctness >= 4:
        return "partial"
    return "incorrect"


def _text(v: Any, limit: int = 500) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        v = "; ".join(str(x) for x in v)
    return str(v).strip()[:limit]


def normalize_evaluation(raw: dict, evaluator: str) -> Evaluation:
    if not isinstance(raw, dict):
        raise EvaluationError("evaluation must be an object")
    missing_keys = [m for m in METRICS if m not in raw]
    if missing_keys:
        raise EvaluationError(f"missing metrics: {missing_keys}")
    vals = {m: _scale10(_num(raw[m], m)) for m in METRICS}
    conf = _scale1(_num(raw.get("confidence", 0.6), "confidence"))
    concepts = raw.get("missing_concepts") or []
    if isinstance(concepts, str):
        concepts = [s.strip() for s in concepts.split(";") if s.strip()]
    concepts = [_text(c, 120) for c in concepts if _text(c)][:6]
    return Evaluation(
        **vals,
        confidence=conf,
        score=overall_score(vals["correctness"], vals["relevance"], vals["depth"], vals["clarity"]),
        verdict=derive_verdict(vals["correctness"], vals["relevance"]),
        did_well=_text(raw.get("did_well")),
        missing=_text(raw.get("missing")),
        improvement=_text(raw.get("improvement")),
        missing_concepts=concepts,
        evaluator=evaluator,
    )
