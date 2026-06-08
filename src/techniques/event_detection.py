"""
Event Detection Technique.

Identifies persistent abnormal episodes by grouping consecutive minutes
where signals exceed baseline thresholds.

Methodology
-----------
1. Load 24-hour evaluation window
2. Identify abnormal minutes (exceeding P95/P99 or below P1/P5)
3. Group consecutive abnormal minutes into events
4. Merge events with gaps <5 minutes
5. Classify events by duration (spike/episode/sustained)
6. Calculate event severity scores
7. Store individual events and generate technique result

Event Types
-----------
- Spike: <5 minutes
- Episode: 5-60 minutes
- Sustained: >60 minutes
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path

from src.techniques.base import BaseTechnique
from src.models.entities import TechniqueResult, EvaluationWindow
from src.models.events import Event
from src.config.signal_registry import SignalRegistry
from src.baselines.baseline_manager import BaselineManager
from src.scoring.normalization import normalize_event_severity
from src.scoring.confidence import calculate_event_confidence


class EventDetection(BaseTechnique):
    """
    Event detection technique.
    
    Detects and classifies abnormal episodes in telemetry data.
    
    Parameters
    ----------
    signal_registry : SignalRegistry
        Signal metadata registry
    baseline_manager : BaselineManager
        Baseline retrieval manager
    output_dir : Path
        Directory for technique results
    events_dir : Path
        Directory for event records
    merge_gap_minutes : int
        Maximum gap to merge events (default 5)
    """
    
    def __init__(
        self,
        signal_registry: SignalRegistry,
        baseline_manager: BaselineManager,
        output_dir: Path,
        events_dir: Path,
        merge_gap_minutes: int = 5,
    ):
        super().__init__(
            technique_name="event_detection",
            technique_version="1.0.0",
            validity_period_days=2,  # Daily results valid for 2 days
            signal_registry=signal_registry,
            baseline_manager=baseline_manager,
            output_dir=output_dir,
        )
        self.events_dir = events_dir
        self.merge_gap_minutes = merge_gap_minutes
        
        # Ensure events directory exists
        self.events_dir.mkdir(parents=True, exist_ok=True)
    
    def evaluate(
        self,
        unit_id: str,
        client: str,
        equipment_model: str,
        signal_name: str,
        window: EvaluationWindow,
        silver_df: pd.DataFrame,
    ) -> Optional[TechniqueResult]:
        """
        Execute event detection analysis.
        
        Parameters
        ----------
        unit_id : str
            Equipment identifier
        client : str
            Client identifier
        equipment_model : str
            Equipment model
        signal_name : str
            Signal to evaluate
        window : EvaluationWindow
            Temporal evaluation window (24h for daily)
        silver_df : pd.DataFrame
            Silver layer telemetry data
        
        Returns
        -------
        Optional[TechniqueResult]
            Result object or None if evaluation failed
        """
        try:
            # Get signal metadata
            signal_meta = self._get_signal_metadata(signal_name)
            if not signal_meta:
                self.logger.warning(f"Signal {signal_name} not in registry, skipping")
                return None
            
            # Filter to evaluation window
            window_df = silver_df[
                (silver_df['Fecha'] >= window.start) &
                (silver_df['Fecha'] <= window.end)
            ].copy()
            
            if len(window_df) == 0:
                self.logger.warning(
                    f"No data for {unit_id}/{signal_name} in window {window.start} to {window.end}"
                )
                return None
            
            # Filter to valid operational states
            window_df = self._filter_by_operational_state(window_df, signal_name)
            
            if len(window_df) == 0:
                self.logger.warning(
                    f"No data after state filter for {unit_id}/{signal_name}"
                )
                return None
            
            # Get primary operational state
            primary_state = window_df['EstadoMaquina'].mode()[0] if 'EstadoMaquina' in window_df.columns else 'Operacional'
            
            # Retrieve baseline
            baseline = self.baseline_manager.get_baseline(
                client=client,
                equipment_model=equipment_model,
                unit_id=unit_id,
                signal_name=signal_name,
                operational_state=primary_state,
            )
            
            if baseline is None:
                self.logger.warning(
                    f"No baseline for {unit_id}/{signal_name}/{primary_state}"
                )
                return None
            
            # Detect abnormal minutes
            window_df = self._mark_abnormal_minutes(
                df=window_df,
                signal_name=signal_name,
                baseline=baseline,
                risk_direction=signal_meta['risk_direction'],
            )
            
            # Group into events
            events = self._group_into_events(
                df=window_df,
                signal_name=signal_name,
                unit_id=unit_id,
                client=client,
                equipment_model=equipment_model,
                system=signal_meta['system'],
                baseline=baseline,
            )
            
            # Calculate aggregate evidence
            evidence = self._calculate_evidence(events, baseline)
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(evidence)
            
            # Calculate confidence score
            baseline_quality = baseline.get('quality_score', 0.7)
            data_coverage = len(window_df) / (24 * 60)  # Expected 1 sample/minute
            confidence_score = evidence.get('avg_event_confidence', 80.0)
            
            # Classify status
            status = self._classify_status(risk_score, confidence_score)
            
            # Write events to storage
            if events:
                self._write_events(events, window.end)
            
            # Create result
            result = TechniqueResult(
                technique_name=self.technique_name,
                technique_version=self.technique_version,
                evaluation_timestamp=datetime.utcnow(),
                evaluation_window_start=window.start,
                evaluation_window_end=window.end,
                unit_id=unit_id,
                client=client,
                equipment_model=equipment_model,
                signal_name=signal_name,
                system=signal_meta['system'],
                risk_score=risk_score,
                confidence_score=confidence_score,
                status=status,
                validity_period_days=self.validity_period_days,
                baseline_version=baseline.get('baseline_version'),
                evidence=evidence,
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                f"Event detection failed for {unit_id}/{signal_name}: {e}",
                exc_info=True
            )
            return None
    
    def _mark_abnormal_minutes(
        self,
        df: pd.DataFrame,
        signal_name: str,
        baseline: Dict[str, Any],
        risk_direction: str,
    ) -> pd.DataFrame:
        """
        Mark abnormal minutes based on baseline exceedance.
        
        Parameters
        ----------
        df : pd.DataFrame
            Window dataframe
        signal_name : str
            Signal name
        baseline : Dict[str, Any]
            Baseline statistics
        risk_direction : str
            "high", "low", or "both"
        
        Returns
        -------
        pd.DataFrame
            Dataframe with 'is_abnormal' column
        """
        p1 = baseline.get('p1', 0)
        p5 = baseline.get('p5', 0)
        p95 = baseline.get('p95', 100)
        p99 = baseline.get('p99', 100)
        
        values = df[signal_name]
        
        if risk_direction == "high":
            df['is_abnormal'] = values > p95
        elif risk_direction == "low":
            df['is_abnormal'] = values < p5
        else:  # "both"
            df['is_abnormal'] = (values > p95) | (values < p5)
        
        return df
    
    def _group_into_events(
        self,
        df: pd.DataFrame,
        signal_name: str,
        unit_id: str,
        client: str,
        equipment_model: str,
        system: str,
        baseline: Dict[str, Any],
    ) -> List[Event]:
        """
        Group consecutive abnormal minutes into events.
        
        Parameters
        ----------
        df : pd.DataFrame
            Dataframe with 'is_abnormal' column
        signal_name : str
            Signal name
        unit_id : str
            Unit identifier
        client : str
            Client identifier
        equipment_model : str
            Equipment model
        system : str
            System name
        baseline : Dict[str, Any]
            Baseline statistics
        
        Returns
        -------
        List[Event]
            List of detected events
        """
        events = []
        
        # Find runs of consecutive abnormal minutes
        df = df.sort_values('Fecha').reset_index(drop=True)
        df['group'] = (df['is_abnormal'] != df['is_abnormal'].shift()).cumsum()
        
        # Process each abnormal group
        for group_id, group_df in df.groupby('group'):
            if not group_df['is_abnormal'].iloc[0]:
                continue  # Skip normal groups
            
            # Check duration
            event_start = group_df['Fecha'].min()
            event_end = group_df['Fecha'].max()
            duration_minutes = int((event_end - event_start).total_seconds() / 60) + 1
            
            # Merge check: if gap to previous event is small, extend previous event
            if events and (event_start - events[-1].event_end).total_seconds() / 60 <= self.merge_gap_minutes:
                # Extend previous event
                events[-1].event_end = event_end
                events[-1].duration_minutes = int(
                    (events[-1].event_end - events[-1].event_start).total_seconds() / 60
                ) + 1
                
                # Recalculate statistics
                all_values = pd.concat([
                    df[(df['Fecha'] >= events[-1].event_start) & (df['Fecha'] <= events[-1].event_end)][signal_name]
                ])
                events[-1].max_value = float(all_values.max())
                events[-1].min_value = float(all_values.min())
                events[-1].mean_value = float(all_values.mean())
                
                continue
            
            # Classify event type
            if duration_minutes < 5:
                event_type = "spike"
            elif duration_minutes <= 60:
                event_type = "episode"
            else:
                event_type = "sustained"
            
            # Calculate event statistics
            values = group_df[signal_name].dropna()
            if len(values) == 0:
                continue
            
            max_value = float(values.max())
            min_value = float(values.min())
            mean_value = float(values.mean())
            
            # Calculate deviation from baseline
            p50 = baseline.get('p50', mean_value)
            p95 = baseline.get('p95', max_value)
            p5 = baseline.get('p5', min_value)
            
            if mean_value > p50:
                deviation_pct = ((mean_value - p50) / p50) * 100 if p50 > 0 else 0
            else:
                deviation_pct = ((p50 - mean_value) / p50) * 100 if p50 > 0 else 0
            
            # Calculate severity
            severity_score = normalize_event_severity(
                duration_minutes=duration_minutes,
                deviation_from_baseline=abs(deviation_pct),
                event_type=event_type,
            )
            
            # Get operational state
            operational_state = group_df['EstadoMaquina'].mode()[0] if 'EstadoMaquina' in group_df.columns else 'Operacional'
            
            # Create event
            event = Event(
                unit_id=unit_id,
                client=client,
                equipment_model=equipment_model,
                signal_name=signal_name,
                system=system,
                event_start=event_start,
                event_end=event_end,
                duration_minutes=duration_minutes,
                event_type=event_type,
                max_value=max_value,
                min_value=min_value,
                mean_value=mean_value,
                baseline_p95=float(p95),
                baseline_p5=float(p5),
                severity_score=severity_score,
                operational_state=operational_state,
            )
            
            events.append(event)
        
        return events
    
    def _calculate_evidence(
        self,
        events: List[Event],
        baseline: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculate aggregate evidence from events.
        
        Parameters
        ----------
        events : List[Event]
            Detected events
        baseline : Dict[str, Any]
            Baseline statistics
        
        Returns
        -------
        Dict[str, Any]
            Evidence dictionary
        """
        if not events:
            return {
                "event_count": 0,
                "total_abnormal_minutes": 0,
                "max_event_duration": 0,
                "avg_event_duration": 0,
                "max_severity": 0,
                "avg_severity": 0,
                "event_types": {},
                "avg_event_confidence": 80.0,
            }
        
        # Aggregate statistics
        total_minutes = sum(e.duration_minutes for e in events)
        max_duration = max(e.duration_minutes for e in events)
        avg_duration = total_minutes / len(events)
        max_severity = max(e.severity_score for e in events)
        avg_severity = sum(e.severity_score for e in events) / len(events)
        
        # Event type distribution
        event_types = {}
        for event in events:
            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
        
        # Calculate average event confidence
        baseline_quality = baseline.get('quality_score', 0.7)
        avg_confidence = sum(
            calculate_event_confidence(
                event_duration_minutes=e.duration_minutes,
                baseline_quality=baseline_quality,
                data_coverage=0.9,  # Assume good coverage if we detected events
            ) for e in events
        ) / len(events)
        
        evidence = {
            "event_count": len(events),
            "total_abnormal_minutes": int(total_minutes),
            "max_event_duration": int(max_duration),
            "avg_event_duration": float(avg_duration),
            "max_severity": float(max_severity),
            "avg_severity": float(avg_severity),
            "event_types": event_types,
            "spike_count": event_types.get("spike", 0),
            "episode_count": event_types.get("episode", 0),
            "sustained_count": event_types.get("sustained", 0),
            "avg_event_confidence": float(avg_confidence),
        }
        
        return evidence
    
    def _calculate_risk_score(self, evidence: Dict[str, Any]) -> float:
        """
        Convert event evidence to risk score (0-100).
        
        Parameters
        ----------
        evidence : Dict[str, Any]
            Evidence dictionary
        
        Returns
        -------
        float
            Risk score (0-100)
        """
        if evidence['event_count'] == 0:
            return 0.0
        
        # Use max severity as base
        base_score = evidence['max_severity']
        
        # Boost for multiple events (persistence)
        event_count = evidence['event_count']
        if event_count > 1:
            persistence_boost = min((event_count - 1) * 5, 20)  # Max +20
            base_score += persistence_boost
        
        # Boost for sustained events
        if evidence['sustained_count'] > 0:
            base_score += 10
        
        # Cap at 100
        return min(base_score, 100.0)
    
    def _calculate_confidence_score(
        self,
        data_df: pd.DataFrame,
        baseline: Optional[Dict[str, Any]],
    ) -> float:
        """
        Calculate confidence score based on data quality.
        
        Parameters
        ----------
        data_df : pd.DataFrame
            Analysis window data
        baseline : Optional[Dict[str, Any]]
            Baseline statistics
        
        Returns
        -------
        float
            Confidence score (0-100)
        """
        # For event detection, confidence comes from individual events
        # Placeholder if needed
        return 80.0
    
    def _write_events(self, events: List[Event], evaluation_date: datetime) -> None:
        """
        Write events to partitioned Parquet.
        
        Parameters
        ----------
        events : List[Event]
            Events to write
        evaluation_date : datetime
            Evaluation date for partitioning
        """
        if not events:
            return
        
        # Convert to DataFrame
        df = pd.DataFrame([e.to_dict() for e in events])
        
        # Build partition path (year/month/day)
        partition_path = (
            self.events_dir /
            f"year={evaluation_date.year}" /
            f"month={evaluation_date.month:02d}" /
            f"day={evaluation_date.day:02d}"
        )
        partition_path.mkdir(parents=True, exist_ok=True)
        
        # Write to Parquet
        output_file = partition_path / f"events_{evaluation_date.strftime('%Y%m%d')}.parquet"
        df.to_parquet(output_file, index=False, compression="snappy")
        
        self.logger.info(
            f"Wrote {len(events)} events to {output_file.relative_to(self.events_dir.parent.parent)}"
        )
