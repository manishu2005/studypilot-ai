from app.diagnostic import DiagnosticEngine


def test_perfect_diagnostic():

    engine = DiagnosticEngine()

    result = engine.calculate_topic_result(
        topic="BFS",
        correct=5,
        total=5,
    )

    assert result.score == 1.0
    assert result.initial_mastery == 0.90


def test_zero_diagnostic():

    engine = DiagnosticEngine()

    result = engine.calculate_topic_result(
        topic="BFS",
        correct=0,
        total=5,
    )

    assert result.score == 0.0
    assert result.initial_mastery == 0.20


def test_partial_diagnostic():

    engine = DiagnosticEngine()

    result = engine.calculate_topic_result(
        topic="BFS",
        correct=3,
        total=5,
    )

    assert result.score == 0.6
    assert result.initial_mastery == 0.62
    