"""
Weekly Signal Aggregator.

Aggregates minute-level telemetry into weekly summaries for trend analysis.

Methodology
-----------
1. Load one week of minute-level Silver data
2. Group by unit + signal + operational state
3. Calculate statistics: mean, median, std, percentiles (P5, P50, P95, P99)
4. Calculate derived metrics: abnormal%, event_count, coverage
5. Write to weekly aggregates partition

Output used by: Trend Analysis technique
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path

from src.config.signal_registry import SignalRegistry
from src.baselines.baseline_manager import BaselineManager
from src.utils.logger import get_logger


class WeeklyAggregator:
    """
    Aggregates minute-level telemetry into weekly summaries.
    
    Parameters
    ----------
    signal_registry : SignalRegistry
        Signal metadata registry
    baseline_manager : BaselineManager
        Baseline retrieval manager
    output_dir : Path
        Directory for weekly aggregates
    """
    
    def __init__(
        self,
        signal_registry: SignalRegistry,
        baseline_manager: BaselineManager,
        output_dir: Path,
    ):
        self.signal_registry = signal_registry
        self.baseline_manager = baseline_manager
        self.output_dir = output_dir
        self.logger = get_logger("weekly_aggregator")
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def aggregate_week(
        self,
        unit_id: str,
        client: str,
        equipment_model: str,
        week_start: datetime,
        week_end: datetime,
        silver_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Aggregate one week of data for all signals.
        
        Parameters
        ----------
        unit_id : str
            Equipment identifier
        client : str
            Client identifier
        equipment_model : str
            Equipment model
        week_start : datetime
            Week start date
        week_end : datetime
            Week end date
        silver_df : pd.DataFrame
            Silver layer telemetry data
        
        Returns
        -------
        pd.DataFrame
            Weekly aggregate dataframe
        """
        try:
            # Filter to week
            week_df = silver_df[
                (silver_df['Fecha'] >= week_start) &
                (silver_df['Fecha'] <= week_end)
            ].copy()
            
            if len(week_df) == 0:
                self.logger.warning(
                    f"No data for {unit_id} in week {week_start.date()} to {week_end.date()}"
                )
                return pd.DataFrame()
            
            # Get all signals from registry
            signals = self.signal_registry.get_all_signals()
            
            aggregates = []
            
            for signal in signals:
                signal_name = signal.name
                
                # Skip if signal not in dataframe
                if signal_name not in week_df.columns:
                    continue
                
                # Get valid states for this signal
                valid_states = signal.valid_states
                
                # Aggregate by operational state
                for state in valid_states:
                    state_df = week_df[week_df['EstadoMaquina'] == state].copy()
                    
                    if len(state_df) == 0:
                        continue
                    
                    # Extract signal values
                    values = state_df[signal_name].dropna()
                    
                    if len(values) == 0:
                        continue
                    
                    # Calculate statistics
                    agg = self._calculate_statistics(
                        unit_id=unit_id,
                        client=client,
                        equipment_model=equipment_model,
                        signal_name=signal_name,
                        system=signal.system,
                        operational_state=state,
                        values=values,
                        week_start=week_start,
                        week_end=week_end,
                        total_minutes=len(state_df),
                    )
                    
                    # Get baseline for comparison
                    baseline = self.baseline_manager.get_baseline(
                        client=client,
                        equipment_model=equipment_model,
                        unit_id=unit_id,
                        signal_name=signal_name,
                        operational_state=state,
                    )
                    
                    if baseline:
                        # Calculate abnormal percentage
                        agg['abnormal_pct'] = self._calculate_abnormal_pct(
                            values=values,
                            baseline=baseline,
                            risk_direction=signal.risk_direction,
                        )
                        agg['baseline_version'] = baseline.get('baseline_version')
                    else:
                        agg['abnormal_pct'] = 0.0
                        agg['baseline_version'] = None
                    
                    aggregates.append(agg)
            
            if not aggregates:
                return pd.DataFrame()
            
            # Convert to DataFrame
            agg_df = pd.DataFrame(aggregates)
            
            return agg_df
            
        except Exception as e:
            self.logger.error(
                f"Weekly aggregation failed for {unit_id}: {e}",
                exc_info=True
            )
            return pd.DataFrame()
    
    def _calculate_statistics(
        self,
        unit_id: str,
        client: str,
        equipment_model: str,
        signal_name: str,
        system: str,
        operational_state: str,
        values: pd.Series,
        week_start: datetime,
        week_end: datetime,
        total_minutes: int,
    ) -> Dict[str, Any]:
        """
        Calculate weekly statistics for signal.
        
        Parameters
        ----------
        unit_id : str
            Equipment identifier
        client : str
            Client identifier
        equipment_model : str
            Equipment model
        signal_name : str
            Signal name
        system : str
            System name
        operational_state : str
            Operational state
        values : pd.Series
            Signal values
        week_start : datetime
            Week start
        week_end : datetime
            Week end
        total_minutes : int
            Total minutes in state
        
        Returns
        -------
        Dict[str, Any]
            Statistics dictionary
        """
        # Calculate ISO week number
        iso_year, iso_week, _ = week_start.isocalendar()
        
        # Basic statistics
        stats = {
            'unit_id': unit_id,
            'client': client,
            'equipment_model': equipment_model,
            'signal_name': signal_name,
            'system': system,
            'operational_state': operational_state,
            'week_start': week_start,
            'week_end': week_end,
            'iso_year': iso_year,
            'iso_week': iso_week,
            'sample_count': int(len(values)),
            'total_minutes_in_state': int(total_minutes),
            'coverage': float(len(values) / total_minutes) if total_minutes > 0 else 0.0,
            'mean': float(values.mean()),
            'median': float(values.median()),
            'std': float(values.std()),
            'min': float(values.min()),
            'max': float(values.max()),
            'p5': float(values.quantile(0.05)),
            'p25': float(values.quantile(0.25)),
            'p75': float(values.quantile(0.75)),
            'p95': float(values.quantile(0.95)),
            'p99': float(values.quantile(0.99)),
        }
        
        return stats
    
    def _calculate_abnormal_pct(
        self,
        values: pd.Series,
        baseline: Dict[str, Any],
        risk_direction: str,
    ) -> float:
        """
        Calculate percentage of abnormal values.
        
        Parameters
        ----------
        values : pd.Series
            Signal values
        baseline : Dict[str, Any]
            Baseline statistics
        risk_direction : str
            "high", "low", or "both"
        
        Returns
        -------
        float
            Percentage of abnormal values (0-100)
        """
        p5 = baseline.get('p5', 0)
        p95 = baseline.get('p95', 100)
        
        if risk_direction == "high":
            abnormal_count = (values > p95).sum()
        elif risk_direction == "low":
            abnormal_count = (values < p5).sum()
        else:  # "both"
            abnormal_count = ((values > p95) | (values < p5)).sum()
        
        return (abnormal_count / len(values)) * 100 if len(values) > 0 else 0.0
    
    def write_aggregates(
        self,
        agg_df: pd.DataFrame,
        week_start: datetime,
    ) -> None:
        """
        Write weekly aggregates to partitioned Parquet.
        
        Parameters
        ----------
        agg_df : pd.DataFrame
            Aggregates dataframe
        week_start : datetime
            Week start date for partitioning
        """
        if len(agg_df) == 0:
            self.logger.warning("No aggregates to write")
            return
        
        # Get ISO week
        iso_year, iso_week, _ = week_start.isocalendar()
        
        # Build partition path
        partition_path = (
            self.output_dir /
            f"year={iso_year}" /
            f"week={iso_week:02d}"
        )
        partition_path.mkdir(parents=True, exist_ok=True)
        
        # Write to Parquet
        output_file = partition_path / f"weekly_aggregates_{iso_year}W{iso_week:02d}.parquet"
        agg_df.to_parquet(output_file, index=False, compression="snappy")
        
        self.logger.info(
            f"Wrote {len(agg_df)} weekly aggregates to {output_file.relative_to(self.output_dir.parent.parent)}"
        )
    
    def load_aggregates(
        self,
        unit_id: str,
        signal_name: str,
        lookback_weeks: int,
        reference_date: datetime,
    ) -> pd.DataFrame:
        """
        Load historical weekly aggregates for trend analysis.
        
        Parameters
        ----------
        unit_id : str
            Equipment identifier
        signal_name : str
            Signal name
        lookback_weeks : int
            Number of weeks to load (4, 8, or 12)
        reference_date : datetime
            Reference date (end of lookback window)
        
        Returns
        -------
        pd.DataFrame
            Historical aggregates
        """
        # Calculate date range
        start_date = reference_date - timedelta(weeks=lookback_weeks)
        
        # Load all relevant partitions
        aggregates = []
        
        current_date = start_date
        while current_date <= reference_date:
            iso_year, iso_week, _ = current_date.isocalendar()
            
            partition_path = (
                self.output_dir /
                f"year={iso_year}" /
                f"week={iso_week:02d}"
            )
            
            if partition_path.exists():
                # Load all parquet files in partition
                for file_path in partition_path.glob("*.parquet"):
                    try:
                        df = pd.read_parquet(file_path)
                        aggregates.append(df)
                    except Exception as e:
                        self.logger.warning(f"Failed to load {file_path}: {e}")
            
            current_date += timedelta(weeks=1)
        
        if not aggregates:
            return pd.DataFrame()
        
        # Combine and filter
        agg_df = pd.concat(aggregates, ignore_index=True)
        agg_df = agg_df[
            (agg_df['unit_id'] == unit_id) &
            (agg_df['signal_name'] == signal_name) &
            (agg_df['week_start'] >= start_date) &
            (agg_df['week_start'] <= reference_date)
        ]
        
        return agg_df.sort_values('week_start').reset_index(drop=True)
