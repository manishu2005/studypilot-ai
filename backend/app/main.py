from pathlib import Path
import sqlite3
import traceback

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import settings
from app.service import StudyService, get_study_service
from app.video.video_storage import is_supported_video
from app.knowledge.rag_models import TutorResponse
from app.quiz.quiz_generator import QuizGenerator
from app.dashboard.dashboard import DashboardService
from app.learning.learner_model import LearnerModel
from app.assessment.diagnostic import DiagnosticEngine
from app.api.routes import router as learning_tools_router
from app.learning.graph_routes import router as graph_router
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.service import get_study_service
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_study_service()
    yield


app = FastAPI(
    title="AI-Study_Companion",
    description=(
        "An AI-powered study companion that helps you "
        "understand and learn from your documents."
    ),
    version="1.0.0",
    lifespan=lifespan
    
)
app.include_router(learning_tools_router)
app.include_router(graph_router)


DEFAULT_STUDENT_ID="default_student"

# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class SearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=1000,
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )


class TutorRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2000,
    )

    top_k: int = Field(
        default=8,
        ge=1,
        le=15,
    )

class QuizRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    number_of_questions: int =Field(default=5, ge=1, le=20)
    question_type: str = Field(default="mcq")
    difficulty: str = Field(default="medium")

class DiagnosticResultRequest(BaseModel):
    topic: str
    total: int = Field(ge=1)
    correct: int = Field(ge=0) 
# ============================================================
# SERVICE DEPENDENCY
# ============================================================

def get_service() -> StudyService:
    return get_study_service()


# ============================================================
# BASIC ENDPOINTS
# ============================================================

@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


# ============================================================
# DOCUMENT LIST
# ============================================================

@app.get("/api/documents")
def list_documents(
    service: StudyService = Depends(get_service),
):
    return {
        "documents": service.list_documents(),
    }


# ============================================================
# DOCUMENT UPLOAD
# ============================================================

@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    service: StudyService = Depends(get_service),
):

    filename = Path(file.filename or "").name

    supported_document = (
        filename.lower().endswith(".pdf")
        or filename.lower().endswith(".pptx")
        or is_supported_video(filename)
    )

    if not supported_document:
        raise HTTPException(
            status_code=415,
            detail=(
                "Supported files are PDF, PPTX, "
                "MP4, MOV, MKV, WEBM, AVI and M4V."
            ),
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024

    data = await file.read(max_bytes + 1)

    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail="File exceeds the configured upload limit.",
        )

    if not data:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    try:

        return service.ingest_document(
            filename,
            data,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Document processing failed: {exc}",
        ) from exc

    finally:

        await file.close()


# ============================================================
# SEARCH
# ============================================================

@app.post("/api/search")
def search_documents(
    request: SearchRequest,
    service: StudyService = Depends(get_service),
):

    try:

        matches = service.search(
            request.query,
            request.top_k,
        )

        return {
            "query": request.query,
            "matches": matches,
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {exc}",
        ) from exc


# ============================================================
# GET SINGLE DOCUMENT
# ============================================================

@app.get("/api/documents/{document_id}")
def get_document(
    document_id: str,
    service: StudyService = Depends(get_service),
):

    details = service.get_document_details(document_id)
    if not details:
        raise HTTPException(
            status_code=404,
            detail=f"Document with ID {document_id} was not found.",
        )
    return details


# ============================================================
# KNOWLEDGE ANALYSIS
# ============================================================

