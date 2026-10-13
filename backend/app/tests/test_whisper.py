import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.video_transcriber import VideoTranscriber


BACKEND_DIR = Path(__file__).resolve().parents[2]
SAMPLE_VIDEO = BACKEND_DIR / "test_materials" / "sample_lecture.mp4"


def test_transcribe_rejects_missing_video(tmp_path):
    video_path = tmp_path / "missing.mp4"
    transcriber = VideoTranscriber()

    with pytest.raises(FileNotFoundError, match="Video not found"):
        transcriber.transcribe(video_path)


def test_transcribe_rejects_empty_video(tmp_path):
    video_path = tmp_path / "empty.mp4"
    video_path.write_bytes(b"")

    transcriber = VideoTranscriber()

    with pytest.raises(ValueError, match="Video file is empty"):
        transcriber.transcribe(video_path)


def test_transcribe_returns_timestamped_segments(tmp_path, monkeypatch):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"fake video data")

    fake_segment = SimpleNamespace(
        start=1.0,
        end=3.5,
        text=" Introduction to computer science. ",
        avg_logprob=-0.2,
        no_speech_prob=0.01,
        words=[
            SimpleNamespace(
                start=1.0,
                end=1.5,
                word=" Introduction",
                probability=0.95,
            )
        ],
    )

    fake_info = SimpleNamespace(
        duration=10.0,
        language="en",
        language_probability=0.99,
    )

    class FakeModel:
        def transcribe(self, *args, **kwargs):
            return iter([fake_segment]), fake_info

    transcriber = VideoTranscriber()
    monkeypatch.setattr(transcriber, "_get_model", lambda: FakeModel())

    result = transcriber.transcribe(video_path)

    assert result.language == "en"
    assert result.language_probability == pytest.approx(0.99)
    assert result.duration_seconds == pytest.approx(10.0)
    assert len(result.segments) == 1

    segment = result.segments[0]
    assert segment.start_seconds == pytest.approx(1.0)
    assert segment.end_seconds == pytest.approx(3.5)
    assert segment.text == "Introduction to computer science."
    assert segment.words is not None
    assert segment.words[0]["word"] == " Introduction"

def test_transcribe_returns_empty_segments_when_no_speech_detected(tmp_path, monkeypatch):
    video_path = tmp_path / "beep.mp4"
    video_path.write_bytes(b"video data does not validated")
    fake_info = SimpleNamespace(
        duration=5.0,
        language="en",
        language_probability=0.5
    )

    class FakeModel:
        def transcribe(self, *args, **kwargs):
            return iter([]), fake_info

    transcriber = VideoTranscriber()
    monkeypatch.setattr(transcriber, "_get_model", lambda:FakeModel())
    result = transcriber.transcribe(video_path)
    assert result.segments == []
    assert result.duration_seconds == pytest.approx(5.0)

@pytest.mark.integration
def test_sample_lecture_transcription():

    if os.getenv("RUN_WHISPER_INTEGRATION") != "1":
        pytest.skip("Set RUN_WHISPER_INTEGRATION=1 to run real Whisper transcription")

    if not SAMPLE_VIDEO.is_file():
        pytest.skip(f"Sample lecture video not found: {SAMPLE_VIDEO}")

    result = VideoTranscriber().transcribe(SAMPLE_VIDEO)

    assert result.language
    assert result.duration_seconds > 0
    assert result.segments

    for segment in result.segments:
        assert segment.start_seconds >= 0
        assert segment.end_seconds >= segment.start_seconds
        assert segment.text.strip()
