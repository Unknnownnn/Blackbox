"""
Timezone utility functions for the platform.
Handles timezone conversion and display formatting.
"""

from datetime import datetime
import pytz
from models.settings import Settings


def get_platform_timezone():
    """Get the configured platform timezone, defaults to UTC."""
    tz_name = Settings.get('timezone', 'UTC')
    try:
        return pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        return pytz.UTC


def get_timezone_aware_now():
    """Get current datetime in the platform's configured timezone."""
    tz = get_platform_timezone()
    return datetime.now(pytz.UTC).astimezone(tz)


def convert_to_platform_tz(dt):
    """
    Convert a datetime to the platform's timezone.
    
    Args:
        dt: A datetime object (naive or aware)
    
    Returns:
        Timezone-aware datetime in platform timezone
    """
    tz = get_platform_timezone()
    
    if dt is None:
        return None
    
    # If naive datetime, assume it's UTC
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    return dt.astimezone(tz)


def format_datetime(dt, format_str='%Y-%m-%d %H:%M:%S'):
    """
    Format a datetime in the platform's timezone.
    
    Args:
        dt: A datetime object (naive or aware)
        format_str: strftime format string
    
    Returns:
        Formatted datetime string
    """
    if dt is None:
        return 'Never'
    
    tz_dt = convert_to_platform_tz(dt)
    return tz_dt.strftime(format_str)


def get_common_timezones():
    """
    Get a list of common timezones for UI selection.
    
    Returns:
        List of (timezone_name, display_name) tuples
    """
    common_zones = [
        ('UTC', 'UTC (Coordinated Universal Time)'),
        ('US/Eastern', 'US Eastern (New York)'),
        ('US/Central', 'US Central (Chicago)'),
        ('US/Mountain', 'US Mountain (Denver)'),
        ('US/Pacific', 'US Pacific (Los Angeles)'),
        ('Europe/London', 'Europe/London (GMT)'),
        ('Europe/Paris', 'Europe/Paris (CET)'),
        ('Europe/Berlin', 'Europe/Berlin (CET)'),
        ('Europe/Moscow', 'Europe/Moscow (MSK)'),
        ('Asia/Dubai', 'Asia/Dubai (GST)'),
        ('Asia/Kolkata', 'Asia/Kolkata (IST)'),
        ('Asia/Shanghai', 'Asia/Shanghai (CST)'),
        ('Asia/Tokyo', 'Asia/Tokyo (JST)'),
        ('Asia/Singapore', 'Asia/Singapore (SGT)'),
        ('Australia/Sydney', 'Australia/Sydney (AEDT)'),
        ('Pacific/Auckland', 'Pacific/Auckland (NZDT)'),
    ]
    return common_zones


def get_timezone_offset(tz_name=None):
    """
    Get the UTC offset string for a timezone.
    
    Args:
        tz_name: Timezone name, defaults to platform timezone
    
    Returns:
        Offset string like '+05:00' or '-08:00'
    """
    if tz_name is None:
        tz = get_platform_timezone()
    else:
        try:
            tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            return '+00:00'
    
    now = datetime.now(pytz.UTC)
    tz_now = now.astimezone(tz)
    offset = tz_now.strftime('%z')
    
    # Format as +HH:MM
    if len(offset) >= 5:
        return f"{offset[:3]}:{offset[3:]}"
    return '+00:00'
