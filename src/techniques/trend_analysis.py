"""
Trend Analysis Technique.

Detects progressive degradation by analyzing trends in weekly signal aggregates
over 4-week, 8-week, and 12-week lookback windows.

Methodology
-----------
1. Load weekly aggregates for lookback period (4, 8, or 12 weeks)
2. Fit linear regression to weekly statistics (mean, P95, etc.)
3. Calculate trend slope, R², and p-value
4. Calculate percent change from baseline
5. Assess statistical significance (p < 0.05)
6. Normalize to risk score (0-100)
7. Calculate confidence from data quality and trend strength

Trend Windows
-------------
- 4-week: Recent changes, more volatile
- 8-week: Medium-term trends, balanced
- 12-week: Long-term trends, more stable
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

from src.techniques.base import BaseTechnique
from src.techniques.weekly_aggregator import WeeklyAggregator
from src.models.entities import TechniqueResult, EvaluationWindow
from src.config.signal_registry import SignalRegistry
from src.baselines.baseline_manager import BaselineManager
from src.scoring.normalization import normalize_trend_slope
from src.scoring.confidence import calculate_trend_confidence


class TrendAnalysis(BaseTechnique):
    """
    Trend analysis technique.
    
    Detects progressive degradation through regression analysis
    of weekly signal aggregates.
    
    Parameters
    ----------
    signal_registry : SignalRegistry
        Signal metadata registry
    baseline_manager : BaselineManager
        Baseline retrieval manager
    output_dir : Path
        Directory for technique results
    weekly_aggregator : WeeklyAggregator
        Weekly aggregates loader
    lookback_weeks : int
        Number of weeks to analyze (4, 8, or 12)
    """
    
    def __init__(
        self,
        signal_registry: SignalRegistry,
        baseline_manager: BaselineManager,
        output_dir: Path,
        weekly_aggregator: WeeklyAggregator,
        lookback_weeks: int = 8,
    ):
        super().__init__(
            technique_name="trend_analysis",
            technique_version="1.0.0",
            validity_period_days=lookback_weeks * 7 // 2,  # Half the lookback period
            signal_registry=signal_registry,
            baseline_manager=baseline_manager,
            output_dir=output_dir,
        )
        self.weekly_aggregator = weekly_aggregator
        self.lookback_weeks = lookback_weeks
    
    def evaluate(
        self,
        unit_id: str,
        client: str,
        equipment_model: str,
        signal_name: str,
        window: EvaluationWindow,
        silver_df: pd.DataFrame = None,  # Not used, data from weekly aggregates
    ) -> Optional[TechniqueResult]:
        """
        Execute trend analysis.
        
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
            Temporal evaluation window
        silver_df : pd.DataFrame
            Not used (data comes from weekly aggregates)
        
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
            
            # Load weekly aggregates
            agg_df = self.weekly_aggregator.load_aggregates(
                unit_id=unit_id,
                signal_name=signal_name,
                lookback_weeks=self.lookback_weeks,
                reference_date=window.end,
            )
            
            if len(agg_df) < 3:  # Need at least 3 weeks for regression
                self.logger.warning(
                    f"Insufficient weeks for {unit_id}/{signal_name}: {len(agg_df)} < 3"
                )
                return None
            
            # Get primary operational state
            primary_state = agg_df['operational_state'].mode()[0] if len(agg_df) > 0 else 'Operacional'
            
            # Filter to primary state
            state_df = agg_df[agg_df['operational_state'] == primary_state].copy()
            
            if len(state_df) < 3:
                self.logger.warning(
                    f"Insufficient weeks after state filter for {unit_id}/{signal_name}"
                )
                return None
            
            # Retrieve baseline for comparison
            baseline = self.baseline_manager.get_baseline(
                client=client,
                equipment_model=equipment_model,
                unit_id=unit_id,
                signal_name=signal_name,
                operational_state=primary_state,
            )
            
            # Perform trend analysis on multiple metrics
            evidence = self._calculate_evidence(
                agg_df=state_df,
                baseline=baseline,
                risk_direction=signal_meta['risk_direction'],
            )
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(evidence)
            
            # Calculate confidence score
            confidence_score = calculate_trend_confidence(
                valid_weeks=evidence['valid_weeks'],
                required_weeks=self.lookback_weeks,
                r_squared=evidence['r_squared'],
                p_value=evidence['p_value'],
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
                baseline_version=baseline.get('baseline_version') if baseline else None,
                evidence=evidence,
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                f"Trend analysis failed for {unit_id}/{signal_name}: {e}",
                exc_info=True
            )
            return None
    
    def _calculate_evidence(
        self,
        agg_df: pd.DataFrame,
        baseline: Optional[Dict[str, Any]],
        risk_direction: str,
    ) -> Dict[str, Any]:
        """
        Calculate trend evidence through regression analysis.
        
        Parameters
        ----------
        agg_df : pd.DataFrame
            Weekly aggregates
        baseline : Optional[Dict[str, Any]]
            Baseline statistics
        risk_direction : str
            "high", "low", or "both"
        
        Returns
        -------
        Dict[str, Any]
            Evidence dictionary with regression results
        """
        # Prepare time series (week index as x)
        agg_df = agg_df.sort_values('week_start').reset_index(drop=True)
        agg_df['week_index'] = range(len(agg_df))
        
        # Perform regression on mean values
        x = agg_df['week_index'].values
        y_mean = agg_df['mean'].values
        
        slope_mean, intercept_mean, r_value_mean, p_value_mean, std_err_mean = stats.linregress(x, y_mean)
        
        # Perform regression on P95 values
        y_p95 = agg_df['p95'].values
        slope_p95, intercept_p95, r_value_p95, p_value_p95, std_err_p95 = stats.linregress(x, y_p95)
        
        # Calculate percent change
        if len(y_mean) > 0 and y_mean[0] != 0:
            percent_change_mean = ((y_mean[-1] - y_mean[0]) / abs(y_mean[0])) * 100
        else:
            percent_change_mean = 0.0
        
        if len(y_p95) > 0 and y_p95[0] != 0:
            percent_change_p95 = ((y_p95[-1] - y_p95[0]) / abs(y_p95[0])) * 100
        else:
            percent_change_p95 = 0.0
        
        # Compare to baseline
        if baseline:
            baseline_mean = baseline.get('mean', 0)
            baseline_p95 = baseline.get('p95', 0)
            
            current_mean = y_mean[-1]
            current_p95 = y_p95[-1]
            
            if baseline_mean != 0:
                delta_from_baseline_mean = ((current_mean - baseline_mean) / abs(baseline_mean)) * 100
            else:
                delta_from_baseline_mean = 0.0
            
            if baseline_p95 != 0:
                delta_from_baseline_p95 = ((current_p95 - baseline_p95) / abs(baseline_p95)) * 100
            else:
                delta_from_baseline_p95 = 0.0
        else:
            delta_from_baseline_mean = 0.0
            delta_from_baseline_p95 = 0.0
        
        # Classify trend direction
        if abs(slope_mean) < 0.01:
            trend_direction = "stable"
        elif slope_mean > 0:
            trend_direction = "increasing"
        else:
            trend_direction = "decreasing"
        
        # Build evidence
        evidence = {
            "lookback_weeks": int(self.lookback_weeks),
            "valid_weeks": int(len(agg_df)),
            "regression_method": "linear",
            # Mean trend
            "slope": float(slope_mean),
            "intercept": float(intercept_mean),
            "r_squared": float(r_value_mean ** 2),
            "p_value": float(p_value_mean),
            "percent_change": float(percent_change_mean),
            "delta_from_baseline": float(delta_from_baseline_mean),
            # P95 trend
            "slope_p95": float(slope_p95),
            "r_squared_p95": float(r_value_p95 ** 2),
            "p_value_p95": float(p_value_p95),
            "percent_change_p95": float(percent_change_p95),
            "delta_from_baseline_p95": float(delta_from_baseline_p95),
            # Classification
            "trend_direction": trend_direction,
            "is_significant": bool(p_value_mean < 0.05),
            # Time series data (first/last for reference)
            "first_week_mean": float(y_mean[0]),
            "last_week_mean": float(y_mean[-1]),
            "first_week_p95": float(y_p95[0]),
            "last_week_p95": float(y_p95[-1]),
        }
        
        return evidence
    
    def _calculate_risk_score(self, evidence: Dict[str, Any]) -> float:
        """
        Convert trend evidence to risk score (0-100).
        
        Parameters
        ----------
        evidence : Dict[str, Any]
            Evidence dictionary
        
        Returns
        -------
        float
            Risk score (0-100)
        """
        # Get signal metadata for risk direction
        signal_meta = self._get_signal_metadata(evidence.get('signal_name', ''))
        risk_direction = signal_meta.get('risk_direction', 'high') if signal_meta else 'high'
        
        # Use normalization function
        return normalize_trend_slope(
            slope=evidence['slope'],
            r_squared=evidence['r_squared'],
            p_value=evidence['p_value'],
            percent_change=evidence['percent_change'],
            risk_direction=risk_direction,
        )
    
    def _calculate_confidence_score(
        self,
        data_df: pd.DataFrame,
        baseline: Optional[Dict[str, Any]],
    ) -> float:
        """
        Calculate confidence score based on trend strength.
        
        Parameters
        ----------
        data_df : pd.DataFrame
            Weekly aggregates
        baseline : Optional[Dict[str, Any]]
            Baseline statistics
        
        Returns
        -------
        float
            Confidence score (0-100)
        """
        # Confidence calculated in evaluate() using calculate_trend_confidence
        # This is a placeholder to satisfy abstract method
        return 80.0
