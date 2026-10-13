from datetime import date
import pytest

from app.course_graph import ConceptNode, CourseGraph, SourceReference

def node(node_id, title, *, mastery=0.0, prerequisites=None, due_date=None, minutes=20, source_refs=None):
    return ConceptNode(
        id=node_id,
        title=title,
        level="concept",
        mastery=mastery,
        prerequisites=prerequisites or [],
        due_date=due_date,
        estimated_minutes=minutes,
        source_refs=source_refs or [],
    )

def test_valid_graph_returns_prerequisite_first_order():
    graph = CourseGraph([
        node("circuits", "Circuits", prerequisites=["gates"]),
        node("gates", "Logic gates", prerequisites=["boolean"]),
        node("boolean", "Boolean algebra"),
    ])

    result = graph.validate()

    assert result.valid
    assert result.topological_order.index("boolean") < (
        result.topological_order.index("gates")
    )
    assert result.topological_order.index("gates") < (
        result.topological_order.index("circuits")
    )


def test_missing_prerequisite_is_rejected():
    graph = CourseGraph([
        node("gates", "Logic gates", prerequisites=["missing"]),
    ])

    result = graph.validate()

    assert not result.valid
    assert any("missing prerequisite" in error for error in result.errors)


def test_prerequisite_cycle_is_rejected():
    graph = CourseGraph([
        node("a", "Concept A", prerequisites=["b"]),
        node("b", "Concept B", prerequisites=["a"]),
    ])

    result = graph.validate()

    assert not result.valid
    assert any("cycle" in error.lower() for error in result.errors)


def test_duplicate_node_ids_are_rejected():
    with pytest.raises(ValueError, match="Duplicate node id"):
        CourseGraph([
            node("a", "First"),
            node("a", "Second"),
        ])


def test_invalid_mastery_is_rejected():
    graph = CourseGraph([
        node("a", "Concept A", mastery=1.2),
    ])

    result = graph.validate()

    assert not result.valid
    assert any("mastery" in error.lower() for error in result.errors)


def test_invalid_pdf_citation_is_rejected():
    graph = CourseGraph([
        node(
            "a",
            "Concept A",
            source_refs=[
                SourceReference(
                    source_id="lecture.pdf",
                    source_type="pdf",
                    page_number=0,
                )
            ],
        )
    ])

    result = graph.validate()

    assert not result.valid
    assert any("page_number" in error for error in result.errors)


def test_video_reference_keeps_timestamp():
    ref = SourceReference(
        source_id="lecture.mp4",
        source_type="video",
        start_seconds=80.0,
        end_seconds=95.0,
    )

    graph = CourseGraph([
        node("a", "Concept A", source_refs=[ref]),
    ])

    result = graph.validate()

    assert result.valid
    assert ref.start_seconds == 80.0
    assert ref.end_seconds == 95.0


def test_low_mastery_prerequisite_is_scheduled_first():
    graph = CourseGraph([
        node("circuits", "Circuits", prerequisites=["gates"], mastery=0.1),
        node("gates", "Logic gates", prerequisites=["boolean"], mastery=0.2),
        node("boolean", "Boolean algebra", mastery=0.3),
    ])

    plan = graph.build_study_plan(
        today=date(2026, 10, 12),
        limit=3,
    )

    ids = [task.node_id for task in plan]

    assert ids == ["boolean", "gates", "circuits"]


def test_mastered_prerequisite_does_not_need_scheduling():
    graph = CourseGraph([
        node("boolean", "Boolean algebra", mastery=0.95),
        node(
            "gates",
            "Logic gates",
            mastery=0.2,
            prerequisites=["boolean"],
        ),
    ])

    plan = graph.build_study_plan(limit=5)

    assert [task.node_id for task in plan] == ["gates"]


def test_overdue_topic_gets_higher_priority():
    graph = CourseGraph([
        node("regular", "Regular topic", mastery=0.3),
        node(
            "overdue",
            "Overdue topic",
            mastery=0.3,
            due_date="2026-10-01",
        ),
    ])

    plan = graph.build_study_plan(
        today=date(2026, 10, 12),
        limit=2,
    )

    assert plan[0].node_id == "overdue"
    assert "overdue review" in plan[0].reason


def test_study_plan_respects_time_budget():
    graph = CourseGraph([
        node("short", "Short topic", minutes=15),
        node("long", "Long topic", minutes=45),
    ])

    plan = graph.build_study_plan(
        limit=5,
        max_minutes=30,
    )

    assert sum(task.estimated_minutes for task in plan) <= 30
    assert [task.node_id for task in plan] == ["short"]


def test_plan_limit_is_respected():
    graph = CourseGraph([
        node("a", "A"),
        node("b", "B"),
        node("c", "C"),
    ])

    assert len(graph.build_study_plan(limit=2)) == 2


def test_invalid_graph_cannot_generate_a_plan():
    graph = CourseGraph([
        node("a", "A", prerequisites=["not-present"]),
    ])

    with pytest.raises(ValueError, match="invalid graph"):
        graph.build_study_plan()


def test_invalid_due_date_is_rejected():
    graph = CourseGraph([
        node("a", "A", due_date="12-10-2026"),
    ])

    result = graph.validate()

    assert not result.valid
    assert any("YYYY-MM-DD" in error for error in result.errors)
