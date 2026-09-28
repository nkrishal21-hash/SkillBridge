"""
app/utils/time.py — Timezone helpers for Nepal Standard Time (UTC+05:45).
Nepal does not observe Daylight Saving Time (DST).
"""

from datetime import datetime, date, timezone, timedelta
from typing import Optional

# Nepal Standard Time (UTC+05:45).
NPT = timezone(timedelta(hours=5, minutes=45))


def to_nepal(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convert a datetime to Nepal Standard Time (NPT).
    Treats a naive datetime as UTC (since DB models store timestamps in UTC).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(NPT)


def nepal_now() -> datetime:
    """Return the current datetime in Nepal Standard Time."""
    return datetime.now(timezone.utc).astimezone(NPT)


def nepal_today() -> date:
    """Return today's date in Nepal Standard Time."""
    return nepal_now().date()


def npt_filter(dt: Optional[datetime], fmt: str = "%b %d, %Y %I:%M %p") -> str:
    """
    Jinja filter to display a stored UTC datetime in Nepal Standard Time.
    Default format is '%b %d, %Y %I:%M %p', accepting an optional format string argument.
    """
    if not dt:
        return ""
    nepal_dt = to_nepal(dt)
    return nepal_dt.strftime(fmt)
