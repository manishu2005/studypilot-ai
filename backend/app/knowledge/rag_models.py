from pydantic import BaseModel, Field


class Citation(BaseModel):
    source: str
    source_type: str
    location_type: str
    location_start: float | int
    location_end: float | int
    label: str
    document_id: str
    chunk_index: int


class TutorModelResponse(BaseModel):
    grounded: bool = Field(
        description=(
            "True only if the supplied study material "
            "contains enough information to answer."
        )
    )

    answer: str = Field(
        description=(
            "Answer using only the supplied study material."
        )
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence between 0 and 1."
    )

    limitation: str = Field(
        description=(
            "Explain what is missing when the material "
            "does not sufficiently answer the question. "
            "Return an empty string when there is no limitation."
        )
    )


class TutorResponse(BaseModel):
    grounded: bool
    answer: str
    citations: list[Citation]
    confidence: float
    limitation: str