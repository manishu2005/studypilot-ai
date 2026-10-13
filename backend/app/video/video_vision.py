from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

from app.core.gemini_client import get_gemini_client
from app.core.config import settings


@dataclass
class VideoKeyframe:
    timestamp_seconds: float
    frame_index: int
    image_path: Path
    extracted_text: str | None = None
    visual_summary: str | None = None


class VideoSlideExtractor:
    def __init__(
        self,
        output_dir: str | Path = "./video_keyframes",
        sample_interval_sec: float = 2.0,
        difference_threshold: float = 0.35,
    ):
        """
        :param sample_interval_sec: Check video every N seconds (e.g., 2.0s).
        :param difference_threshold: Color histogram difference required to declare a new slide (0.0 to 1.0).
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.sample_interval_sec = sample_interval_sec
        self.difference_threshold = difference_threshold
        self.gemini_client = get_gemini_client()

    def _frame_difference(self, frame_a: np.ndarray, frame_b: np.ndarray) -> float:
        """Compute normalized correlation distance between color histograms of two frames."""
        gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)

        hist_a = cv2.calcHist([gray_a], [0], None, [64], [0, 256])
        hist_b = cv2.calcHist([gray_b], [0], None, [64], [0, 256])

        cv2.normalize(hist_a, hist_a, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        cv2.normalize(hist_b, hist_b, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

        similarity = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
        return max(0.0, 1.0 - similarity)

    def extract_keyframes(self, video_path: str | Path) -> list[VideoKeyframe]:
        video_path = Path(video_path)
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_step = int(fps * self.sample_interval_sec)

        keyframes: list[VideoKeyframe] = []
        last_saved_frame: np.ndarray | None = None
        frame_idx = 0

        video_id = video_path.stem
        target_dir = self.output_dir / video_id
        target_dir.mkdir(parents=True, exist_ok=True)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_step == 0:
                timestamp = round(frame_idx / fps, 2)
                should_save = False

                if last_saved_frame is None:
                    should_save = True
                else:
                    diff = self._frame_difference(last_saved_frame, frame)
                    if diff >= self.difference_threshold:
                        should_save = True

                if should_save:
                    save_path = target_dir / f"slide_{int(timestamp)}s.jpg"
                    # Resize to 1080p width to save disk space while preserving text legibility
                    h, w = frame.shape[:2]
                    if w > 1920:
                        scale = 1920 / w
                        frame = cv2.resize(frame, (1920, int(h * scale)))

                    cv2.imwrite(str(save_path), frame)
                    keyframes.append(
                        VideoKeyframe(
                            timestamp_seconds=timestamp,
                            frame_index=frame_idx,
                            image_path=save_path,
                        )
                    )
                    last_saved_frame = frame.copy()

            frame_idx += 1

        cap.release()
        return keyframes

    def analyze_slide(self, image_path: Path) -> tuple[str, str]:
        """
        Uses Gemini Vision to extract both text/code and a short educational description.
        """
        pil_img = Image.open(image_path)
        prompt = (
            "Analyze this slide or video frame. "
            "1. Extract all legible text, code, math formulas, and diagrams accurately. "
            "2. Provide a 1-sentence summary of the slide's visual topic. "
            "Format your output as:\n"
            "TEXT: <extracted text>\n"
            "SUMMARY: <summary>"
        )

        model_name = getattr(settings, "gemini_model", "gemini-1.5-flash")
        response = self.gemini_client.models.generate_content(
            model=model_name,
            contents=[prompt, pil_img],
        )

        raw = response.text or ""
        text_part = ""
        summary_part = ""

        if "SUMMARY:" in raw:
            parts = raw.split("SUMMARY:", 1)
            text_part = parts[0].replace("TEXT:", "").strip()
            summary_part = parts[1].strip()
        else:
            text_part = raw.strip()

        return text_part, summary_part