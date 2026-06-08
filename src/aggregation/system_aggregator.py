"""
System-Level Health Aggregator.

Aggregates signal-level technique results into system-level health scores
(Engine, Transmission, Brakes, Drive, Steering, Electrical).

Methodology
-----------
1. Load all recent technique results for unit
2. Filter by system (using signal-to-system mapping)
3. Apply signal criticality weights
4. Apply time-decay weighting (recent results weighted higher)
5. Apply technique diversity bonus (3+ techniques = +10%)
6. Apply persistence bonus (3+ consecutive abnormal = +15%)
7. Calculate weighted mean risk score
8. Calculate confidence (harmonic mean)
9. Identify top 3 contributing signals

System Criticality Weights
---------------------------
- Engine: 3.0 (highest criticality)
- Transmission: 2.5
- Brakes: 2.0
- Drive: 1.8
- Steering: 1.5
- Electrical: 1.2
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path

from src.models.entities import SystemHealth, TechniqueResult
from src.config.signal_registry import SignalRegistry
from src.utils.logger import get_logger


class SystemAggregator:
    """
    Aggregates signal-level results into system-level health scores.
    
    Parameters
    ----------
    signal_registry : SignalRegistry
        Signal metadata registry
    output_dir : Path
        Directory for system health outputs
    system_criticality_weights : Optional[Dict[str, float]]
        System criticality multipliers (default: Engine=3.0, Transmission=2.5, etc.)
    time_decay_lambda : float
        Exponential decay factor for time weighting (default: 0.3)
    diversity_bonus : float
        Bonus for multiple techniques (default: 0.10 = 10%)
    persistence_bonus : float
        Bonus for repeated abnormal findings (default: 0.15 = 15%)
    """
    
    # Default system criticality weights
    DEFAULT_SYSTEM_WEIGHTS = {
        "Engine": 3.0,
        "Transmission": 2.5,
        "Brakes": 2.0,
        "Drive": 1.8,
        "Steering": 1.5,
        "Electrical": 1.2,
    }
    
    def __init__(
        self,
        signal_registry: SignalRegistry,
        output_dir: Path,
        system_criticality_weights: Optional[Dict[str, float]] = None,
        time_decay_lambda: float = 0.3,
        diversity_bonus: float = 0.10,
        persistence_bonus: float = 0.15,
    ):
        self.signal_registry = signal_registry
        self.output_dir = output_dir
        self.system_weights = system_criticality_weights or self.DEFAULT_SYSTEM_WEIGHTS
        self.time_decay_lambda = time_decay_lambda
        self.diversity_bonus = diversity_bonus
        self.persistence_bonus = persistence_bonus
        self.logger = get_logger("system_aggregator")
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def aggregate_system_health(
        self,
        unit_id: str,
        client: str,
        equipment_model: str,
        system: str,
        technique_results: List[TechniqueResult],
        evaluation_end: datetime,
    ) -> Optional[SystemHealth]:
        """
        Aggregate technique results into system health score.
        
        Parameters
        ----------
        unit_id : str
            Equipment identifier
        client : str
            Client identifier
        equipment_model : str
            Equipment model
        system : str
            System name (e.g., "Engine")
        technique_results : List[TechniqueResult]
            Recent technique results for all signals
        evaluation_end : datetime
            End of evaluation period
        
        Returns
        -------
        Optional[SystemHealth]
            System health assessment or None if insufficient data
        """
        try:
            # Filter results for this system
            system_results = self._filter_results_by_system(technique_results, system)
            
            if len(system_results) == 0:
                self.logger.warning(
                    f"No technique results for {unit_id}/{system}"
                )
                return None
            
            # Calculate evaluation period
            evaluation_start = min(r.evaluation_window_start for r in system_results if r.evaluation_window_start)
            
            # Apply weighting and calculate risk score
            risk_score, weighted_results = self._calculate_weighted_risk_score(
                system_results, evaluation_end, system
            )
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(weighted_results)
            
            # Classify status
            status = self._classify_status(risk_score, confidence_score)
            
            # Identify top contributing signals
            top_signals = self._identify_top_signals(weighted_results, top_n=3)
            
            # Identify contributing techniques
            top_techniques = list(set(r.technique_name for r in system_results))
            
            # Build evidence summary
            evidence_summary = self._build_evidence_summary(
                weighted_results, risk_score, confidence_score
            )
            
            # Create system health assessment
            system_health = SystemHealth(
                unit_id=unit_id,
                client=client,
                equipment_model=equipment_model,
                system=system,
                assessment_timestamp=datetime.utcnow(),
                evaluation_period_start=evaluation_start,
                evaluation_period_end=evaluation_end,
                system_score=risk_score,
                system_confidence=confidence_score,
                system_status=status,
                top_signals=top_signals,
                top_techniques=top_techniques,
                explanation="",  # To be filled by ExplanationGenerator
                evidence_summary=evidence_summary,
            )
            
            return system_health
            
        except Exception as e:
            self.logger.error(
                f"System aggregation failed for {unit_id}/{system}: {e}",
                exc_info=True
            )
            return None
    
    def _filter_results_by_system(
        self,
        technique_results: List[TechniqueResult],
        system: str,
    ) -> List[TechniqueResult]:
        """
        Filter technique results to specific system.
        
        Parameters
        ----------
        technique_results : List[TechniqueResult]
            All technique results
        system : str
            System name to filter
        
        Returns
        -------
        List[TechniqueResult]
            Filtered results for system
        """
        system_results = []
        
        for result in technique_results:
            # Check if signal belongs to system
            signal = self.signal_registry.get_signal(result.signal_name)
            if signal and signal.system == system:
                system_results.append(result)
        
        return system_results
    
    def _calculate_weighted_risk_score(
        self,
        system_results: List[TechniqueResult],
        evaluation_end: datetime,
        system: str,
    ) -> Tuple[float, List[Tuple[TechniqueResult, float]]]:
        """
        Calculate weighted risk score with time decay and bonuses.
        
        Parameters
        ----------
        system_results : List[TechniqueResult]
            Technique results for system
        evaluation_end : datetime
            End of evaluation period
        system : str
            System name
        
        Returns
        -------
        Tuple[float, List[Tuple[TechniqueResult, float]]]
            (risk_score, list of (result, weight) tuples)
        """
        weighted_results = []
        
        for result in system_results:
            # Base weight from signal criticality
            signal = self.signal_registry.get_signal(result.signal_name)
            signal_criticality = signal.criticality if signal else 1.0
            
            # Time decay weight (exponential decay based on result age)
            if result.evaluation_timestamp:
                days_old = (evaluation_end - result.evaluation_timestamp).days
                time_weight = np.exp(-self.time_decay_lambda * days_old)
            else:
                time_weight = 1.0
            
            # Confidence weight
            confidence_weight = result.confidence_score / 100.0
            
            # Combined weight
            combined_weight = signal_criticality * time_weight * confidence_weight
            
            weighted_results.append((result, combined_weight))
        
        # Calculate weighted mean risk score
        total_weighted_risk = sum(r.risk_score * w for r, w in weighted_results)
        total_weight = sum(w for _, w in weighted_results)
        
        if total_weight > 0:
            base_risk_score = total_weighted_risk / total_weight
        else:
            base_risk_score = 0.0
        
        # Apply diversity bonus (multiple techniques)
        unique_techniques = set(r.technique_name for r, _ in weighted_results)
        if len(unique_techniques) >= 3:
            diversity_multiplier = 1.0 + self.diversity_bonus
        else:
            diversity_multiplier = 1.0
        
        # Apply persistence bonus (multiple abnormal results)
        abnormal_count = sum(1 for r, _ in weighted_results if r.status in ["Alerta", "Anormal"])
        if abnormal_count >= 3:
            persistence_multiplier = 1.0 + self.persistence_bonus
        else:
            persistence_multiplier = 1.0
        
        # Calculate final risk score
        final_risk_score = base_risk_score * diversity_multiplier * persistence_multiplier
        
        # Critical finding preservation (max > 80 cannot be averaged away)
        max_risk = max((r.risk_score for r, _ in weighted_results), default=0)
        if max_risk >= 80:
            final_risk_score = 0.7 * max_risk + 0.3 * final_risk_score
        
        # Cap at 100
        final_risk_score = min(final_risk_score, 100.0)
        
        return final_risk_score, weighted_results
    
    def _calculate_confidence_score(
        self,
        weighted_results: List[Tuple[TechniqueResult, float]],
    ) -> float:
        """
        Calculate aggregate confidence using weighted harmonic mean.
        
        Parameters
        ----------
        weighted_results : List[Tuple[TechniqueResult, float]]
            Results with weights
        
        Returns
        -------
        float
            Confidence score (0-100)
        """
        if not weighted_results:
            return 0.0
        
        # Weighted harmonic mean (conservative aggregation)
        weighted_sum = 0.0
        total_weight = 0.0
        
        for result, weight in weighted_results:
            if result.confidence_score > 0:
                weighted_sum += weight / result.confidence_score
                total_weight += weight
        
        if weighted_sum > 0 and total_weight > 0:
            harmonic_mean = total_weight / weighted_sum
        else:
            # Fallback to simple mean
            harmonic_mean = sum(r.confidence_score for r, _ in weighted_results) / len(weighted_results)
        
        return min(harmonic_mean, 100.0)
    
    def _classify_status(self, risk_score: float, confidence_score: float) -> str:
        """
        Classify system status based on risk and confidence.
        
        Parameters
        ----------
        risk_score : float
            System risk score (0-100)
        confidence_score : float
            System confidence score (0-100)
        
        Returns
        -------
        str
            Status: "Normal", "Alerta", "Anormal", "InsufficientData"
        """
        if confidence_score < 50:
            return "InsufficientData"
        
        if risk_score < 30:
            return "Normal"
        elif risk_score < 60:
            return "Alerta"
        else:
            return "Anormal"
    
    def _identify_top_signals(
        self,
        weighted_results: List[Tuple[TechniqueResult, float]],
        top_n: int = 3,
    ) -> List[str]:
        """
        Identify top N contributing signals by weighted risk score.
        
        Parameters
        ----------
        weighted_results : List[Tuple[TechniqueResult, float]]
            Results with weights
        top_n : int
            Number of top signals to return
        
        Returns
        -------
        List[str]
            Top signal names
        """
        # Aggregate by signal (in case multiple techniques per signal)
        signal_scores = {}
        
        for result, weight in weighted_results:
            signal_name = result.signal_name
            weighted_risk = result.risk_score * weight
            
            if signal_name in signal_scores:
                signal_scores[signal_name] += weighted_risk
            else:
                signal_scores[signal_name] = weighted_risk
        
        # Sort by weighted risk
        sorted_signals = sorted(
            signal_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [signal for signal, _ in sorted_signals[:top_n]]
    
    def _build_evidence_summary(
        self,
        weighted_results: List[Tuple[TechniqueResult, float]],
        risk_score: float,
        confidence_score: float,
    ) -> Dict[str, Any]:
        """
        Build evidence summary dictionary.
        
        Parameters
        ----------
        weighted_results : List[Tuple[TechniqueResult, float]]
            Results with weights
        risk_score : float
            Final risk score
        confidence_score : float
            Final confidence score
        
        Returns
        -------
        Dict[str, Any]
            Evidence summary
        """
        # Count results by status
        status_counts = {}
        for result, _ in weighted_results:
            status = result.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count results by technique
        technique_counts = {}
        for result, _ in weighted_results:
            technique = result.technique_name
            technique_counts[technique] = technique_counts.get(technique, 0) + 1
        
        # Get signal count
        unique_signals = set(r.signal_name for r, _ in weighted_results)
        
        evidence = {
            "total_results": len(weighted_results),
            "unique_signals": len(unique_signals),
            "unique_techniques": len(technique_counts),
            "status_distribution": status_counts,
            "technique_distribution": technique_counts,
            "final_risk_score": float(risk_score),
            "final_confidence_score": float(confidence_score),
        }
        
        return evidence
    
    def write_system_health(
        self,
        system_health_list: List[SystemHealth],
        evaluation_end: datetime,
    ) -> None:
        """
        Write system health assessments to partitioned Parquet.
        
        Parameters
        ----------
        system_health_list : List[SystemHealth]
            System health assessments to write
        evaluation_end : datetime
            Evaluation end date for partitioning
        """
        if not system_health_list:
            self.logger.warning("No system health assessments to write")
            return
        
        # Convert to DataFrame
        df = pd.DataFrame([sh.to_dict() for sh in system_health_list])
        
        # Get ISO week for partitioning
        iso_year, iso_week, _ = evaluation_end.isocalendar()
        client = system_health_list[0].client
        
        # Build partition path
        partition_path = (
            self.output_dir /
            f"year={iso_year}" /
            f"week={iso_week:02d}" /
            f"client={client}"
        )
        partition_path.mkdir(parents=True, exist_ok=True)
        
        # Write to Parquet
        output_file = partition_path / f"system_health_{iso_year}W{iso_week:02d}.parquet"
        df.to_parquet(output_file, index=False, compression="snappy")
        
        self.logger.info(
            f"Wrote {len(system_health_list)} system health assessments to "
            f"{output_file.relative_to(self.output_dir.parent.parent)}"
        )
