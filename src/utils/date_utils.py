"""
Date and time utilities for telemetry health evaluation framework.
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional
import re


def parse_week_year(filename: str) -> Tuple[int, int]:
    """
    Extract week and year from filename.
    
    Parameters
    ----------
    filename : str
        Filename in format Week{WW}Year{YYYY}.parquet
        
    Returns
    -------
    Tuple[int, int]
        (week, year)
        
    Raises
    ------
    ValueError
        If filename doesn't match expected format
        
    Examples
    --------
    >>> parse_week_year("Week21Year2026.parquet")
    (21, 2026)
    """
    pattern = r'Week(\d{1,2})Year(\d{4})\.parquet'
    match = re.search(pattern, filename)
    
    if not match:
        raise ValueError(f"Filename doesn't match expected format: {filename}")
    
    week = int(match.group(1))
    year = int(match.group(2))
    
    if not 1 <= week <= 53:
        raise ValueError(f"Invalid week number: {week}")
    
    return week, year


def get_week_date_range(year: int, week: int) -> Tuple[datetime, datetime]:
    """
    Get start and end dates for an ISO week.
    
    Parameters
    ----------
    year : int
        Year
    week : int
        ISO week number (1-53)
        
    Returns
    -------
    Tuple[datetime, datetime]
        (start_date, end_date) - Monday to Sunday
        
    Examples
    --------
    >>> get_week_date_range(2026, 21)
    (datetime(2026, 5, 18, 0, 0), datetime(2026, 5, 24, 23, 59, 59, 999999))
    """
    # ISO week date calculation
    # Week 1 is the first week with Thursday in it
    jan_4 = datetime(year, 1, 4)
    week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
    
    # Calculate start of target week
    start_date = week_1_monday + timedelta(weeks=week - 1)
    
    # End of week (Sunday 23:59:59.999999)
    end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
    
    return start_date, end_date


def format_date(dt: datetime, format_type: str = "iso") -> str:
    """
    Format datetime to string.
    
    Parameters
    ----------
    dt : datetime
        DateTime to format
    format_type : str
        Format type: "iso", "date", "datetime", "filename"
        
    Returns
    -------
    str
        Formatted date string
        
    Examples
    --------
    >>> dt = datetime(2026, 5, 25, 14, 30, 0)
    >>> format_date(dt, "iso")
    '2026-05-25T14:30:00'
    >>> format_date(dt, "date")
    '2026-05-25'
    >>> format_date(dt, "filename")
    '20260525'
    """
    formats = {
        "iso": "%Y-%m-%dT%H:%M:%S",
        "date": "%Y-%m-%d",
        "datetime": "%Y-%m-%d %H:%M:%S",
        "filename": "%Y%m%d",
    }
    
    format_str = formats.get(format_type, formats["iso"])
    return dt.strftime(format_str)


def calculate_lookback_period(
    end_date: datetime,
    lookback_window: str
) -> Tuple[datetime, datetime]:
    """
    Calculate start date from lookback window specification.
    
    Parameters
    ----------
    end_date : datetime
        End of evaluation period
    lookback_window : str
        Window specification: "24h", "7d", "4w", "8w", "12w"
        
    Returns
    -------
    Tuple[datetime, datetime]
        (start_date, end_date)
        
    Raises
    ------
    ValueError
        If lookback_window format is invalid
        
    Examples
    --------
    >>> end = datetime(2026, 5, 25, 0, 0)
    >>> start, end = calculate_lookback_period(end, "24h")
    >>> start
    datetime(2026, 5, 24, 0, 0)
    """
    # Parse lookback window
    pattern = r'(\d+)([hdw])'
    match = re.match(pattern, lookback_window.lower())
    
    if not match:
        raise ValueError(f"Invalid lookback window format: {lookback_window}")
    
    value = int(match.group(1))
    unit = match.group(2)
    
    if unit == 'h':
        start_date = end_date - timedelta(hours=value)
    elif unit == 'd':
        start_date = end_date - timedelta(days=value)
    elif unit == 'w':
        start_date = end_date - timedelta(weeks=value)
    else:
        raise ValueError(f"Unsupported time unit: {unit}")
    
    return start_date, end_date


def parse_baseline_version(version: str) -> datetime:
    """
    Parse baseline version string to datetime.
    
    Parameters
    ----------
    version : str
        Baseline version in YYYYMMDD format
        
    Returns
    -------
    datetime
        Parsed date
        
    Examples
    --------
    >>> parse_baseline_version("20260524")
    datetime(2026, 5, 24, 0, 0)
    """
    try:
        return datetime.strptime(version, "%Y%m%d")
    except ValueError as e:
        raise ValueError(f"Invalid baseline version format: {version}. Expected YYYYMMDD") from e


def get_current_baseline_version() -> str:
    """
    Get current baseline version string.
    
    Returns
    -------
    str
        Current date in YYYYMMDD format
        
    Examples
    --------
    >>> get_current_baseline_version()  # On 2026-05-25
    '20260525'
    """
    return datetime.now().strftime("%Y%m%d")
