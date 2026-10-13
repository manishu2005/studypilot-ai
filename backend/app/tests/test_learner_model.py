from app.learner_model import LearnerModel


def test_correct_answer_increases_mastery():

    model = LearnerModel()

    updated = model.update(
        current_mastery=0.50,
        correct=True,
        score=1.0,
    )

    assert updated > 0.50
    assert updated <= 1.0


def test_wrong_answer_decreases_mastery():

    model = LearnerModel()

    updated = model.update(
        current_mastery=0.70,
        correct=False,
        score=0.0,
    )

    assert updated < 0.70
    assert updated >= 0.0


def test_mastery_status():

    model = LearnerModel()

    assert model.status(0.20) == "weak"
    assert model.status(0.50) == "developing"
    assert model.status(0.75) == "proficient"
    assert model.status(0.90) == "strong"


def test_adaptive_difficulty():

    model = LearnerModel()

    assert model.recommended_difficulty(0.20) == "easy"
    assert model.recommended_difficulty(0.55) == "medium"
    assert model.recommended_difficulty(0.90) == "hard"