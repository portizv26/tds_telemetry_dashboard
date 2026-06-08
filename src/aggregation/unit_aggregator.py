"""
Unit-Level Health Aggregator.

Aggregates system-level health scores into overall unit health assessment
with priority scoring for fleet maintenance ranking.

Methodology
-----------
1. Load all system health scores for unit
2. Apply system criticality weights (Engine most critical)
3. Calculate weighted mean unit health score
4. Apply multi-system impact bonus (3+ systems abnormal = +20%)
5. Apply critical system penalty (Engine abnormal = 1.5x weight)
6. Calculate priority score (health + degradation + diagnostic rules)
7. Classify maintenance urgency
8. Calculate fleet ranking percentile

Priority Scoring Factors
-------------------------
- Base health score (0-100)
- Recent degradation (week-over-week delta)
- Critical system flags (Engine/Transmission abnormal)
- Diagnostic rule firings
- Multi-system impact
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path

from src.models.entities import UnitHealth, SystemHealth
from src.utils.logger import get_logger


class UnitAggregator:
    """
    Aggregates system-level health into unit-level assessment.
    
    Parameters
    ----------
    output_dir : Path
        Directory for unit health outputs
    system_criticality_weights : Optional[Dict[str, float]]
        System criticality multipliers
    multi_system_bonus : float
        Bonus when 3+ systems abnormal (default: 0.20 = 20%)
    critical_system_multiplier : float
        Weight multiplier for critical systems (default: 1.5)
    degradation_weight : float
        Weight of week-over-week change in priority (default: 0.3)
    """
    
    # Default system criticality weights (same as SystemAggregator)
    DEFAULT_SYSTEM_WEIGHTS = {
        "Engine": 3.0,
        "Transmission": 2.5,
        "Brakes": 2.0,
        "Drive": 1.8,
        "Steering": 1.5,
        "Electrical": 1.2,
    }
    
    # Critical systems (failures are more severe)
    CRITICAL_SYSTEMS = ["Engine", "Transmission"]
    
    def __init__(
        self,
        output_dir: Path,
        system_criticality_weights: Optional[Dict[str, float]] = None,
        multi_system_bonus: float = 0.20,
        critical_system_multiplier: float = 1.5,
        degradation_weight: float = 0.3,
    ):
        self.output_dir = output_dir
        self.system_weights = system_criticality_weights or self.DEFAULT_SYSTEM_WEIGHTS
        self.multi_system_bonus = multi_system_bonus
        self.critical_system_multiplier = critical_system_multiplier
        self.degradation_weight = degradation_weight
        self.logger = get_logger("unit_aggregator")
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def aggregate_unit_health(
        self,
        unit_id: str,
        client: str,
        equipment_model: str,
        system_health_list: List[SystemHealth],
        previous_unit_health: Optional[UnitHealth] = None,
        diagnostic_rule_count: int = 0,
    ) -> Optional[UnitHealth]:
        """
        Aggregate system health scores into unit health assessment.
        
        Parameters
        ----------
        unit_id : str
            Equipment identifier
        client : str
            Client identifier
        equipment_model : str
            Equipment model
        system_health_list : List[SystemHealth]
            System health assessments for unit
        previous_unit_health : Optional[UnitHealth]
            Previous week's unit health (for degradation tracking)
        diagnostic_rule_count : int
            Number of diagnostic rules fired
        
        Returns
        -------
        Optional[UnitHealth]
            Unit health assessment or None if insufficient data
        """
        try:
            if len(system_health_list) == 0:
                self.logger.warning(f"No system health data for {unit_id}")
                return None
            
            # Calculate evaluation period
            evaluation_start = min(sh.evaluation_period_start for sh in system_health_list if sh.evaluation_period_start)
            evaluation_end = max(sh.evaluation_period_end for sh in system_health_list if sh.evaluation_period_end)
            
            # Calculate weighted unit health score
            unit_score = self._calculate_unit_score(system_health_list)
            
            # Calculate unit confidence
            unit_confidence = self._calculate_unit_confidence(system_health_list)
            
            # Classify overall status
            overall_status = self._classify_status(unit_score, unit_confidence)
            
            # Count systems by status
            systems_anormal = sum(1 for sh in system_health_list if sh.system_status == "Anormal")
            systems_alerta = sum(1 for sh in system_health_list if sh.system_status == "Alerta")
            systems_normal = sum(1 for sh in system_health_list if sh.system_status == "Normal")
            
            # Identify top risk systems
            top_risk_systems = self._identify_top_risk_systems(system_health_list, top_n=3)
            
            # Calculate priority score
            priority_score = self._calculate_priority_score(
                unit_score=unit_score,
                system_health_list=system_health_list,
                previous_unit_health=previous_unit_health,
                diagnostic_rule_count=diagnostic_rule_count,
                systems_anormal=systems_anormal,
            )
            
            # Build evidence summary
            evidence_summary = self._build_evidence_summary(
                system_health_list=system_health_list,
                unit_score=unit_score,
                priority_score=priority_score,
                previous_unit_health=previous_unit_health,
                diagnostic_rule_count=diagnostic_rule_count,
            )
            
            # Create unit health assessment
            unit_health = UnitHealth(
                unit_id=unit_id,
                client=client,
                equipment_model=equipment_model,
                assessment_timestamp=datetime.utcnow(),
                evaluation_period_start=evaluation_start,
                evaluation_period_end=evaluation_end,
                unit_score=unit_score,
                unit_confidence=unit_confidence,
                overall_status=overall_status,
                priority_score=priority_score,
                top_risk_systems=top_risk_systems,
                systems_anormal=systems_anormal,
                systems_alerta=systems_alerta,
                systems_normal=systems_normal,
                executive_summary="",  # To be filled by ExplanationGenerator
                evidence_summary=evidence_summary,
            )
            
            return unit_health
            
        except Exception as e:
            self.logger.error(
                f"Unit aggregation failed for {unit_id}: {e}",
                exc_info=True
            )
            return None
    
    def _calculate_unit_score(
        self,
        system_health_list: List[SystemHealth],
    ) -> float:
        """
        Calculate weighted unit health score from system scores.
        
        Parameters
        ----------
        system_health_list : List[SystemHealth]
            System health assessments
        
        Returns
        -------
        float
            Unit health score (0-100)
        """
        weighted_sum = 0.0
        total_weight = 0.0
        
        # Count abnormal critical systems
        critical_systems_abnormal = 0
        systems_abnormal_count = 0
        
        for system_health in system_health_list:
            system_name = system_health.system
            system_score = system_health.system_score
            
            # Base weight from system criticality
            base_weight = self.system_weights.get(system_name, 1.0)
            
            # Apply critical system multiplier if abnormal
            if system_name in self.CRITICAL_SYSTEMS and system_health.system_status == "Anormal":
                weight = base_weight * self.critical_system_multiplier
                critical_systems_abnormal += 1
            else:
                weight = base_weight
            
            # Count abnormal systems
            if system_health.system_status in ["Anormal", "Alerta"]:
                systems_abnormal_count += 1
            
            weighted_sum += system_score * weight
            total_weight += weight
        
        # Calculate base unit score
        if total_weight > 0:
            base_unit_score = weighted_sum / total_weight
        else:
            base_unit_score = 0.0
        
        # Apply multi-system impact bonus (3+ systems abnormal)
        if systems_abnormal_count >= 3:
            multi_system_multiplier = 1.0 + self.multi_system_bonus
            base_unit_score *= multi_system_multiplier
        
        # Critical finding preservation (max system > 80)
        max_system_score = max(sh.system_score for sh in system_health_list)
        if max_system_score >= 80:
            base_unit_score = 0.7 * max_system_score + 0.3 * base_unit_score
        
        # Cap at 100
        return min(base_unit_score, 100.0)
    
    def _calculate_unit_confidence(
        self,
        system_health_list: List[SystemHealth],
    ) -> float:
        """
        Calculate unit confidence from system confidences.
        
        Uses minimum confidence (conservative approach).
        
        Parameters
        ----------
        system_health_list : List[SystemHealth]
            System health assessments
        
        Returns
        -------
        float
            Unit confidence score (0-100)
        """
        if not system_health_list:
            return 0.0
        
        # Use minimum confidence (unit confidence limited by weakest system)
        min_confidence = min(sh.system_confidence for sh in system_health_list)
        
        return min_confidence
    
    def _classify_status(self, unit_score: float, unit_confidence: float) -> str:
        """
        Classify unit status based on score and confidence.
        
        Parameters
        ----------
        unit_score : float
            Unit health score (0-100)
        unit_confidence : float
            Unit confidence score (0-100)
        
        Returns
        -------
        str
            Status: "Normal", "Alerta", "Anormal", "InsufficientData"
        """
        if unit_confidence < 50:
            return "InsufficientData"
        
        if unit_score < 30:
            return "Normal"
        elif unit_score < 60:
            return "Alerta"
        else:
            return "Anormal"
    
    def _identify_top_risk_systems(
        self,
        system_health_list: List[SystemHealth],
        top_n: int = 3,
    ) -> List[str]:
        """
        Identify top N systems by risk score.
        
        Parameters
        ----------
        system_health_list : List[SystemHealth]
            System health assessments
        top_n : int
            Number of top systems to return
        
        Returns
        -------
        List[str]
            Top system names
        """
        # Sort by system score (descending)
        sorted_systems = sorted(
            system_health_list,
            key=lambda sh: sh.system_score,
            reverse=True
        )
        
        return [sh.system for sh in sorted_systems[:top_n]]
    
    def _calculate_priority_score(
        self,
        unit_score: float,
        system_health_list: List[SystemHealth],
        previous_unit_health: Optional[UnitHealth],
        diagnostic_rule_count: int,
        systems_abnormal: int,
    ) -> float:
        """
        Calculate priority score for fleet ranking.
        
        Priority score considers:
        - Current health score
        - Recent degradation (week-over-week)
        - Critical system flags
        - Diagnostic rule firings
        - Multi-system impact
        
        Parameters
        ----------
        unit_score : float
            Current unit health score
        system_health_list : List[SystemHealth]
            System health assessments
        previous_unit_health : Optional[UnitHealth]
            Previous week's assessment
        diagnostic_rule_count : int
            Number of rules fired
        systems_abnormal : int
            Number of abnormal systems
        
        Returns
        -------
        float
            Priority score (0-100+, can exceed 100 for very urgent)
        """
        # Base priority from health score
        priority = unit_score
        
        # Degradation factor (week-over-week change)
        if previous_unit_health:
            degradation = unit_score - previous_unit_health.unit_score
            if degradation > 10:  # Significant worsening
                priority += degradation * self.degradation_weight
        
        # Critical system penalty
        critical_systems_abnormal = sum(
            1 for sh in system_health_list
            if sh.system in self.CRITICAL_SYSTEMS and sh.system_status == "Anormal"
        )
        if critical_systems_abnormal > 0:
            priority += critical_systems_abnormal * 15  # +15 per critical system
        
        # Diagnostic rule bonus
        if diagnostic_rule_count > 0:
            priority += min(diagnostic_rule_count * 10, 25)  # +10 per rule, max +25
        
        # Multi-system impact bonus
        if systems_abnormal >= 3:
            priority += 20
        
        return priority
    
    def _build_evidence_summary(
        self,
        system_health_list: List[SystemHealth],
        unit_score: float,
        priority_score: float,
        previous_unit_health: Optional[UnitHealth],
        diagnostic_rule_count: int,
    ) -> Dict[str, Any]:
        """
        Build evidence summary for unit health.
        
        Parameters
        ----------
        system_health_list : List[SystemHealth]
            System health assessments
        unit_score : float
            Unit health score
        priority_score : float
            Priority score
        previous_unit_health : Optional[UnitHealth]
            Previous assessment
        diagnostic_rule_count : int
            Number of rules fired
        
        Returns
        -------
        Dict[str, Any]
            Evidence summary
        """
        # System scores
        system_scores = {
            sh.system: float(sh.system_score)
            for sh in system_health_list
        }
        
        # Week-over-week delta
        if previous_unit_health:
            week_over_week_delta = unit_score - previous_unit_health.unit_score
        else:
            week_over_week_delta = None
        
        # Maintenance urgency classification
        if priority_score >= 85:
            maintenance_urgency = "immediate"
        elif priority_score >= 70:
            maintenance_urgency = "this_week"
        elif priority_score >= 50:
            maintenance_urgency = "this_month"
        else:
            maintenance_urgency = "monitor"
        
        evidence = {
            "system_scores": system_scores,
            "unit_score": float(unit_score),
            "priority_score": float(priority_score),
            "week_over_week_delta": float(week_over_week_delta) if week_over_week_delta is not None else None,
            "diagnostic_rules_fired": diagnostic_rule_count,
            "maintenance_urgency": maintenance_urgency,
            "total_systems_evaluated": len(system_health_list),
        }
        
        return evidence
    
    def write_unit_health(
        self,
        unit_health_list: List[UnitHealth],
        evaluation_end: datetime,
    ) -> None:
        """
        Write unit health assessments to partitioned Parquet.
        
        Parameters
        ----------
        unit_health_list : List[UnitHealth]
            Unit health assessments to write
        evaluation_end : datetime
            Evaluation end date for partitioning
        """
        if not unit_health_list:
            self.logger.warning("No unit health assessments to write")
            return
        
        # Convert to DataFrame
        df = pd.DataFrame([uh.to_dict() for uh in unit_health_list])
        
        # Get ISO week for partitioning
        iso_year, iso_week, _ = evaluation_end.isocalendar()
        client = unit_health_list[0].client
        
        # Build partition path
        partition_path = (
            self.output_dir /
            f"year={iso_year}" /
            f"week={iso_week:02d}" /
            f"client={client}"
        )
        partition_path.mkdir(parents=True, exist_ok=True)
        
        # Write to Parquet
        output_file = partition_path / f"unit_health_{iso_year}W{iso_week:02d}.parquet"
        df.to_parquet(output_file, index=False, compression="snappy")
        
        self.logger.info(
            f"Wrote {len(unit_health_list)} unit health assessments to "
            f"{output_file.relative_to(self.output_dir.parent.parent)}"
        )
    
    def generate_fleet_summary(
        self,
        unit_health_list: List[UnitHealth],
    ) -> Dict[str, Any]:
        """
        Generate fleet-level statistics.
        
        Parameters
        ----------
        unit_health_list : List[UnitHealth]
            All unit health assessments for fleet
        
        Returns
        -------
        Dict[str, Any]
            Fleet statistics
        """
        if not unit_health_list:
            return {}
        
        scores = [uh.unit_score for uh in unit_health_list]
        
        summary = {
            "total_units": len(unit_health_list),
            "mean_health": float(np.mean(scores)),
            "median_health": float(np.median(scores)),
            "std_health": float(np.std(scores)),
            "min_health": float(np.min(scores)),
            "max_health": float(np.max(scores)),
            "p25_health": float(np.percentile(scores, 25)),
            "p75_health": float(np.percentile(scores, 75)),
            "p95_health": float(np.percentile(scores, 95)),
            "units_normal": sum(1 for uh in unit_health_list if uh.overall_status == "Normal"),
            "units_alerta": sum(1 for uh in unit_health_list if uh.overall_status == "Alerta"),
            "units_anormal": sum(1 for uh in unit_health_list if uh.overall_status == "Anormal"),
            "units_insufficient_data": sum(1 for uh in unit_health_list if uh.overall_status == "InsufficientData"),
            "pct_abnormal": (sum(1 for uh in unit_health_list if uh.overall_status == "Anormal") / len(unit_health_list)) * 100,
        }
        
        return summary
    
    def get_top_priority_units(
        self,
        unit_health_list: List[UnitHealth],
        top_n: int = 10,
    ) -> List[UnitHealth]:
        """
        Get top N priority units for maintenance.
        
        Parameters
        ----------
        unit_health_list : List[UnitHealth]
            All unit health assessments
        top_n : int
            Number of units to return
        
        Returns
        -------
        List[UnitHealth]
            Top priority units sorted by priority score
        """
        sorted_units = sorted(
            unit_health_list,
            key=lambda uh: uh.priority_score,
            reverse=True
        )
        
        return sorted_units[:top_n]
