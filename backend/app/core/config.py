from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    app_name: str = "AI-Study_Companion"
    max_upload_mb: int = 25

    database_path: str = str(BACKEND_DIR / "study_companion.db")
    chroma_path: str = str(BACKEND_DIR / "chroma_db")

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    groq_api_key:str=""
    groq_model:str="openai/gpt-oss-120b"
    whisper_model:str="small"
    whisper_device:str="cpu"
    whisper_compute_type:str="int8"
    whisper_language:str=""
    whisper_beam_size:int=5
    whisper_vad_filter:bool=True
    video_chunk_seconds:int=45
    video_chunk_overlap_seconds:int=5

    model_config = SettingsConfigDict(
        env_file= BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()