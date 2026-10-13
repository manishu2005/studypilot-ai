from app.video.video_utils import format_timestamp

def format_location(source_type: str, location_type: str, start: float | int, end: float | int)->str:
    if source_type == "pdf":
        return f"Page {int(start)}"

    if source_type == "pptx":
        return f"Slide {int(start)}"

    if source_type == "video":
        start_label = format_timestamp(float(start))
        end_label = format_timestamp(float(end))
        if start_label == end_label:
            return start_label

        return (f"{start_label} - {end_label}")

    return (
        f"{location_type}"
        f"{start}-{end}"
    )

def build_source_label(source_name: str, source_type: str, location_type: str, start: float | int, end: float | int)->str:
    location = format_location(
        source_type=source_type,
        location_type=location_type,
        start=start,
        end=end,
    )

    return (
        f"{source_name} — {location}"
    )