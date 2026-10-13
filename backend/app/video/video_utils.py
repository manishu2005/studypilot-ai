def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS."""
    seconds = int(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def source_label(filename: str, start_seconds: float, end_seconds: float):
    """Return source filename and timestamp range."""

    start = format_timestamp(start_seconds)
    end = format_timestamp(end_seconds)

    return (
        f"{filename} --",
        f"{start}-{end}",
    )