import hashlib
from pathlib import Path

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".m4v",
}

def is_supported_video(filename:str)->bool:
    return (
        Path(filename).suffix.lower() in VIDEO_EXTENSIONS
    )

def save_video(filename:str, data:bytes, document_id:str)->Path:
    extension = (Path(filename).suffix.lower())
    if extension not in VIDEO_EXTENSIONS:
        raise ValueError(
             f"Unsupported video format: "
            f"{extension}"
        )

    root = (Path(__file__).resolve().parent.parent / "uploads" / "videos" / document_id)
    root.mkdir(parents=True, exist_ok=True)

    safe_name = (Path(filename).stem.replace(" ","_").replace("/","_").replace("\\", "_"))
    output_path = root / f"{safe_name}{extension}"
    output_path.write_bytes(data)
    return output_path

def file_sha256(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

    
