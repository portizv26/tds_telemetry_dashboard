"""
Threshold Deviation Technique.

Detects repeated limit violations by comparing signal values against
state-specific baseline percentiles (P1, P5, P95, P99).

Methodology
-----------
1. Load 24-hour evaluation window
2. Filter to valid operational states
3. Retrieve state-matched baseline
4. Calculate exceedance percentages (% time exceeding limits)
5. Calculate deviation magnitudes
6. Normalize to risk score (0-100)
7. Calculate confidence from data quality

Daily execution: Evaluates previous 24 hours
Weekly summary: Aggregates 7 days of daily results
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path

from src.techniques.base import BaseTechnique
from src.models.entities import TechniqueResult, EvaluationWindow
from src.config.signal_registry import SignalRegistry
from src.baselines.baseline_manager import BaselineManager
from src.scoring.normalization import normalize_threshold_deviation
from src.scoring.confidence import calculate_confidence_score


class ThresholdDeviation(BaseTechnique):
    """
    Threshold deviation detection technique.
    
    Analyzes whether signals repeatedly exceed baseline percentiles,
    indicating sustained abnormal behavior.
    
    Parameters
    ----------
    signal_registry : SignalRegistry
        Signal metadata registry
    baseline_manager : BaselineManager
        Baseline retrieval manager
    output_dir : Path
        Directory for technique results
    """
    
    def __init__(
        self,
        signal_registry: SignalRegistry,
        baseline_manager: BaselineManager,
        output_dir: Path,
    ):
        super().__init__(
            technique_name="threshold_deviation",
            technique_version="1.0.0",
            validity_period_days=2,  # Daily results valid for 2 days
            signal_registry=signal_registry,
            baseline_manager=baseline_manager,
            output_dir=output_dir,
        )
    
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
        Execute threshold deviation analysis.
        
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
            
            # Extract signal values
            if signal_name not in window_df.columns:
                self.logger.error(f"Signal {signal_name} not in dataframe columns")
                return None
            
            values = window_df[signal_name].dropna()
            
            if len(values) == 0:
                self.logger.warning(f"All values null for {unit_id}/{signal_name}")
                return None
            
            # Calculate exceedances and deviations
            evidence = self._calculate_evidence(
                values=values,
                baseline=baseline,
                risk_direction=signal_meta['risk_direction'],
            )
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(evidence)
            
            # Calculate confidence score
            expected_samples = int((window.end - window.start).total_seconds() / 60)  # 1 sample/minute
            confidence_score = self._calculate_confidence_score(
                data_df=window_df[[signal_name]],
                baseline=baseline,
            )
            confidence_score = calculate_confidence_score(
                data_df=window_df[[signal_name]],
                expected_samples=expected_samples,
                baseline=baseline,
                state_matched=True,
            )
            
            # Classify status
            status = self._classify_status(risk_score, confidence_score)
            
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
                f"Threshold deviation failed for {unit_id}/{signal_name}: {e}",
                exc_info=True
            )
            return None
    
    def _calculate_evidence(
        self,
        values: pd.Series,
        baseline: Dict[str, Any],
        risk_direction: str,
    ) -> Dict[str, Any]:
        """
        Calculate threshold deviation evidence.
        
        Parameters
        ----------
        values : pd.Series
            Signal values in evaluation window
        baseline : Dict[str, Any]
            Baseline statistics
        risk_direction : str
            "high", "low", or "both"
        
        Returns
        -------
        Dict[str, Any]
            Evidence dictionary with exceedances and deviations
        """
        # Extract baseline percentiles
        p1 = baseline.get('p1', 0)
        p5 = baseline.get('p5', 0)
        p50 = baseline.get('p50', 0)
        p95 = baseline.get('p95', 100)
        p99 = baseline.get('p99', 100)
        
        # Calculate exceedances based on risk direction
        if risk_direction == "high":
            # High values are risk
            exceedance_p95 = (values > p95).sum()
            exceedance_p99 = (values > p99).sum()
            exceedance_p95_pct = (exceedance_p95 / len(values)) * 100
            exceedance_p99_pct = (exceedance_p99 / len(values)) * 100
            
            # Deviation magnitude
            exceeding_values = values[values > p95]
            if len(exceeding_values) > 0:
                max_deviation = (exceeding_values.max() - p95)
                mean_deviation = (exceeding_values.mean() - p95)
            else:
                max_deviation = 0
                mean_deviation = 0
        
        elif risk_direction == "low":
            # Low values are risk
            exceedance_p95 = (values < p5).sum()
            exceedance_p99 = (values < p1).sum()
            exceedance_p95_pct = (exceedance_p95 / len(values)) * 100
            exceedance_p99_pct = (exceedance_p99 / len(values)) * 100
            
            # Deviation magnitude
            exceeding_values = values[values < p5]
            if len(exceeding_values) > 0:
                max_deviation = (p5 - exceeding_values.min())
                mean_deviation = (p5 - exceeding_values.mean())
            else:
                max_deviation = 0
                mean_deviation = 0
        
        else:  # "both"
            # Either extreme is risk
            exceedance_p95_high = (values > p95).sum()
            exceedance_p95_low = (values < p5).sum()
            exceedance_p95 = exceedance_p95_high + exceedance_p95_low
            
            exceedance_p99_high = (values > p99).sum()
            exceedance_p99_low = (values < p1).sum()
            exceedance_p99 = exceedance_p99_high + exceedance_p99_low
            
            exceedance_p95_pct = (exceedance_p95 / len(values)) * 100
            exceedance_p99_pct = (exceedance_p99 / len(values)) * 100
            
            # Deviation magnitude (max of both directions)
            high_exceeding = values[values > p95]
            low_exceeding = values[values < p5]
            
            if len(high_exceeding) > 0:
                max_dev_high = (high_exceeding.max() - p95)
                mean_dev_high = (high_exceeding.mean() - p95)
            else:
                max_dev_high = 0
                mean_dev_high = 0
            
            if len(low_exceeding) > 0:
                max_dev_low = (p5 - low_exceeding.min())
                mean_dev_low = (p5 - low_exceeding.mean())
            else:
                max_dev_low = 0
                mean_dev_low = 0
            
            max_deviation = max(max_dev_high, max_dev_low)
            mean_deviation = max(mean_dev_high, mean_dev_low)
        
        # Build evidence dictionary
        evidence = {
            "baseline_p1": float(p1),
            "baseline_p5": float(p5),
            "baseline_p50": float(p50),
            "baseline_p95": float(p95),
            "baseline_p99": float(p99),
            "exceedance_p95_count": int(exceedance_p95),
            "exceedance_p99_count": int(exceedance_p99),
            "exceedance_p95_pct": float(exceedance_p95_pct),
            "exceedance_p99_pct": float(exceedance_p99_pct),
            "max_deviation": float(max_deviation),
            "mean_deviation": float(mean_deviation),
            "sample_count": int(len(values)),
            "min_value": float(values.min()),
            "max_value": float(values.max()),
            "mean_value": float(values.mean()),
            "median_value": float(values.median()),
            "std_value": float(values.std()),
        }
        
        return evidence
    
    def _calculate_risk_score(self, evidence: Dict[str, Any]) -> float:
        """
        Convert threshold deviation evidence to risk score (0-100).
        
        Parameters
        ----------
        evidence : Dict[str, Any]
            Evidence dictionary
        
        Returns
        -------
        float
            Risk score (0-100)
        """
        return normalize_threshold_deviation(
            exceedance_p95_pct=evidence['exceedance_p95_pct'],
            exceedance_p99_pct=evidence['exceedance_p99_pct'],
            max_deviation=evidence['max_deviation'],
            mean_deviation=evidence['mean_deviation'],
        )
    
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
        # Use utility function
        expected_samples = 24 * 60  # 24 hours * 60 minutes
        return calculate_confidence_score(
            data_df=data_df,
            expected_samples=expected_samples,
            baseline=baseline,
            state_matched=True,
        )
