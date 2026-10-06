"""Small, deterministic reporting metrics shared by orchestration stages."""


def real_time_factor(elapsed_seconds: float, media_seconds: float) -> float | None:
    """Return processing time divided by media duration; 1.0 means real time."""
    if elapsed_seconds <= 0 or media_seconds <= 0:
        return None
    return round(elapsed_seconds / media_seconds, 4)