@app.post("/api/knowledge/analyze/{document_id}")
def analyze_document_knowledge(
    document_id: str,
    service: StudyService = Depends(get_service),
):

    document = next(
        (
            item
            for item in service.list_documents()
            if item["id"] == document_id
        ),
        None,
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return {
        "document_id": document_id,
        "status": "analysis_started",
    }


# ============================================================
# VIDEO TRANSCRIPT
# ============================================================

@app.get("/api/documents/{document_id}/transcript")
def get_video_transcript(
    document_id: str,
    service: StudyService = Depends(get_service),
):

    with sqlite3.connect(service.database_path) as connection:

        connection.row_factory = sqlite3.Row

        video = connection.execute(
            """
            SELECT
                duration_seconds,
                language,
                language_probability
            FROM videos
            WHERE document_id = ?
            """,
            (document_id,),
        ).fetchone()

        if video is None:
            raise HTTPException(
                status_code=404,
                detail="Video transcript not found.",
            )

        rows = connection.execute(
            """
            SELECT
                segment_index,
                start_seconds,
                end_seconds,
                text
            FROM video_transcript_segments
            WHERE document_id = ?
            ORDER BY segment_index
            """,
            (document_id,),
        ).fetchall()

    return {
        "document_id": document_id,
        "duration_seconds": video["duration_seconds"],
        "language": video["language"],
        "language_probability": video["language_probability"],
        "segments": [
            dict(row)
            for row in rows
        ],
    }


# ============================================================
# SINGLE VIDEO TRANSCRIPT SEGMENT
# ============================================================

@app.get(
    "/api/documents/{document_id}/transcript/{segment_index}"
)
def get_video_segment(
    document_id: str,
    segment_index: int,
    service: StudyService = Depends(get_service),
):

    with sqlite3.connect(service.database_path) as connection:

        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT
                segment_index,
                start_seconds,
                end_seconds,
                text
            FROM video_transcript_segments
            WHERE document_id = ?
              AND segment_index = ?
            """,
            (
                document_id,
                segment_index,
            ),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Transcript segment not found.",
        )

    return dict(row)


# ============================================================
# AI TUTOR / RAG
# ============================================================

@app.post("/api/tutor",response_model=TutorResponse,)
def tutor(
    request: TutorRequest,
    service: StudyService = Depends(get_service),
):

    try:

        result = service.get_rag_service().answer(
            question=request.question,
            top_k=request.top_k,
        )

        return result

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Tutor request failed.",
        )

@app.post("/api/quiz/generate")
def generate_quiz(request:QuizRequest, service: StudyService=Depends(get_service)):
    try:
        print("--- [DEBUG] STEP 1: Starting search ---")
        retrieved = service.search(request.query, top_k=10)
        print(f"--- [DEBUG] STEP 2: Search finished, found {len(retrieved)} items ---")
        if not retrieved:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No relevant study material was found."
                ),
            )

        context = "\n\n".join(
            item["text"]
            for item in retrieved
        )
        logger.info("Quiz generation started.")

        generator = QuizGenerator()
        print("--- [DEBUG] STEP 3: Calling QuizGenerator ---")
        # topic_mastery = service.get_topic_mastery(
        #     DEFAULT_STUDENT_ID, request.query
        # )

        difficulty = getattr(request, "difficulty", "medium")

        quiz = generator.generate(
            context=context,
            number_of_questions=request.number_of_questions,
            question_type=request.question_type,
            difficulty=difficulty,
        )
        logger.info("Quiz generation completed.")
        return quiz

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Quiz generation failed: {exc}",
        ) from exc

@app.get("/api/learner/mastery")
def learner_mastery(service: StudyService = Depends(get_service)):
    return {
        "student_id": DEFAULT_STUDENT_ID,
        "topics": service.get_learner_profile(DEFAULT_STUDENT_ID),
    }

@app.get("/api/learner/mastery/{topic}")
def topic_mastery(topic:str, service: StudyService=Depends(get_service)):
    return service.get_topic_mastery(
        DEFAULT_STUDENT_ID,
        topic,
    )

@app.post("/api/learner/diagnostic/result")
def diagnostic_result(
    request: DiagnosticResultRequest,
    service: StudyService = Depends(get_service),
):
    engine = DiagnosticEngine()

    result = engine.calculate_topic_result(
        topic=request.topic,
        correct=request.correct,
        total=request.total,
    )

    return {
        "topic": result.topic,
        "total": result.total,
        "correct": result.correct,
        "score": result.score,
        "initial_mastery": result.initial_mastery,
        "status": LearnerModel.status(
            result.initial_mastery
        ),
    }

@app.get("/api/learner/dashboard")
def learner_dashboard(service:StudyService = Depends(get_service)):
    topics=service.get_learner_profile(DEFAULT_STUDENT_ID)
    dashboard = DashboardService()
    return dashboard.build(topics)

@app.get("/api/documents/{document_id}/diagrams")
def get_document_diagrams_endpoint(
    document_id: str,
    service: StudyService = Depends(get_study_service),  # use get_service if defined that way in main.py
):
    diagrams = service.get_document_diagrams(document_id)
    # Always return 200 OK with the diagrams list (even if empty [])
    return {
        "document_id": document_id,
        "diagrams": diagrams
    }