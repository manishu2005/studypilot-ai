from datetime import date
import pytest
from app.learning_tools import build_revision_plan, build_tutor_prompt, language_instruction

def test_supported_languages():
    assert "English" in language_instruction("en")
    assert "हिंदी" in language_instruction("hi")
    assert "Hinglish" in language_instruction("hinglish")

def test_unsupported_language_is_rejected():
    with pytest.raises(ValueError):
        language_instruction("fr")

def test_empty_question_is_rejected():
    with pytest.raises(ValueError):
        build_tutor_prompt("  ", "Some source context")

def test_prompt_preserves_source_context():
    prompt = build_tutor_prompt(
        question="Explain arrays",
        retrieved_context="[PDF: chapter.pdf, page 4] Arrays store elements.",
        language="en",
    )
    assert "page 4" in prompt
    assert "Arrays store elements" in prompt
    assert "Explain arrays" in prompt

def test_empty_context_instructs_tutor_not_to_guess():
    prompt = build_tutor_prompt("Explain this topic", "", "hi")
    assert "Do not guess" in prompt
    assert "उत्तर हिंदी में दें" in prompt

def test_low_mastery_topic_is_prioritized():
    plan = build_revision_plan(
        [
            {"topic": "Trees", "mastery": 0.85},
            {"topic": "Arrays", "mastery": 0.20},
        ],
        today=date(2026, 10, 11),
    )
    assert plan[0]["topic"] == "Arrays"
    assert plan[0]["priority"] == "high"

def test_overdue_topic_is_marked_due():
    plan = build_revision_plan(
        [
            {
                "topic": "Graphs",
                "mastery": 0.55,
                "next_review": "2026-10-05",
            }
        ],
        today=date(2026, 10, 11),
    )
    assert plan[0]["due"] is True


def test_future_review_is_not_due():
    plan = build_revision_plan(
        [
            {
                "topic": "Trees",
                "mastery": 0.85,
                "next_review": "2026-10-18",
            }
        ],
        today=date(2026, 10, 11),
    )
    assert plan[0]["due"] is False


def test_revision_plan_limit():
    plan = build_revision_plan(
        [
            {"topic": "Arrays", "mastery": 0.20},
            {"topic": "Trees", "mastery": 0.30},
            {"topic": "Graphs", "mastery": 0.50},
        ],
        today=date(2026, 10, 11),
        limit=2,
    )
    assert len(plan) == 2


def test_negative_limit_is_rejected():
    with pytest.raises(ValueError):
        build_revision_plan([], limit=-1)


def test_invalid_mastery_is_clamped():
    plan = build_revision_plan(
        [{"topic": "Arrays", "mastery": 1.5}],
        today=date(2026, 10, 11),
    )
    assert plan[0]["mastery"] == 1.0
