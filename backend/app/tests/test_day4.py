from app.schemas import (
    DiagramAnalysis,
    TopicAnalysis,
)


def test_topic_schema():

    result = TopicAnalysis(
        topic="Graph Traversal",
        subtopics=[
            "BFS",
            "DFS",
        ],
        concepts=[],
        prerequisites=[
            "Graph",
        ],
        keywords=[
            "queue",
            "stack",
        ],
    )

    assert result.topic == "Graph Traversal"

    assert "BFS" in result.subtopics

    assert "Graph" in result.prerequisites


def test_diagram_schema():

    result = DiagramAnalysis(
        diagram_type="flowchart",
        title="BFS",
        description=(
            "Shows BFS traversal through a graph."
        ),
        components=[
            "Queue",
            "Graph",
        ],
        relationships=[
            "Queue processes vertices."
        ],
        concepts=[
            "BFS",
            "Graph traversal",
        ],
        educational_value=(
            "Demonstrates level-order traversal."
        ),
    )

    assert result.diagram_type == "flowchart"

    assert "BFS" in result.concepts

    assert len(result.components) == 2