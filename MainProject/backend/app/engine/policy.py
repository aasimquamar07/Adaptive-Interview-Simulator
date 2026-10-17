"""Adaptive interview policy: pure, deterministic and unit-tested.

After every answer, `decide_next` chooses *what kind* of question comes next:

  correct (>= 7.5)  -> practical scenario on the same topic (harder), or move to a new topic
  partial (4-7.5)   -> follow-up that probes the specific missing concepts
  incorrect / off   -> diagnostic (simpler) question on the same topic, then move on
  skipped           -> record a gap, move to a new topic at a lower level

Guard rails:
  * at most `max_followups` probing questions per topic thread (no infinite follow-up loops)
  * hard question limit and time limit -> "finish"
  * never the same topic twice in a row once a thread ends; repeats across the session are penalised

`choose_topic` ranks topics using session coverage, long-term mastery (weak topics from earlier
sessions are scheduled first), resume / job-description skills and, for mixed interviews, the
target mix of technical / coding / behavioural / project questions.

The LLM never decides the policy; it only writes the question for the decision made here. That
keeps the interview's behaviour predictable, testable and impossible to derail via prompt content.
"""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field

from .question_bank import T, BankQuestion
from .text_utils import is_repeat

FIXED_LEVEL = {"beginner": 1, "intermediate": 2, "advanced": 3}
LEVEL_LABEL = {1: "Beginner", 2: "Intermediate", 3: "Advanced"}
KIND_FOR_CATEGORY = {"technical": "core", "hr": "behavioral", "project": "project", "coding": "coding"}
MIX_TARGET = {"technical": 0.5, "coding": 0.2, "hr": 0.15, "project": 0.15}

CORRECT_AT = 7.5
PARTIAL_AT = 4.0


@dataclass
class AskedQ:
    topic: str
    level: int
    kind: str
    text: str
    bank_id: str | None = None
    score: float | None = None
    correctness: float | None = None
    verdict: str | None = None
    skipped: bool = False
    hints_used: int = 0
    missing_concepts: list[str] = field(default_factory=list)


@dataclass
class Ctx:
    topics: list[str]
    interview_type: str
    difficulty_mode: str
    current_level: int
    asked: list[AskedQ] = field(default_factory=list)
    history_texts: list[str] = field(default_factory=list)
    mastery: dict[str, float] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)
    focus_topics: list[str] = field(default_factory=list)
    skill_topics: list[str] = field(default_factory=list)
    remaining_seconds: float = 10_000
    remaining_questions: int = 10
    max_followups: int = 2
    seed: int = 0


@dataclass
class Decision:
    action: str  # followup | diagnostic | scenario | new_topic | finish
    topic: str | None
    level: int
    kind: str
    reason: str
    probe_concepts: list[str] = field(default_factory=list)
    new_current_level: int = 2


def clamp_level(x: int) -> int:
    return max(1, min(3, x))


def initial_level(mode: str, mastery: dict[str, float], attempts: dict[str, int], topics: list[str]) -> int:
    if mode in FIXED_LEVEL:
        return FIXED_LEVEL[mode]
    known = [mastery[t] for t in topics if attempts.get(t, 0) > 0 and t in mastery]
    if len(known) >= 2:
        avg = sum(known) / len(known)
        if avg >= 0.75:
            return 3
        if avg < 0.4:
            return 1
    return 2


def adjust_level(mode: str, level: int, last: AskedQ) -> int:
    """Only adaptive interviews move the global difficulty."""
    if mode != "adaptive":
        return FIXED_LEVEL.get(mode, level)
    if last.skipped:
        return clamp_level(level - 1)
    s = last.score if last.score is not None else 5
    if s >= 8 and last.hints_used == 0:
        return clamp_level(level + 1)
    if s <= 4:
        return clamp_level(level - 1)
    return level


def category(topic_id: str) -> str:
    return T[topic_id].category if topic_id in T else "technical"


def current_thread(asked: list[AskedQ]) -> list[AskedQ]:
    """Trailing questions that belong to the same topic as the last one."""
    if not asked:
        return []
    topic = asked[-1].topic
    out = []
    for a in reversed(asked):
        if a.topic != topic:
            break
        out.append(a)
    return list(reversed(out))


def level_for_topic(ctx: Ctx, topic: str, base: int) -> int:
    if ctx.difficulty_mode != "adaptive":
        return FIXED_LEVEL.get(ctx.difficulty_mode, base)
    m, n = ctx.mastery.get(topic), ctx.attempts.get(topic, 0)
    if m is not None and n > 0:
        if m >= 0.8:
            return clamp_level(base + 1)
        if m < 0.4:
            return clamp_level(base - 1)
    return base


