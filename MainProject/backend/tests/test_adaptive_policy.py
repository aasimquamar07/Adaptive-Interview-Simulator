"""Adaptive question selection: follow-ups, difficulty changes, loop limits, topic scheduling."""
from app.engine.policy import AskedQ, Ctx, choose_topic, decide_next, initial_level, pick_bank_question
from app.engine.question_bank import CODING_TOPICS, HR_TOPICS, ROLE_TOPICS, T, topics_for
from app.engine.text_utils import extract_skills, is_repeat, topics_for_skills

JAVA = ROLE_TOPICS["java_developer"]


def ctx(asked, **kw):
    base = dict(topics=JAVA, interview_type="technical", difficulty_mode="adaptive", current_level=2,
                asked=asked, remaining_questions=10, remaining_seconds=900)
    base.update(kw)
    return Ctx(**base)


def q(topic="java_oop", level=2, kind="core", score=None, verdict=None, skipped=False, missing=None, hints=0):
    return AskedQ(topic=topic, level=level, kind=kind, text=f"{topic} {kind} {level} {score}", score=score,
                  verdict=verdict, skipped=skipped, missing_concepts=missing or [], hints_used=hints)


def test_correct_answer_raises_difficulty_with_scenario_on_same_topic():
    d = decide_next(ctx([q(score=9, verdict="correct")]))
    assert d.action == "scenario" and d.topic == "java_oop"
    assert d.level == 3 and d.new_current_level == 3


def test_partial_answer_gets_targeted_followup():
    d = decide_next(ctx([q(score=5.5, verdict="partial", missing=["runtime polymorphism", "example"])]))
    assert d.action == "followup" and d.topic == "java_oop"
    assert d.probe_concepts == ["runtime polymorphism", "example"]


def test_incorrect_answer_gets_simpler_diagnostic_then_moves_on():
    d = decide_next(ctx([q(score=2, verdict="incorrect", missing=["x"])]))
    assert d.action == "diagnostic" and d.topic == "java_oop" and d.level == 1 and d.new_current_level == 1
    d2 = decide_next(ctx([q(score=2, verdict="incorrect"), q(level=1, kind="diagnostic", score=2, verdict="incorrect")],
                         current_level=1))
    assert d2.action == "new_topic" and d2.topic != "java_oop"


def test_followups_are_capped_no_infinite_loop():
    thread = [q(score=5, verdict="partial", missing=["a"]),
              q(kind="followup", score=5, verdict="partial", missing=["a"]),
              q(kind="followup", score=5, verdict="partial", missing=["a"])]
    d = decide_next(ctx(thread, max_followups=2))
    assert d.action == "new_topic" and d.topic != "java_oop"


def test_long_session_never_exceeds_followup_cap():
    asked = []
    for _ in range(20):
        d = decide_next(ctx(asked, max_followups=2, remaining_questions=20 - len(asked)))
        if d.action == "finish":
            break
        asked.append(q(topic=d.topic, level=d.level, kind=d.kind, score=5, verdict="partial", missing=["gap"]))
    run, longest = 1, 1
    for a, b in zip(asked, asked[1:]):
        run = run + 1 if a.topic == b.topic else 1
        longest = max(longest, run)
    assert longest <= 3  # one core question + at most two follow-ups


def test_skip_moves_on_and_lowers_adaptive_level():
    d = decide_next(ctx([q(skipped=True)]))
    assert d.action == "new_topic" and d.topic != "java_oop" and d.new_current_level == 1


def test_fixed_difficulty_never_changes_level():
    d = decide_next(ctx([q(level=1, score=10, verdict="correct")], difficulty_mode="beginner", current_level=1))
    assert d.level == 1 and d.new_current_level == 1


def test_limits_finish_the_interview():
    assert decide_next(ctx([q(score=8, verdict="correct")], remaining_questions=0)).action == "finish"
    assert decide_next(ctx([q(score=8, verdict="correct")], remaining_seconds=20)).action == "finish"


def test_weak_history_topics_are_scheduled_first():
    c = ctx([], focus_topics=["java_jvm"], mastery={"java_jvm": 0.2}, attempts={"java_jvm": 3})
    assert choose_topic(c) == "java_jvm"


def test_resume_or_jd_skills_steer_topic_choice():
    skills = extract_skills("Built REST microservices with Spring Boot and PostgreSQL")
    assert "Spring Boot" in skills and "SQL" in skills
    st = topics_for_skills(skills, JAVA)
    assert "spring_boot" in st
    assert choose_topic(ctx([], skill_topics=["spring_boot"])) == "spring_boot"


def test_strong_history_starts_adaptive_interviews_harder():
    m = {t: 0.9 for t in JAVA[:3]}
    a = {t: 3 for t in JAVA[:3]}
    assert initial_level("adaptive", m, a, JAVA) == 3
    assert initial_level("adaptive", {t: 0.2 for t in JAVA[:3]}, a, JAVA) == 1
    assert initial_level("advanced", {}, {}, JAVA) == 3


def test_topics_are_not_repeated_back_to_back_and_coverage_is_spread():
    asked = []
    for _ in range(6):
        t = choose_topic(ctx(asked))
        assert not asked or t != asked[-1].topic
        asked.append(q(topic=t, score=8, verdict="correct"))
    assert len({a.topic for a in asked}) == 6


def test_mixed_interview_covers_several_categories():
    topics = topics_for("python_developer", "mixed")
    asked = []
    for _ in range(8):
        t = choose_topic(ctx(asked, topics=topics, interview_type="mixed"))
        asked.append(q(topic=t, score=8, verdict="correct"))
    cats = {T[a.topic].category for a in asked}
    assert {"technical", "coding"} <= cats and len(cats) >= 3


def test_interview_type_selects_topic_pool():
    assert topics_for("java_developer", "hr") == HR_TOPICS
    assert topics_for("java_developer", "coding") == CODING_TOPICS
    custom = topics_for("custom", "technical", "React Native frontend engineer")
    assert "react" in custom


def test_bank_never_repeats_a_question_within_a_session():
    first = pick_bank_question("java_collections", 2, set(), [], [])
    second = pick_bank_question("java_collections", 2, {first.id}, [first.text], [])
    assert second is not None and second.id != first.id


def test_bank_prefers_questions_not_seen_in_previous_sessions():
    seen = pick_bank_question("sql", 2, set(), [], [])
    other = pick_bank_question("sql", 2, set(), [], [seen.text])
    assert other.text != seen.text


def test_repeat_detection_catches_rephrasing():
    assert is_repeat("What is polymorphism in Java?", ["what is polymorphism in java"])
    assert is_repeat("Explain how HashMap works internally in Java.", ["How does HashMap work internally in Java?"])
    assert not is_repeat("What is a database index?", ["What is polymorphism in Java?"])
