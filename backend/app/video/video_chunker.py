from app.core.config import settings
from app.video.video_models import TranscriptSegment, VideoChunk

def chunk_transcript(segments:list[TranscriptSegment], chunk_seconds:int | None = None, overlap_seconds: int | None=None)->list[VideoChunk]:
    if not segments:
        return []

    chunk_seconds = (chunk_seconds or settings.video_chunk_seconds)
    overlap_seconds = (
        overlap_seconds
        if overlap_seconds is not None
        else settings.video_chunk_overlap_seconds
    )

    if chunk_seconds <= 0:
        raise ValueError("chunk_seconds must be positive")

    if overlap_seconds >= chunk_seconds:
        raise ValueError("overlap_seconds must be smaller than chunk_seconds.")

    chunks = []
    current_segments = []
    current_start = segments[0].start_seconds
    current_end = current_start
    for segment in segments:
        if not current_segments:
            current_start = segment.start_seconds

        proposed_end = segment.end_seconds
        duration = proposed_end - current_start
        if (current_segments and duration > chunk_seconds):
            chunks.append(_create_chunk(len(chunks), current_segments))
            overlap_start = max(current_start, current_end - overlap_seconds)
            current_segments = [
                item 
                for item in current_segments
                if item.end_seconds > overlap_start
            ]
            if current_segments:
                current_start = current_segments[0].start_seconds
            else:
                current_start = segments.start_seconds

        current_segments.append(segment)
        current_end = max(current_end, segment.end_seconds)

    if current_segments:
        chunks.append(_create_chunk(len(chunks), current_segments))
    
    return chunks

def _create_chunk(index:int, segments: list[TranscriptSegment])->VideoChunk:
    return VideoChunk(
        chunk_index=index,
        start_seconds=segments[0].start_seconds,
        end_seconds=segments[-1].end_seconds,
        text=" ".join(
            segment.text.strip()
            for segment in segments
            if segment.text.strip()
        ),
        segment_indices=[
            segment.segment_index
            for segment in segments
        ],
    )