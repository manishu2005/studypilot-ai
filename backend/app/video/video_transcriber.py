from pathlib import Path
from faster_whisper import WhisperModel
from app.core.config import settings
from app.video.video_models import TranscriptSegment, VideoTranscript
from app.video.video_vision import VideoSlideExtractor

class VideoTranscriber:
    def __init__(self):
        self._model = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                settings.whisper_model,
                device=settings.whisper_device,
                compute_type=settings.whisper_compute_type,
            )
        return self._model

    def transcribe(self, video_path: str | Path) -> VideoTranscript:
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        if video_path.stat().st_size == 0:
            raise ValueError(f"Video file is empty: {video_path}")

        model = self._get_model()
        language = settings.whisper_language.strip() if settings.whisper_language else None

        segments_gen, info = model.transcribe(
            str(video_path),
            language=language,
            beam_size=settings.whisper_beam_size,
            vad_filter=settings.whisper_vad_filter,
            word_timestamps=True,
            condition_on_previous_text=False,
        )
        segments = list(segments_gen)

        if settings.whisper_vad_filter and not any(s.text.strip() for s in segments):
            segments_gen, info = model.transcribe(
                str(video_path),
                language=language,
                beam_size=settings.whisper_beam_size,
                vad_filter=False,
                word_timestamps=True,
                condition_on_previous_text=False,
            )
            segments = list(segments_gen)

        transcript_segments = []
        for index, segment in enumerate(segments):
            text = segment.text.strip()
            if not text:
                continue

            words = None
            if segment.words:
                words = [
                    {
                        "start": float(w.start) if w.start is not None else None,
                        "end": float(w.end) if w.end is not None else None,
                        "word": w.word,
                        "probability": float(w.probability) if w.probability is not None else None,
                    }
                    for w in segment.words
                ]

            transcript_segments.append(
                TranscriptSegment(
                    segment_index=index,
                    start_seconds=float(segment.start or 0.0),
                    end_seconds=float(segment.end or 0.0),
                    text=text,
                    avg_logprob=float(segment.avg_logprob) if segment.avg_logprob is not None else None,
                    no_speech_probability=(
                        float(segment.no_speech_prob)
                        if getattr(segment, "no_speech_prob", None) is not None
                        else None
                    ),
                    words=words,
                )
            )

        return VideoTranscript(
            segments=transcript_segments,
            duration_seconds=float(getattr(info, "duration", 0.0)),
            language=info.language,
            language_probability=float(getattr(info, "language_probability", 0.0)),
        )

    def process_full_video(video_path: Path):
        transcriber = VideoTranscriber()
        transcript = transcriber.transcribe(video_path)

        extractor = VideoSlideExtractor()
        keyframes = extractor.extract_keyframes(video_path)

        for kf in keyframes:
            extracted_text, summary = extractor.analyze_slide(kf.image_path)
            kf.extracted_text = extracted_text
            kf.visual_summary = summary

        multimodal_chunks = []
        for kf in keyframes:
            matching_audio = [
                seg.text
                for seg in transcript.segments
                if abs(seg.start_seconds - kf.timestamp_seconds) <= 15.0
            ]
            spoken_text = " ".join(matching_audio)

            combined_chunk_text = (
                f"[Timestamp: {kf.timestamp_seconds}s]\n"
                f"[Visual Summary]: {kf.visual_summary}\n"
                f"[On-Screen Text/Code]: {kf.extracted_text}\n"
                f"[Spoken Audio]: {spoken_text}"
            )

            multimodal_chunks.append({
                "timestamp": kf.timestamp_seconds,
                "image_path": str(kf.image_path),
                "text": combined_chunk_text,
            })

        return multimodal_chunks