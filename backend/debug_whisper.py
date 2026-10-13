from pathlib import Path
import sys

from faster_whisper import WhisperModel


VIDEO_PATH = Path(
    r"D:\OneDrive\Desktop\HacaktonProject\AI-Study-Companinon\backend\test_materials\sample_lecture.mp4"
)


def main():
    print("=" * 70)
    print("FASTER-WHISPER DIRECT DIAGNOSTIC")
    print("=" * 70)

    print("Python:", sys.executable)
    print("Video:", VIDEO_PATH)
    print("Exists:", VIDEO_PATH.exists())

    if not VIDEO_PATH.exists():
        raise FileNotFoundError(VIDEO_PATH)

    print("\nLoading Whisper model...")

    model = WhisperModel(
        "base",
        device="cpu",
        compute_type="int8",
    )

    print("Model loaded.")

    print("\nCalling transcribe()...")

    segments, info = model.transcribe(
        str(VIDEO_PATH),
        language="en",
        beam_size=5,

        # IMPORTANT:
        # Disable VAD for this diagnostic.
        vad_filter=False,

        condition_on_previous_text=False,
        temperature=0.0,
    )

    print("\nWhisper information")
    print("-" * 70)
    print("language:", info.language)
    print("language_probability:", info.language_probability)
    print("duration:", info.duration)

    if hasattr(info, "duration_after_vad"):
        print("duration_after_vad:", info.duration_after_vad)

    # IMPORTANT:
    # faster-whisper returns a lazy generator.
    # Transcription actually happens when we iterate it.
    segments = list(segments)

    print("\nSegment count:", len(segments))

    print("\nSegments")
    print("-" * 70)

    for index, segment in enumerate(segments):
        print(
            f"{index:03d} "
            f"[{segment.start:.2f} -> {segment.end:.2f}] "
            f"{segment.text!r}"
        )

        print(
            f"avg_logprob={segment.avg_logprob}"
        )

        print(
            f"no_speech_prob={segment.no_speech_prob}"
        )

        if index >= 20:
            print("\nShowing first 21 segments only.")
            break


if __name__ == "__main__":
    main()