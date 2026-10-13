from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.learning.learning_tools import build_revision_plan

router = APIRouter(
    prefix="/api/learning-tools",
    tags=["learning-tools"],
)

class TopicRecord(BaseModel):
    topic: str
    mastery: float = Field(default=0.0, ge=0.0, le=1.0)
    last_reviewed: Optional[date] = None
    next_review: Optional[date] = None

class RevisionPlanRequest(BaseModel):
    topic_records: list[TopicRecord]
    today: Optional[date] = None
    limit: int = Field(default=10, ge=0, le=100)

@router.post("/revision-plan")
def create_revision_plan(request: RevisionPlanRequest):
    try:
        records = [record.dict() for record in request.topic_records]

        plan = build_revision_plan(
            topic_records=records,
            today=request.today,
            limit=request.limit,
        )

        return {
            "count": len(plan),
            "revision_plan": plan,
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
