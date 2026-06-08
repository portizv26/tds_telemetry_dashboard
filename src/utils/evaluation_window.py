"""
Evaluation window management for technique execution.
Based on implementation_phase_1.md Day 9
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from src.utils.date_utils import calculate_lookback_period, get_week_date_range

logger = logging.getLogger(__name__)


@dataclass
class EvaluationWindow:
    """
    Temporal window for technique evaluation.
    
    Attributes
    ----------
    start : datetime
        Window start timestamp
    end : datetime
        Window end timestamp
    lookback_window : str
        Window duration (e.g., "24h", "7d", "8w")
    cadence : str
        Evaluation frequency (e.g., "daily", "weekly", "6h")
    """
    
    start: datetime
    end: datetime
    lookback_window: str
    cadence: str
    
    def __post_init__(self):
        """Validate window parameters."""
        if self.end <= self.start:
            raise ValueError(f"Window end ({self.end}) must be after start ({self.start})")
    
    def duration_days(self) -> float:
        """Get window duration in days."""
        delta = self.end - self.start
        return delta.total_seconds() / 86400
    
    def duration_hours(self) -> float:
        """Get window duration in hours."""
        delta = self.end - self.start
        return delta.total_seconds() / 3600
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"EvaluationWindow("
            f"start={self.start.isoformat()}, "
            f"end={self.end.isoformat()}, "
            f"lookback={self.lookback_window}, "
            f"cadence={self.cadence})"
        )


class EvaluationWindowGenerator:
    """
    Generates evaluation windows for different technique types.
    
    Supports:
    - Rolling windows (6h, 24h)
    - Weekly windows (7d)
    - Multi-week windows (4w, 8w, 12w)
    """
    
    @staticmethod
    def generate_daily_window(
        evaluation_date: datetime,
        lookback_window: str = "24h"
    ) -> EvaluationWindow:
        """
        Generate a daily evaluation window.
        
        Parameters
        ----------
        evaluation_date : datetime
            The date to evaluate (end of window)
        lookback_window : str
            Lookback duration (e.g., "24h")
            
        Returns
        -------
        EvaluationWindow
            Daily evaluation window
            
        Examples
        --------
        >>> eval_date = datetime(2026, 5, 25, 23, 59, 59)
        >>> window = EvaluationWindowGenerator.generate_daily_window(eval_date)
        >>> window.start
        datetime(2026, 5, 24, 23, 59, 59)
        """
        start, end = calculate_lookback_period(evaluation_date, lookback_window)
        
        return EvaluationWindow(
            start=start,
            end=end,
            lookback_window=lookback_window,
            cadence="daily"
        )
    
    @staticmethod
    def generate_weekly_window(
        year: int,
        week: int,
        lookback_weeks: int = 1
    ) -> EvaluationWindow:
        """
        Generate a weekly evaluation window.
        
        Parameters
        ----------
        year : int
            Year
        week : int
            ISO week number
        lookback_weeks : int
            Number of weeks to look back
            
        Returns
        -------
        EvaluationWindow
            Weekly evaluation window
            
        Examples
        --------
        >>> window = EvaluationWindowGenerator.generate_weekly_window(2026, 21)
        >>> # Returns window for Week 21, 2026
        """
        # Get end of target week
        week_start, week_end = get_week_date_range(year, week)
        
        # Calculate start based on lookback
        if lookback_weeks == 1:
            start = week_start
        else:
            start = week_end - timedelta(weeks=lookback_weeks)
        
        return EvaluationWindow(
            start=start,
            end=week_end,
            lookback_window=f"{lookback_weeks}w",
            cadence="weekly"
        )
    
    @staticmethod
    def generate_hourly_window(
        evaluation_timestamp: datetime,
        lookback_hours: int = 6
    ) -> EvaluationWindow:
        """
        Generate an hourly evaluation window (for AutoEncoder).
        
        Parameters
        ----------
        evaluation_timestamp : datetime
            Evaluation timestamp (end of window)
        lookback_hours : int
            Number of hours to look back
            
        Returns
        -------
        EvaluationWindow
            Hourly evaluation window
        """
        start = evaluation_timestamp - timedelta(hours=lookback_hours)
        
        return EvaluationWindow(
            start=start,
            end=evaluation_timestamp,
            lookback_window=f"{lookback_hours}h",
            cadence=f"{lookback_hours}h"
        )
    
    @staticmethod
    def generate_trend_windows(
        end_date: datetime,
        lookback_weeks_list: List[int] = [4, 8, 12]
    ) -> List[EvaluationWindow]:
        """
        Generate multiple trend analysis windows.
        
        Parameters
        ----------
        end_date : datetime
            End date for all windows
        lookback_weeks_list : List[int]
            List of lookback periods in weeks
            
        Returns
        -------
        List[EvaluationWindow]
            List of trend windows (4w, 8w, 12w)
            
        Examples
        --------
        >>> end = datetime(2026, 5, 25)
        >>> windows = EvaluationWindowGenerator.generate_trend_windows(end)
        >>> len(windows)
        3
        """
        windows = []
        
        for weeks in lookback_weeks_list:
            start = end_date - timedelta(weeks=weeks)
            
            window = EvaluationWindow(
                start=start,
                end=end_date,
                lookback_window=f"{weeks}w",
                cadence="weekly"
            )
            windows.append(window)
        
        return windows
    
    @staticmethod
    def generate_custom_window(
        start: datetime,
        end: datetime,
        cadence: str = "custom"
    ) -> EvaluationWindow:
        """
        Generate a custom evaluation window.
        
        Parameters
        ----------
        start : datetime
            Window start
        end : datetime
            Window end
        cadence : str
            Cadence label
            
        Returns
        -------
        EvaluationWindow
            Custom evaluation window
        """
        # Calculate lookback window string
        delta = end - start
        days = delta.days
        
        if days <= 1:
            lookback_window = f"{int(delta.total_seconds() / 3600)}h"
        elif days <= 14:
            lookback_window = f"{days}d"
        else:
            weeks = days // 7
            lookback_window = f"{weeks}w"
        
        return EvaluationWindow(
            start=start,
            end=end,
            lookback_window=lookback_window,
            cadence=cadence
        )
