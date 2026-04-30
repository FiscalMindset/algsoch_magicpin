"""Utils module."""
from .formatters import format_date, format_time, validate_context

__all__ = [
    "format_date",
    "format_time",
    "validate_context",
]


def format_date(date_obj):
    """Format datetime object to string."""
    return date_obj.isoformat() if date_obj else None


def format_time(seconds):
    """Format seconds to readable time."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m"
    else:
        return f"{int(seconds / 3600)}h"


def validate_context(context_data, required_fields):
    """Validate context has required fields."""
    missing = [field for field in required_fields if field not in context_data]
    return len(missing) == 0, missing
