from dataclasses import dataclass

@dataclass
class TranscriptSegment:
    segment_index:int
    start_seconds:float
    end_seconds:float
    text:str
    avg_logprob:float|None=None
    no_speech_probability: float | None = None
    words: list[dict] | None = None

@dataclass
class VideoTranscript:
    segments: list[TranscriptSegment]
    duration_seconds: float
    language: str
    language_probability: float

@dataclass
class VideoChunk:
    chunk_index: int
    start_seconds: float
    end_seconds: float
    text: str
    segment_indices: list[int]

    