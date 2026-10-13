from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Iterable

DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}

def clamp_mastery(value: float) -> float:
    """Keep mastery within the valid 0.0-1.0 range."""
    return max(0.0, min(1.0, float(value)))

def expected_difficulty(mastery: float) -> str:
    """
    Deterministic baseline for evaluating adaptive difficulty.

    Low mastery: easy
    Moderate mastery: medium
    High mastery: hard
    """
    mastery = clamp_mastery(mastery)

    if mastery < 0.40:
        return "easy"
    if mastery < 0.70:
        return "medium"
    return "hard"

def expected_status(mastery: float) -> str:
    """Convert mastery to a learner-facing progress category."""
    mastery = clamp_mastery(mastery)

    if mastery < 0.40:
        return "weak"
    if mastery < 0.70:
        return "developing"
    if mastery < 0.85:
        return "proficient"
    return "mastered"

def normalize_question(text: str) -> str:
    """Normalize question wording for basic duplicate detection."""
    text = text.casefold().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def find_duplicate_questions(questions:Iterable[dict[str, Any]])->list[dict[str, Any]]:
    """
    Find exact normalized duplicates.

    Each question should contain a stable 'id' and a 'question' string.
    This does not detect every semantic duplicate; paraphrases require
    a semantic similarity model and should be checked separately.
    """
    seen: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []

    for item in questions:
        question_text = str(item.get("question", ""))
        normalized = normalize_question(question_text)

        if not normalized:
            continue

        if normalized in seen:
            duplicates.append(
                {
                    "duplicate_id": item.get("id"),
                    "original_id": seen[normalized].get("id"),
                    "normalized_question": normalized,
                }
            )
        else:
            seen[normalized] = item

    return duplicates

def select_weak_topics(topic_mastery:dict[str, float], limit:int = 3)->list[dict[str, Any]]:
    """Prioritize the lowest-mastery topics."""
    if limit < 0:
        raise ValueError("limit must be >= 0")

    rows = [
        {
            "topic": topic,
            "mastery": clamp_mastery(mastery),
            "status": expected_status(mastery),
            "recommended_difficulty": expected_difficulty(mastery),
        }
        for topic, mastery in topic_mastery.items()
    ]

    rows.sort(key=lambda row: (row["mastery"], row["topic"].casefold()))
    return rows[:limit]


@dataclass
class MasteryUpdate:
    topic: str
    previous_mastery: float
    updated_mastery: float
    is_correct: bool
    learning_rate: float

def update_mastery(topic:str, previous_mastery:float, is_correct:bool, learning_rate:float=0.20)->MasteryUpdate:
    """
    Apply a transparent exponential update.

    Correct answer: mastery moves toward 1.
    Incorrect answer: mastery moves toward 0.

    This is a simple baseline, not a calibrated psychometric model.
    """
    if not 0.0 < learning_rate <= 1.0:
        raise ValueError(
            "learning_rate must be greater than 0 and <= 1"
        )

    previous = clamp_mastery(previous_mastery)
    observed = 1.0 if is_correct else 0.0
    updated = previous + learning_rate * (observed - previous)

    return MasteryUpdate(
        topic=topic,
        previous_mastery=previous,
        updated_mastery=clamp_mastery(updated),
        is_correct=bool(is_correct),
        learning_rate=learning_rate,
    )


def evaluate_difficulty_alignment(records:Iterable[dict[str, Any]])->dict[str, Any]:
    """
    Compare the difficulty served by the application with the
    deterministic baseline expected from the learner's mastery.

    Each record requires mastery and served_difficulty.
    """
    total = 0
    matches = 0
    invalid = 0

    for record in records:
        total += 1
        mastery = record.get("mastery")
        served = str(record.get("served_difficulty", "")).lower()

        if mastery is None or served not in DIFFICULTY_ORDER:
            invalid += 1
            continue

        expected = expected_difficulty(float(mastery))
        if served == expected:
            matches += 1

    valid = total - invalid

    return {
        "total_records": total,
        "valid_records": valid,
        "invalid_records": invalid,
        "aligned_records": matches,
        "alignment_rate": matches / valid if valid else 0.0,
    }

def evaluate_topic_targeting(topic_mastery:dict[str, float], recommended_topics:Iterable[str], weak_threshold:float=0.40)->dict[str, Any]:
    """Measure whether recommendations include low-mastery topics."""
    recommended = list(recommended_topics)
    known = {
        topic: clamp_mastery(value)
        for topic, value in topic_mastery.items()
    }

    weak_topics = {
        topic for topic, mastery in known.items()
        if mastery < weak_threshold
    }
    known_recommended = [topic for topic in recommended if topic in known]
    weak_recommended = [
        topic for topic in known_recommended if topic in weak_topics
    ]

    return {
        "weak_topics": sorted(weak_topics),
        "recommended_topics": recommended,
        "known_recommendations": len(known_recommended),
        "weak_topics_recommended": len(weak_recommended),
        "weak_topic_recall": (
            len(weak_recommended) / len(weak_topics)
            if weak_topics else 1.0
        ),
        "recommendation_precision_for_weak_topics": (
            len(weak_recommended) / len(known_recommended)
            if known_recommended else 0.0
        ),
    }


def evaluate_question_repetition(questions:iterable[dict[str, Any]])->dict[str, Any]:
    """Summarize exact duplicate questions in a quiz dataset."""
    rows = list(questions)
    duplicates = find_duplicate_questions(rows)

    return {
        "question_count": len(rows),
        "duplicate_count": len(duplicates),
        "duplicate_rate": len(duplicates) / len(rows) if rows else 0.0,
        "duplicates": duplicates,
    }

def evaluate_personalization(difficulty_records:Iterable[dict[str, Any]], topic_mastery:dict[str, float], recommended_topics:Iterable[str], questions:Iterable[dict[str, Any]])->dict[str, Any]:
    """Build a deterministic evaluation report for personalization."""
    difficulty_records = list(difficulty_records)
    recommended_topics = list(recommended_topics)
    questions = list(questions)

    return {
        "difficulty_alignment": evaluate_difficulty_alignment(
            difficulty_records
        ),
        "topic_targeting": evaluate_topic_targeting(
            topic_mastery, recommended_topics
        ),
        "question_repetition": evaluate_question_repetition(questions),
    }

def report_to_dict(report: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-serializable report."""
    return report