def choose_topic(ctx: Ctx) -> str | None:
    if not ctx.topics:
        return None
    rng = random.Random(ctx.seed * 7919 + len(ctx.asked))
    covered = Counter(a.topic for a in ctx.asked)
    last_topic = ctx.asked[-1].topic if ctx.asked else None
    starts = [a for i, a in enumerate(ctx.asked) if i == 0 or ctx.asked[i - 1].topic != a.topic]
    cat_counts = Counter(category(a.topic) for a in starts)
    total_threads = max(1, len(starts))

    best, best_score = None, float("-inf")
    for t in ctx.topics:
        if t == last_topic and len(ctx.topics) > 1:
            continue
        s = 1.0
        s += 2.0 if covered[t] == 0 else -2.5 * covered[t]
        m = ctx.mastery.get(t)
        if t in ctx.focus_topics:  # weak topic from previous sessions -> targeted practice
            s += 1.5 + (1 - (m if m is not None else 0.5))
        if t in ctx.skill_topics:  # appears in resume / job description
            s += 1.0
        if m is not None and ctx.attempts.get(t, 0) >= 2 and m >= 0.85:
            s -= 0.5
        if ctx.interview_type == "mixed":
            cat = category(t)
            share = cat_counts[cat] / total_threads if ctx.asked else 0
            s += 3.0 * (MIX_TARGET.get(cat, 0.1) - share)
            if not ctx.asked:  # open a mixed interview with a technical or project question
                s += 1.0 if cat in ("technical", "project") else -1.0
        s += rng.random() * 0.3
        if s > best_score:
            best, best_score = t, s
    return best


def _new_topic(ctx: Ctx, level: int, reason: str) -> Decision:
    t = choose_topic(ctx)
    if t is None:
        return Decision("finish", None, level, "none", "No topics left", new_current_level=level)
    lvl = level_for_topic(ctx, t, level)
    why = reason
    if t in ctx.focus_topics:
        why += f" Next: {T[t].name}, a topic flagged for practice in your earlier sessions."
    elif t in ctx.skill_topics:
        why += f" Next: {T[t].name}, which appears in your resume / job description."
    return Decision("new_topic", t, lvl, KIND_FOR_CATEGORY.get(category(t), "core"), why.strip(),
                    new_current_level=level)


def decide_next(ctx: Ctx) -> Decision:
    level = ctx.current_level
    if ctx.remaining_questions <= 0:
        return Decision("finish", None, level, "none", "Question limit reached.", new_current_level=level)
    if ctx.remaining_seconds < 45:
        return Decision("finish", None, level, "none", "Interview time is up.", new_current_level=level)
    if not ctx.asked:
        return _new_topic(ctx, level, "Opening question.")

    last = ctx.asked[-1]
    new_level = adjust_level(ctx.difficulty_mode, level, last)
    thread = current_thread(ctx.asked)
    probes_used = len(thread) - 1
    can_probe = probes_used < ctx.max_followups and ctx.remaining_seconds > 90
    cat = category(last.topic)
    s = last.score if last.score is not None else 0
    verdict = last.verdict or ("correct" if s >= CORRECT_AT else "partial" if s >= PARTIAL_AT else "incorrect")

    def stay(action: str, kind: str, lvl: int, reason: str, probe: list[str] | None = None) -> Decision:
        return Decision(action, last.topic, clamp_level(lvl), kind, reason, probe or [], new_current_level=new_level)

    if last.skipped:
        return _new_topic(ctx, new_level, "Question skipped and recorded as a gap; moving on.")

    if verdict == "correct":
        if can_probe and probes_used == 0 and cat in ("technical", "coding", "project"):
            if cat == "coding":
                return stay("followup", "followup", last.level,
                            "Correct solution; probing optimisation and edge cases.",
                            ["optimisation", "edge cases"])
            nxt = last.level + 1 if ctx.difficulty_mode == "adaptive" else last.level
            return stay("scenario", "scenario", nxt, "Strong answer; raising the bar with a practical scenario.")
        return _new_topic(ctx, new_level, "Topic handled well.")

    if verdict == "partial":
        if can_probe and (last.missing_concepts or cat in ("hr", "project")):
            probe = last.missing_concepts[:2]
            return stay("followup", "followup", last.level,
                        "Partially correct; probing the missing parts: " + (", ".join(probe) or "more detail") + ".",
                        probe)
        return _new_topic(ctx, new_level, "Partial understanding noted.")

    # incorrect or off-topic
    already_diagnosed = any(a.kind == "diagnostic" for a in thread)
    if can_probe and not already_diagnosed and cat != "hr":
        return stay("diagnostic", "diagnostic", last.level - 1,
                    "Answer was incorrect or unclear; asking a simpler diagnostic question to find the gap.",
                    last.missing_concepts[:2])
    return _new_topic(ctx, new_level, "Knowledge gap recorded for your roadmap.")


def pick_bank_question(topic: str, level: int, session_ids: set[str], session_texts: list[str],
                       history_texts: list[str], prefer: str = "nearest") -> BankQuestion | None:
    """Best unused bank question for a topic. `prefer`: nearest | lower | higher (relative to level)."""
    tp = T.get(topic)
    if not tp:
        return None
    cands = [q for q in tp.questions if q.id not in session_ids and not is_repeat(q.text, session_texts)]
    if prefer == "lower":
        cands = [q for q in cands if q.level < level + 1]
    elif prefer == "higher":
        cands = [q for q in cands if q.level >= level]
    if not cands:
        return None

    def rank(q: BankQuestion):
        seen_before = 1 if is_repeat(q.text, history_texts, 0.75) else 0
        return (seen_before, abs(q.level - level), -q.level if prefer == "higher" else q.level)

    return sorted(cands, key=rank)[0]
