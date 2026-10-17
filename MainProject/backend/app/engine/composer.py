"""Turns a policy Decision into a concrete question without an LLM (demo mode and fallback).

Preference order: a fitting, unused bank question -> a bank question's own follow-up ->
a rotating follow-up template targeted at the missing concepts. Template ids are tracked per
session so the interviewer does not fall into a repetitive pattern.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .policy import Decision, pick_bank_question
from .question_bank import EXAMPLE, PROJECT, STAR, T, _c, get_bank_question
from .text_utils import is_repeat

WHY = _c("reasoning behind the choice", r"because|since|so that|reason|trade.?off|benefit")
ALTS = _c("alternatives considered", r"instead|alternative|compared|versus|\bvs\b|rather than|other option")
EDGE = _c("edge cases", r"edge|empty|null|none|negative|duplicate|large|overflow|zero|single")
OPT = _c("optimisation idea and its complexity", r"o\(|complexity|hash|cache|sort|index|precompute|reduce|avoid|faster")
TRADE = _c("trade-offs", r"trade.?off|downside|cost|risk|but|however|drawback")
FAIL = _c("what could go wrong", r"fail|break|risk|error|wrong|issue|problem|bottleneck|outage")
RESULT = _c("measurable result", r"result|outcome|reduc|improv|increas|\d+ ?%|deliver|saved")
LEARN = _c("what you learned / would change", r"learn|lesson|differently|next time|realis|realiz")


def cj(c) -> dict:
    return {"label": c.label, "patterns": list(c.patterns)}


PROJECT_C = [cj(c) for c in PROJECT[:2]]


@dataclass
class Composed:
    text: str
    concepts: list[dict]
    hint: str
    bank_id: str | None = None
    template_id: str | None = None
    ack: str = ""
    extras: dict = field(default_factory=dict)


ACKS = {
    "en": {"followup": ["Okay, let's go a bit deeper.", "Good, let me follow up on that.", "Thanks. One follow-up."],
           "scenario": ["Nice, that was solid. Let's make it practical.", "Good answer. Let's raise the bar."],
           "diagnostic": ["No problem, let's step back for a moment.", "Let's approach it from a simpler angle."],
           "new_topic": ["Let's move to a different area.", "Thanks. Switching topics now.", "Alright, next topic."]},
    "hi": {"followup": ["ठीक है, थोड़ा और गहराई में चलते हैं।", "अच्छा, इस पर एक फॉलो-अप सवाल।"],
           "scenario": ["बढ़िया जवाब। अब इसे व्यावहारिक बनाते हैं।", "अच्छा। अब थोड़ा कठिन सवाल।"],
           "diagnostic": ["कोई बात नहीं, एक आसान सवाल से समझते हैं।"],
           "new_topic": ["चलिए अब दूसरे विषय पर चलते हैं।", "ठीक है, अगला विषय।"]},
}


def ack_for(action: str, lang: str, n: int) -> str:
    opts = ACKS.get(lang, ACKS["en"]).get(action, [""])
    return opts[n % len(opts)]


def _concepts_by_label(labels: list[str], parent_bank_id: str | None, parent_concepts: list[dict]) -> list[dict]:
    pool = {c["label"]: c for c in parent_concepts or []}
    bq = get_bank_question(parent_bank_id)
    if bq:
        pool.update({c.label: cj(c) for c in bq.concepts})
    return [pool[l] for l in labels if l in pool]


def compose(decision: Decision, *, parent: dict | None, session_ids: set[str], session_texts: list[str],
            history_texts: list[str], used_templates: list[str], resume_skills: list[str]) -> Composed:
    """parent: {"text","bank_id","key_concepts","topic","kind"} of the question just answered."""
    topic = decision.topic
    tp = T.get(topic)

    if decision.action == "new_topic":
        bq = pick_bank_question(topic, decision.level, session_ids, session_texts, history_texts)
        if bq:
            text = bq.text
            # Project questions: anchor to a resume skill when we have one.
            if tp and tp.category == "project" and resume_skills:
                skill = resume_skills[len(session_ids) % len(resume_skills)]
                text = f"Your profile mentions {skill}. {text}"
            return Composed(text, [cj(c) for c in bq.concepts], bq.hint, bq.id)
        return Composed(
            f"Let's talk about {tp.name if tp else topic}. What's the most important concept here, and how have you applied it in practice?",
            [cj(EXAMPLE), cj(TRADE)], "Pick one concept you know well and explain it with a real example.")

    if decision.action == "diagnostic":
        bq = pick_bank_question(topic, decision.level, session_ids, session_texts, history_texts, prefer="lower")
        if bq:
            return Composed(bq.text, [cj(c) for c in bq.concepts], bq.hint, bq.id)
        # No simpler bank question left: ask for the fundamentals without naming the missing concept
        # (naming it would hand over the answer).
        concepts = _concepts_by_label(decision.probe_concepts[:2], parent and parent.get("bank_id"),
                                      parent and parent.get("key_concepts")) or [cj(EXAMPLE)]
        name = tp.name if tp else topic
        return Composed(f"Let's step back to basics on {name}. In simple terms, what problem does it solve, "
                        "and how would you explain the core idea to a junior colleague?",
                        concepts, "Start from a simple definition, then give one everyday example.",
                        template_id="diag_basics")

    if decision.action == "scenario":
        # Advanced bank questions are written as practical scenarios; below advanced, use the
        # practical template rather than a plain next-level definition question.
        if decision.level >= 3:
            bq = pick_bank_question(topic, 3, session_ids, session_texts, history_texts, prefer="higher")
            if bq and bq.level >= 3:
                return Composed(bq.text, [cj(c) for c in bq.concepts], bq.hint, bq.id)
        name = tp.name if tp else topic
        return Composed(
            f"Let's make it practical. Describe a real situation where {name} mattered in a system you built or used: "
            "what decision did you face, what trade-offs did you weigh, and what could go wrong?",
            [cj(EXAMPLE), cj(TRADE), cj(FAIL)],
            "Pick a concrete system (a project, an app you use) and reason about it step by step.",
            template_id="scenario_practical")

    # follow-up
    parent = parent or {}
    bq = get_bank_question(parent.get("bank_id"))
    if bq:
        for i, f in enumerate(bq.followups):
            tid = f"bank_fu:{bq.id}:{i}"
            if tid not in used_templates and not is_repeat(f, session_texts):
                concepts = _concepts_by_label(decision.probe_concepts, bq.id, parent.get("key_concepts")) \
                    or [cj(c) for c in bq.concepts]
                return Composed(f, concepts, bq.hint, template_id=tid)

    cat = tp.category if tp else "technical"
    probe = decision.probe_concepts
    probe_concepts = _concepts_by_label(probe, parent.get("bank_id"), parent.get("key_concepts"))
    templates: list[tuple[str, str, list[dict], str]] = []
    if cat == "coding":
        templates = [
            ("fu_optimize", "How would you optimise this solution further, and what is the complexity before and after?", [cj(OPT)], "Think about which repeated work could be avoided."),
            ("fu_edge", "What happens in edge cases, for example empty input, duplicates or very large input? How does your code handle them?", [cj(EDGE)], "List the unusual inputs first, then check each against your code."),
        ]
    elif cat == "hr":
        if any("result" in p for p in probe):
            templates.append(("fu_result", "What was the measurable result of that, and how did you know it worked?", [cj(RESULT)], "Numbers, feedback received or what changed afterwards."))
        if any("action" in p for p in probe):
            templates.append(("fu_actions", "What did you personally do, step by step? Focus on your own actions rather than the team's.", [cj(STAR[1])], "Use 'I' statements."))
        templates += [
            ("fu_learn", "Looking back, what would you do differently, and what did it teach you?", [cj(LEARN)], "Be honest; self-awareness matters more than a perfect story."),
            ("fu_result", "What was the outcome, and how did others respond?", [cj(RESULT)], "Describe what changed because of your actions."),
        ]
    elif cat == "project":
        templates = [
            ("fu_why", "Why did you choose that approach? What alternatives did you consider?", [cj(WHY), cj(ALTS)], "Name at least one option you rejected and why."),
            ("fu_project_measure", "How did you measure whether it worked, and what would you improve next?", [cj(RESULT), cj(TRADE)], "Metrics, user feedback, or performance numbers."),
        ]
    else:
        # Templates never name the missing concept (that would reveal the answer); the rubric
        # attached to the follow-up is what targets the gap.
        example_missing = any("example" in p.lower() for p in probe)
        deeper = [
            ("fu_deeper", "That's part of the picture. What else matters here? Walk me through how it works under the hood.", probe_concepts or [cj(EXAMPLE)], "Think about what happens internally, step by step."),
            ("fu_deeper_b", "Good start. If you had to explain this to a teammate debugging a real issue, what details would you add?", probe_concepts + [cj(EXAMPLE)], "Think about the details that matter when something goes wrong."),
        ]
        if example_missing:
            templates.append(("fu_example", "Can you explain that with a concrete example?", [cj(EXAMPLE)] + probe_concepts, "Use a small code snippet or a real situation."))
        if probe_concepts and not (example_missing and len(probe) == 1):
            templates += deeper
        templates += [
            ("fu_example", "Can you explain that with a concrete example?", [cj(EXAMPLE)] + probe_concepts, "Use a small code snippet or a real situation."),
            ("fu_why", "Why does it work that way? What problem does that design solve?", [cj(WHY)] + probe_concepts, "Think about the problem it solves."),
            ("fu_edge", "What happens in an edge case, or when it's used incorrectly?", [cj(EDGE), cj(FAIL)], "Think about unusual inputs or misuse."),
        ]
        if resume_skills:
            templates.append(("fu_project", "Can you describe how you've used this in one of your projects?", [cj(EXAMPLE)] + PROJECT_C, "Pick a project from your resume."))

    for tid, text, concepts, hint in templates:
        if tid not in used_templates and not is_repeat(text, session_texts):
            return Composed(text, concepts, hint, template_id=tid)
    # all templates used: generic but still targeted
    return Composed("Could you expand on that with more detail and one concrete example?",
                    [cj(EXAMPLE)] + probe_concepts, "Add one specific detail and one example.", template_id="fu_generic")
