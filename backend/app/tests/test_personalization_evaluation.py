
import pytest

from app.personalization_evaluation import (
    expected_difficulty,
    expected_status,
    evaluate_difficulty_alignment,
    evaluate_personalization,
    evaluate_topic_targeting,
    find_duplicate_questions,
    select_weak_topics,
    update_mastery,
)


def test_difficulty_bands():
    assert expected_difficulty(0.20) == "easy"
    assert expected_difficulty(0.40) == "medium"
    assert expected_difficulty(0.69) == "medium"
    assert expected_difficulty(0.70) == "hard"


def test_mastery_status_bands():
    assert expected_status(0.20) == "weak"
    assert expected_status(0.50) == "developing"
    assert expected_status(0.75) == "proficient"
    assert expected_status(0.90) == "mastered"


def test_mastery_is_clamped():
    assert expected_difficulty(-1.0) == "easy"
    assert expected_difficulty(2.0) == "hard"


def test_correct_answer_increases_mastery():
    result = update_mastery("Arrays", 0.50, True)
    assert result.updated_mastery == pytest.approx(0.60)


def test_incorrect_answer_decreases_mastery():
    result = update_mastery("Arrays", 0.50, False)
    assert result.updated_mastery == pytest.approx(0.40)


def test_mastery_learning_rate_validation():
    with pytest.raises(ValueError):
        update_mastery("Arrays", 0.50, True, learning_rate=0)


def test_weak_topics_are_prioritized():
    result = select_weak_topics(
        {"Trees": 0.90, "Arrays": 0.20, "Graphs": 0.30},
        limit=2,
    )
    assert [item["topic"] for item in result] == ["Arrays", "Graphs"]


def test_duplicate_questions_are_detected():
    questions = [
        {"id": "1", "question": "What is a stack?"},
        {"id": "2", "question": "  WHAT is a stack? "},
        {"id": "3", "question": "What is a queue?"},
    ]
    duplicates = find_duplicate_questions(questions)
    assert len(duplicates) == 1
    assert duplicates[0]["duplicate_id"] == "2"
    assert duplicates[0]["original_id"] == "1"


def test_difficulty_alignment_metric():
    result = evaluate_difficulty_alignment([
        {"mastery": 0.20, "served_difficulty": "easy"},
        {"mastery": 0.90, "served_difficulty": "easy"},
        {"mastery": 0.50, "served_difficulty": "medium"},
    ])
    assert result["valid_records"] == 3
    assert result["aligned_records"] == 2
    assert result["alignment_rate"] == pytest.approx(2 / 3)


def test_invalid_difficulty_record_is_counted():
    result = evaluate_difficulty_alignment([
        {"mastery": 0.20, "served_difficulty": "impossible"},
        {"served_difficulty": "easy"},
    ])
    assert result["invalid_records"] == 2
    assert result["valid_records"] == 0


def test_weak_topic_targeting():
    result = evaluate_topic_targeting(
        {"Arrays": 0.20, "Trees": 0.90, "Graphs": 0.30},
        ["Arrays", "Trees"],
    )
    assert result["weak_topics_recommended"] == 1
    assert result["weak_topic_recall"] == pytest.approx(0.5)


def test_full_personalization_report():
    report = evaluate_personalization(
        difficulty_records=[
            {"mastery": 0.20, "served_difficulty": "easy"}
        ],
        topic_mastery={"Arrays": 0.20},
        recommended_topics=["Arrays"],
        questions=[
            {"id": "a", "question": "What is an array?"},
            {"id": "b", "question": "What is an array?"},
        ],
    )
    assert report["difficulty_alignment"]["alignment_rate"] == 1.0
    assert report["topic_targeting"]["weak_topic_recall"] == 1.0
    assert report["question_repetition"]["duplicate_count"] == 1
