"""Time utility tools for MCP server."""

from datetime import datetime
import pytz


def get_current_time(timezone: str = "UTC") -> dict:
    """
    Get current time in specified timezone.
    
    Args:
        timezone: Timezone name (e.g., 'UTC', 'America/New_York', 'Asia/Tokyo')
        
    Returns:
        Dictionary with time information
    """
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        
        return {
            "timezone": timezone,
            "datetime": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day_of_week": now.strftime("%A")
        }
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(f"Unknown timezone: {timezone}")


def list_timezones() -> dict:
    """List common timezones."""
    common_timezones = [
        "UTC",
        "America/New_York",
        "America/Los_Angeles",
        "America/Chicago",
        "Europe/London",
        "Europe/Paris",
        "Asia/Tokyo",
        "Asia/Shanghai",
        "Australia/Sydney"
    ]
    
    return {
        "common_timezones": common_timezones,
        "total_available": len(pytz.all_timezones)
    }
