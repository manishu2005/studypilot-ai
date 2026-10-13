import hashlib
import json
import sqlite3
import uuid

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import chromadb
from chromadb.config import Settings
from PIL import Image
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.knowledge.ingestion import extract_document
from app.learning.learner_model import LearnerModel
from app.knowledge.rag_service import RAGService
from app.knowledge.retrieval import HybridRetriever
from app.video.video_service import VideoIngestionService
from app.video.video_storage import is_supported_video


class StudyService:
    def __init__(
        self,
        database_path: str | None = None,
        chroma_path: str | None = None,
        embedding_model: str | None = None,
    ):
        self.database_path = database_path or settings.database_path
        self.chroma_path = chroma_path or settings.chroma_path
        self.embedding_model = embedding_model or settings.embedding_model

        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.chroma_path).parent.mkdir(parents=True, exist_ok=True)

        self._initialize_database()

        self._client = chromadb.PersistentClient(
            path=self.chroma_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
                is_persistent=True,
            ),
        )

        self._collection = self._client.get_or_create_collection(
            name="study_companion",
            metadata={"hnsw:space": "cosine"},
        )
        self._model = None
        self._rag_service = None

    def _initialize_database(self):
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    page_count INTEGER NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    pages_needing_ocr TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS topics (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    UNIQUE(document_id, name),
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS concepts (
                    id TEXT PRIMARY KEY,
                    topic_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    explanation TEXT,
                    FOREIGN KEY(topic_id) REFERENCES topics(id)
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS content_units (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    topic_id TEXT,
                    source_type TEXT NOT NULL,
                    location_number INTEGER NOT NULL,
                    chunk_index INTEGER,
                    text TEXT,
                    content_type TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id),
                    FOREIGN KEY(topic_id) REFERENCES topics(id)
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS diagrams (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    content_unit_id TEXT,
                    source_type TEXT NOT NULL,
                    location_number INTEGER NOT NULL,
                    image_index INTEGER NOT NULL,
                    extension TEXT NOT NULL,
                    width INTEGER,
                    height INTEGER,
                    diagram_type TEXT,
                    title TEXT,
                    description TEXT,
                    educational_value TEXT,
                    FOREIGN KEY(document_id) REFERENCES documents(id),
                    FOREIGN KEY(content_unit_id) REFERENCES content_units(id)
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS prerequisites (
                    id TEXT PRIMARY KEY,
                    topic_id TEXT NOT NULL,
                    prerequisite_name TEXT NOT NULL,
                    FOREIGN KEY(topic_id) REFERENCES topics(id)
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL UNIQUE,
                    duration_seconds REAL NOT NULL,
                    language TEXT,
                    language_probability REAL,
                    transcript_segment_count INTEGER NOT NULL,
                    video_path TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS video_transcript_segments (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    segment_index INTEGER NOT NULL,
                    start_seconds REAL NOT NULL,
                    end_seconds REAL NOT NULL,
                    text TEXT NOT NULL,
                    avg_logprob REAL,
                    no_speech_probability REAL,
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS video_chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    start_seconds REAL NOT NULL,
                    end_seconds REAL NOT NULL,
                    text TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS quiz_questions (
                    id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    question_type TEXT NOT NULL,
                    options_json TEXT NOT NULL,
                    correct_answer TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    document_id TEXT,
                    chunk_index INTEGER,
                    created_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id TEXT PRIMARY KEY,
                    question_id TEXT NOT NULL,
                    student_answer TEXT NOT NULL,
                    correct INTEGER NOT NULL,
                    score REAL NOT NULL,
                    feedback TEXT NOT NULL,
                    misconception TEXT NOT NULL,
                    attempted_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS learner_topic_mastery (
                    student_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    mastery REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    correct INTEGER NOT NULL DEFAULT 0,
                    incorrect INTEGER NOT NULL DEFAULT 0,
                    last_score REAL NOT NULL DEFAULT 0.0,
                    streak INTEGER NOT NULL DEFAULT 0,
                    misconceptions TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (student_id, topic)
                )
                """
            )

    def _get_model(self):
        if self._model is None:
            self._model = SentenceTransformer(self.embedding_model)
        return self._model

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._get_model().encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vectors.tolist()

    def _find_document_by_hash(self, checksum: str) -> dict | None:
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT id, filename, page_count, chunk_count, status, pages_needing_ocr
                FROM documents
                WHERE sha256 = ?
                """,
                (checksum,),
            ).fetchone()

        if row is None:
            return None

        result = dict(row)
        raw_pages = result.pop("pages_needing_ocr")
        result["pages_needing_ocr"] = [
            int(page)
            for page in raw_pages.split(",")
            if page
        ]
        return result

    def ingest_document(self, filename: str, data: bytes) -> dict:
        if is_supported_video(filename):
            return self.ingest_video(filename, data)

        checksum = hashlib.sha256(data).hexdigest()
        existing = self._find_document_by_hash(checksum)

        if existing:
            return {
                "document_id": existing["id"],
                "filename": existing["filename"],
                "status": "duplicate",
                "chunk_count": existing["chunk_count"],
                "page_count": existing["page_count"],
                "pages_needing_ocr": existing["pages_needing_ocr"],
                "message": "This document has already been indexed.",
            }

        extraction = extract_document(filename, data)
        chunks = extraction.chunks
        pages_needing_ocr = extraction.pages_needing_ocr
        page_count = extraction.page_count

        if not chunks:
            raise ValueError("The PDF contains no extractable text")

        document_id = str(uuid.uuid4())
        texts = [chunk.text for chunk in chunks]
        embeddings = self._embed(texts)

        ids = [
            f"{document_id}_{chunk.chunk_index}_{index}"
            for index, chunk in enumerate(chunks)
        ]

        metadatas = []
        for chunk in chunks:
            metadatas.append(
                {
                    "document_id": document_id,
                    "source_name": filename,
                    "source_type": chunk.source_type,
                    "location_number": (
                        chunk.location_number
                        if hasattr(chunk, "location_number")
                        else chunk.page_number
                    ),
                    "chunk_index": chunk.chunk_index,
                    "sha256": checksum,
                }
            )

        self._collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO documents (
                    id, filename, sha256, page_count, chunk_count, status, pages_needing_ocr
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    filename,
                    checksum,
                    page_count,
                    len(chunks),
                    "ready",
                    ",".join(map(str, pages_needing_ocr)),
                ),
            )

            # Persist content units for retrieval:
            chunk_records = [
                (
                    f"{document_id}_{chunk.chunk_index}_{i}",
                    document_id,
                    getattr(chunk, "topic_id", None),
                    chunk.source_type,
                    getattr(chunk, "location_number", getattr(chunk, "page_number", 1)),
                    chunk.chunk_index,
                    chunk.text,
                    "text",
                )
                for i, chunk in enumerate(chunks)
            ]
            connection.executemany(
                """
                INSERT OR IGNORE INTO content_units (
                    id, document_id, topic_id, source_type, location_number, chunk_index, text, content_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                chunk_records,
            )
            

        return {
            "document_id": document_id,
            "filename": filename,
            "status": "ready",
            "page_count": page_count,
            "chunk_count": len(chunks),
            "pages_needing_ocr": pages_needing_ocr,
        }

    def list_documents(self) -> list[dict]:
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, filename, sha256, page_count, chunk_count, status, pages_needing_ocr
                FROM documents 
                ORDER BY rowid DESC
                """
            )
        result = []
        for row in rows:
            item = dict(row)
            raw_pages = item.pop("pages_needing_ocr")
            item["pages_needing_ocr"] = [
                int(x) for x in raw_pages.split(",") if x
            ]
            result.append(item)
        return result

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        query = query.strip()
        if not query:
            raise ValueError("Search query cannot be empty.")
        if top_k < 1 or top_k > 20:
            raise ValueError("top_k must be between 1 and 20.")

        if self._collection.count() == 0:
            return []

        query_embedding = self._embed([query])[0]
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        matches = []
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for text, metadata, distance in zip(documents, metadatas, distances):
            match = {
                "text": text,
                "source": metadata["source_name"],
                "document_id": metadata["document_id"],
                "location_number": metadata.get(
                    "location_number", metadata.get("page_number", 1)
                ),
                "chunk_index": metadata["chunk_index"],
                "distance": float(distance),
            }

            if metadata.get("source_type") == "video":
                match["start_seconds"] = float(metadata["start_seconds"])
                match["end_seconds"] = float(metadata["end_seconds"])
                match["location_type"] = "timestamp"
            else:
                match["page_number"] = metadata.get(
                    "page_number", metadata.get("location_number", 1)
                )

            matches.append(match)
        return matches

    def ingest_video(self, filename: str, data: bytes) -> dict:
        checksum = hashlib.sha256(data).hexdigest()
        existing = self._find_document_by_hash(checksum)

        if existing:
            return {
                "document_id": existing["id"],
                "filename": existing["filename"],
                "status": "duplicate",
                "message": "This document has already been indexed.",
            }

        document_id = str(uuid.uuid4())
        video_service = VideoIngestionService(self.database_path)
        
        result = video_service.ingest(
            filename=filename,
            data=data,
            document_id=document_id,
        )
        chunks = result.get("chunks", [])
        video_chunks = [
            SimpleNamespace(
                chunk_index=chunk["chunk_index"],
                start_seconds=chunk["start_seconds"],
                end_seconds=chunk["end_seconds"],
                text=chunk["text"],
            )
            for chunk in chunks
        ]

        self.index_video_chunks(
            document_id=document_id,
            filename=filename,
            chunks=video_chunks,
        )

        keyframes = result.get("keyframes", [])
        diagram_count = 0
        if keyframes:
            diagram_count = self.index_video_diagrams(
                document_id=document_id,
                filename=filename,
                keyframes=keyframes,
            )

        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO documents (
                    id,
                    filename,
                    sha256,
                    page_count,
                    chunk_count,
                    status,
                    pages_needing_ocr
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    filename,
                    checksum,
                    0,
                    len(video_chunks),
                    "ready" if video_chunks else "failed",
                    "",
                ),
            )

        return {
            "document_id": document_id,
            "filename": filename,
            "status": "ready" if video_chunks else "failed",
            "source_type": "video",
            "duration_seconds": result.get("duration_seconds", 0.0),
            "language": result.get("language"),
            "transcript_segment_count": result.get("transcript_segment_count", 0),
            "chunk_count": len(video_chunks),
            "diagram_count": diagram_count,
        }

    def index_video_chunks(self, document_id: str, filename: str, chunks):
        if not chunks:
            return 0

        texts = [chunk.text for chunk in chunks]
        embeddings = self._embed(texts)
        ids = [
            f"{document_id}_video_{chunk.chunk_index}"
            for chunk in chunks
        ]
        metadatas = []
        for chunk in chunks:
            metadatas.append(
                {
                    "document_id": document_id,
                    "source_name": filename,
                    "source_type": "video",
                    "location_type": "timestamp",
                    "location_number": int(chunk.chunk_index),
                    "start_seconds": float(chunk.start_seconds),
                    "end_seconds": float(chunk.end_seconds),
                    "chunk_index": int(chunk.chunk_index),
                }
            )

        self._collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return len(chunks)

    def get_rag_service(self) -> RAGService:
        if self._rag_service is None:
            retriever = HybridRetriever(
                collection=self._collection,
                embed_function=self._embed,
            )
            self._rag_service = RAGService(retriever=retriever)
        return self._rag_service

    def save_quiz_question(self, question, document_id=None, chunk_index=None):
        question_id = str(uuid.uuid4())
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO quiz_questions (
                    id, question, question_type, options_json, correct_answer,
                    explanation, topic, difficulty, document_id, chunk_index, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question_id,
                    question.question,
                    question.question_type,
                    json.dumps(question.options),
                    question.correct_answer,
                    question.explanation,
                    question.topic,
                    question.difficulty,
                    document_id,
                    chunk_index,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return question_id

    def get_topic_mastery(self, student_id: str, topic: str) -> dict:
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT *
                FROM learner_topic_mastery
                WHERE student_id = ? AND topic = ?
                """,
                (student_id, topic),
            ).fetchone()

        if row is None:
            return {
                "student_id": student_id,
                "topic": topic,
                "mastery": LearnerModel.INITIAL_MASTERY,
                "attempts": 0,
                "correct": 0,
                "incorrect": 0,
                "last_score": 0.0,
                "streak": 0,
                "misconceptions": [],
                "status": "weak",
            }

        item = dict(row)
        item["misconceptions"] = [
            value for value in item["misconceptions"].split("|") if value
        ]
        item["status"] = LearnerModel.status(item["mastery"])
        return item

    def update_topic_mastery(
        self,
        student_id: str,
        topic: str,
        correct: bool,
        score: float,
        misconception: str = "",
    ) -> dict:
        current = self.get_topic_mastery(student_id, topic)
        model = LearnerModel()

        mastery = model.update(
            current_mastery=current["mastery"],
            correct=correct,
            score=score,
        )

        attempts = current["attempts"] + 1
        correct_count = current["correct"] + (1 if correct else 0)
        incorrect_count = current["incorrect"] + (0 if correct else 1)
        streak = current["streak"] + 1 if correct else 0

        misconceptions = current["misconceptions"]
        if misconception and misconception not in misconceptions:
            misconceptions.append(misconception)

        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO learner_topic_mastery (
                    student_id, topic, mastery, attempts, correct, incorrect,
                    last_score, streak, misconceptions, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(student_id, topic)
                DO UPDATE SET
                    mastery = excluded.mastery,
                    attempts = excluded.attempts,
                    correct = excluded.correct,
                    incorrect = excluded.incorrect,
                    last_score = excluded.last_score,
                    streak = excluded.streak,
                    misconceptions = excluded.misconceptions,
                    updated_at = excluded.updated_at
                """,
                (
                    student_id,
                    topic,
                    mastery,
                    attempts,
                    correct_count,
                    incorrect_count,
                    score,
                    streak,
                    "|".join(misconceptions),
                    now,
                ),
            )

        return {
            "student_id": student_id,
            "topic": topic,
            "mastery": mastery,
            "attempts": attempts,
            "correct": correct_count,
            "incorrect": incorrect_count,
            "last_score": score,
            "streak": streak,
            "misconceptions": misconceptions,
            "status": model.status(mastery),
        }

    def get_learner_profile(self, student_id: str) -> list[dict]:
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT *
                FROM learner_topic_mastery
                WHERE student_id = ?
                ORDER BY mastery ASC
                """,
                (student_id,),
            ).fetchall()

        model = LearnerModel()
        result = []
        for row in rows:
            item = dict(row)
            item["misconceptions"] = [
                value for value in item["misconceptions"].split("|") if value
            ]
            item["status"] = model.status(item["mastery"])
            item["recommended_difficulty"] = model.recommended_difficulty(
                item["mastery"]
            )
            result.append(item)
        return result

    def index_video_diagrams(self,document_id: str,filename: str,keyframes: list[dict],) -> int:
        """
        Indexes video keyframes/slides into:
        1. SQLite `diagrams` table for structured retrieval.
        2. ChromaDB collection for semantic image/diagram search.

        Expected keyframe dict structure:
        {
            "timestamp": 12.5,
            "image_path": "path/to/frame.jpg",
            "extracted_text": "Code / text on slide",
            "visual_summary": "Architecture diagram of transformer",
            "title": "Transformer Attention Layers", # optional
        }
        """
        if not keyframes:
            return 0

        diagram_records = []
        embed_texts = []
        ids = []
        metadatas = []

        for idx, kf in enumerate(keyframes):
            diagram_id = str(uuid.uuid4())
            img_path = Path(kf["image_path"])
            
            width, height = 0, 0
            if img_path.exists():
                with Image.open(img_path) as im:
                    width, height = im.size

            ext = img_path.suffix.lstrip(".").lower() or "jpg"
            timestamp = float(kf.get("timestamp", 0.0))
            title = kf.get("title") or f"Slide at {int(timestamp)}s"
            description = kf.get("extracted_text", "")
            educational_value = kf.get("visual_summary", "")

            diagram_records.append(
                (
                    diagram_id,
                    document_id,
                    None,                 
                    "video",              
                    int(timestamp),       
                    idx,                  
                    ext,                  
                    width,                
                    height,               
                    "slide_keyframe",     
                    title,               
                    description,         
                    educational_value,   
                )
            )

            searchable_text = (
                f"Diagram / Slide: {title}\n"
                f"Visual Description: {educational_value}\n"
                f"On-Screen Content: {description}"
            )
            embed_texts.append(searchable_text)
            ids.append(f"{document_id}_diagram_{idx}")
            metadatas.append(
                {
                    "document_id": document_id,
                    "source_name": filename,
                    "source_type": "diagram",
                    "diagram_id": diagram_id,
                    "image_path": str(img_path),
                    "location_type": "timestamp",
                    "location_number": int(timestamp),
                    "start_seconds": timestamp,
                    "title": title,
                }
            )

        with sqlite3.connect(self.database_path) as connection:
            connection.executemany(
                """
                INSERT INTO diagrams (
                    id,
                    document_id,
                    content_unit_id,
                    source_type,
                    location_number,
                    image_index,
                    extension,
                    width,
                    height,
                    diagram_type,
                    title,
                    description,
                    educational_value
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                diagram_records,
            )

        embeddings = self._embed(embed_texts)
        self._collection.add(
            ids=ids,
            documents=embed_texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        return len(diagram_records)

    def get_document_diagrams(self, document_id: str) -> list[dict]:
        """Fetches all diagrams and slides associated with a document."""
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, document_id, source_type, location_number,
                       image_index, width, height, diagram_type,
                       title, description, educational_value
                FROM diagrams
                WHERE document_id = ?
                ORDER BY location_number ASC
                """,
                (document_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_document_details(self, document_id: str) -> dict | None:
        """Fetch full extracted details including metadata, text chunks, video segments, and diagrams."""
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row

            doc = connection.execute(
                """
                SELECT id, filename, sha256, page_count, chunk_count, status, pages_needing_ocr
                FROM documents
                WHERE id = ?
                """,
                (document_id,),
            ).fetchone()

            if not doc:
                return None

            doc_dict = dict(doc)
            raw_ocr = doc_dict.pop("pages_needing_ocr", "")
            doc_dict["pages_needing_ocr"] = [
                int(x) for x in raw_ocr.split(",") if x.strip()
            ]

            video_row = connection.execute(
                """
                SELECT duration_seconds, language, language_probability, transcript_segment_count, video_path
                FROM videos
                WHERE document_id = ?
                """,
                (document_id,),
            ).fetchone()
            doc_dict["video_info"] = dict(video_row) if video_row else None

            chunks = connection.execute(
                """
                SELECT id, topic_id, source_type, location_number, chunk_index, text, content_type
                FROM content_units
                WHERE document_id = ?
                ORDER BY location_number ASC, chunk_index ASC
                """,
                (document_id,),
            ).fetchall()
            doc_dict["chunks"] = [dict(r) for r in chunks]

            if not doc_dict["chunks"] and doc_dict["video_info"]:
                v_chunks = connection.execute(
                    """
                    SELECT id, chunk_index, start_seconds, end_seconds, text
                    FROM video_chunks
                    WHERE document_id = ?
                    ORDER BY chunk_index ASC
                    """,
                    (document_id,),
                ).fetchall()
                doc_dict["chunks"] = [
                    {
                        "id": r["id"],
                        "chunk_index": r["chunk_index"],
                        "location_number": r["start_seconds"],
                        "text": r["text"],
                        "source_type": "video",
                    }
                    for r in v_chunks
                ]

            diagrams = connection.execute(
                """
                SELECT id, source_type, location_number, image_index, extension,
                       width, height, diagram_type, title, description, educational_value
                FROM diagrams
                WHERE document_id = ?
                ORDER BY location_number ASC
                """,
                (document_id,),
            ).fetchall()
            doc_dict["diagrams"] = [dict(d) for d in diagrams]

            topics = connection.execute(
                """
                SELECT id, name, description
                FROM topics
                WHERE document_id = ?
                """,
                (document_id,),
            ).fetchall()
            doc_dict["topics"] = [dict(t) for t in topics]

            return doc_dict


@lru_cache(maxsize=1)
def get_study_service() -> StudyService:
    return StudyService()