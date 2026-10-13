from app.video_utils import format_timestamp, source_label
from app.video_chunker import chunk_transcript
from app.video_models import TranscriptSegment

def test_format_timestamp():
    assert (format_timestamp(0)=="00:00:00")
    assert (format_timestamp(63)=="00:01:03")
    assert (format_timestamp(762)=="00:12:42")


def test_source_label():
    result = source_label("lecture.mp4", 763,798)
    assert result == (
        "lecture.mp4 --" ,
        "00:12:43-00:13:18"
    )

def test_video_chunking_preserves_timestamps():
    segments = [
        TranscriptSegment(
            segment_index=0,
            start_seconds=0,
            end_seconds=10,
            text="BFS uses a queue.",
        ),
        TranscriptSegment(
            segment_index=1,
            start_seconds=10,
            end_seconds=20,
            text="It traverses level by level.",
        ),
        TranscriptSegment(
            segment_index=2,
            start_seconds=20,
            end_seconds=30,
            text="This is useful for graphs.",
        ),
    ]

    chunks = chunk_transcript(
        segments,
        chunk_seconds=25,
        overlap_seconds=5,
    )

    assert chunks

    assert chunks[0].start_seconds == 0

    assert (
        chunks[0].end_seconds
        == 20
        or chunks[0].end_seconds
        == 30
    )

    assert (
        "queue"
        in chunks[0].text.lower()
    )