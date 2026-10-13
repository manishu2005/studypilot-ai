from dataclasses import asdict
from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.learning.course_graph import ConceptNode, CourseGraph, SourceReference
from app.service import StudyService, get_study_service

router = APIRouter(
    prefix="/api/learning-tools/course-graph",
    tags=["Course Graph"],
)

class SourceReferenceInput(BaseModel):
    source_id: str = Field(min_length=1)
    source_type: Literal["pdf", "pptx", "video"]
    page_number: int | None = None
    slide_number: int | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    quote: str | None = None

class ConceptNodeInput(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    level: Literal["topic", "subtopic", "concept"]
    mastery: float = Field(default=0.0, ge=0.0, le=1.0)
    prerequisites: list[str] = Field(default_factory=list)
    source_refs: list[SourceReferenceInput] = Field(default_factory=list)
    due_date: str | None = None
    estimated_minutes: int = Field(default=20, ge=1)

class CourseGraphRequest(BaseModel):
    nodes: list[ConceptNodeInput] = Field(min_length=1)

class StudyPlanRequest(CourseGraphRequest):
    today: date | None = None
    limit: int = Field(default=10, ge=1, le=100)
    max_minutes: int | None = Field(default=None, ge=1)
    mastery_threshold: float = Field(default=0.85, ge=0.0, le=1.0)

# Request model for generating from indexed materials
class GenerateGraphRequest(BaseModel):
    query: str = Field(default="", description="Search query or topic name to extract from")
    student_id: str = Field(default="default_student")


def create_graph(request: CourseGraphRequest) -> CourseGraph:
    nodes = []

    for item in request.nodes:
        source_refs = [
            SourceReference(**ref.model_dump())
            for ref in item.source_refs
        ]

        nodes.append(
            ConceptNode(
                id=item.id,
                title=item.title,
                level=item.level,
                mastery=item.mastery,
                prerequisites=item.prerequisites,
                source_refs=source_refs,
                due_date=item.due_date,
                estimated_minutes=item.estimated_minutes,
            )
        )

    try:
        return CourseGraph(nodes)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


# =============================================================================
# NEW GENERATION ENDPOINT
# =============================================================================
@router.post("/generate")
def generate_course_graph(
    request: GenerateGraphRequest,
    service: StudyService = Depends(get_study_service),
):
    # 1. Retrieve material using existing hybrid search
    query = request.query.strip() or "course curriculum key topics concepts"
    retrieved = service.search(query=query, top_k=10)

    if not retrieved:
        raise HTTPException(
            status_code=404,
            detail="No relevant indexed material found to build course graph.",
        )

    # Format chunks with source metadata
    material_context = "\n\n".join(
        f" (ID: {item['document_id']}), Page/Loc: {item.get('location_number', 1)}]\n{item['text']}"
        for item in retrieved
    )

    # 2. Extract graph via CourseGraph.from_material
    try:
        graph = CourseGraph.from_material(material_context)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Course graph generation failed: {exc}",
        ) from exc

    # 3. Synchronize existing learner mastery from SQLite
    for node in graph.nodes.values():
        profile = service.get_topic_mastery(request.student_id, node.title)
        node.mastery = float(profile.get("mastery", 0.0))

    validation = graph.validate()

    return {
        "valid": validation.valid,
        "errors": validation.errors,
        "topological_order": validation.topological_order,
        "nodes": [
            {
                "id": node.id,
                "title": node.title,
                "level": node.level,
                "mastery": node.mastery,
                "prerequisites": node.prerequisites,
                "estimated_minutes": node.estimated_minutes,
                "due_date": node.due_date,
                "source_refs": [asdict(r) for r in node.source_refs],
            }
            for node in graph.nodes.values()
        ],
    }


@router.post("/validate")
def validate_course_graph(request: CourseGraphRequest):
    graph = create_graph(request)
    result = graph.validate()

    return {
        "valid": result.valid,
        "errors": result.errors,
        "topological_order": result.topological_order,
        "node_count": len(graph.nodes),
    }


@router.post("/plan")
def create_study_plan(request: StudyPlanRequest):
    graph = create_graph(request)
    validation = graph.validate()

    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Course graph is invalid.",
                "errors": validation.errors,
            },
        )

    try:
        tasks = graph.build_study_plan(
            today=request.today,
            limit=request.limit,
            max_minutes=request.max_minutes,
            mastery_threshold=request.mastery_threshold,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "task_count": len(tasks),
        "total_estimated_minutes": sum(
            task.estimated_minutes for task in tasks
        ),
        "tasks": [
            {
                "node_id": task.node_id,
                "title": task.title,
                "level": task.level,
                "priority": task.priority,
                "mastery": task.mastery,
                "estimated_minutes": task.estimated_minutes,
                "reason": task.reason,
                "prerequisites": task.prerequisites,
                "source_refs": task.source_refs,
            }
            for task in tasks
        ],
    }