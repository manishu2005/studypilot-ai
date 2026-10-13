import sqlite3
import uuid
from pathlib import Path
from app.video.video_chunker import chunk_transcript
from app.video.video_models import VideoTranscript
from app.video.video_storage import file_sha256, save_video
from app.video.video_transcriber import VideoTranscriber

class VideoIngestionService:
    def __init__(self, database_path:str):
        self.database_path = database_path
        self.transcriber = VideoTranscriber()

    def ingest(self, filename:str, data:bytes, document_id:str)->dict:
        video_path = save_video(filename=filename, data=data, document_id=document_id)
        transcript = self.transcriber.transcribe(video_path)
        chunks = chunk_transcript(transcript.segments)
        self._save_video(
            document_id=document_id,
            video_path=video_path,
            transcript=transcript,
            chunks=chunks,
        )

        return{
            "document_id": document_id,
            "filename": filename,
            "status": "ready",
            "duration_seconds": transcript.duration_seconds,
            "language": transcript.language,
            "language_probability": transcript.language_probability,
            "transcript_segment_count": len(transcript.segments),
            "chunk_count": len(chunks),
            "chunks": [
                {
                    "chunk_index": chunk.chunk_index,
                    "start_seconds": chunk.start_seconds,
                    "end_seconds": chunk.end_seconds,
                    "text": chunk.text,
                }
                for chunk in chunks
            ],
        }

    def _save_video(self, document_id:str, video_path:Path, transcript:VideoTranscript, chunks):
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO videos(id, document_id, duration_seconds, language, language_probability, transcript_segment_count, video_path)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    str(uuid.uuid4()),
                    document_id,
                    transcript.duration_seconds,
                    transcript.language,
                    transcript.language_probability,
                    len(transcript.segments),
                    str(video_path),
                ),
            )

            for segment in (transcript.segments):
                connection.execute(
                    """
                    INSERT INTO video_transcript_segments(id, document_id, segment_index, start_seconds, end_seconds, text, avg_logprob, no_speech_probability)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        document_id,
                        segment.segment_index,
                        segment.start_seconds,
                        segment.end_seconds,
                        segment.text,
                        segment.avg_logprob,
                        segment.no_speech_probability,
                    ),
                )
            for chunk in chunks:
                connection.execute(
                    """
                    INSERT INTO video_chunks(id, document_id, chunk_index, start_seconds, end_seconds, text)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        document_id,
                        chunk.chunk_index,
                        chunk.start_seconds,
                        chunk.end_seconds,
                        chunk.text,
                    ),
                )