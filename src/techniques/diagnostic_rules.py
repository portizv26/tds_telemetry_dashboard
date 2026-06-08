"""
Diagnostic Rules Engine.

Multi-signal pattern detection for known mechanical failure modes.
Encodes domain expert knowledge as explicit rules.

Methodology
-----------
1. Load diagnostic_rules.yaml configuration
2. Evaluate rules against recent telemetry
3. Check multi-signal conditions (AND, OR, COUNT_THRESHOLD logic)
4. Generate TechniqueResult for fired rules
5. Store rule firing history

Rule Types
----------
- SINGLE: Single signal condition
- AND: All conditions must be met
- OR: Any condition triggers rule
- COUNT_THRESHOLD: N of M conditions must be met
- DELTA: Compare two signals (temperature imbalance, etc.)
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path
import yaml

from src.techniques.base import BaseTechnique
from src.models.entities import TechniqueResult, EvaluationWindow
from src.config.signal_registry import SignalRegistry
from src.baselines.baseline_manager import BaselineManager
from src.scoring.normalization import normalize_diagnostic_rule_score


class DiagnosticRulesEngine(BaseTechnique):
    """
    Diagnostic rules evaluation engine.
    
    Evaluates multi-signal patterns defined in diagnostic_rules.yaml.
    
    Parameters
    ----------
    signal_registry : SignalRegistry
        Signal metadata registry
    baseline_manager : BaselineManager
        Baseline retrieval manager
    output_dir : Path
        Directory for technique results
    rules_config_path : Path
        Path to diagnostic_rules.yaml
    """
    
    def __init__(
        self,
        signal_registry: SignalRegistry,
        baseline_manager: BaselineManager,
        output_dir: Path,
        rules_config_path: Path,
    ):
        super().__init__(
            technique_name="diagnostic_rules",
            technique_version="1.0.0",
            validity_period_days=1,  # Rules evaluated daily
            signal_registry=signal_registry,
            baseline_manager=baseline_manager,
            output_dir=output_dir,
        )
        self.rules_config_path = rules_config_path
        self.rules = self._load_rules()
        self.eval_params = self.rules.get('evaluation_parameters', {})
        self.logger.info(f"Loaded {len(self.rules.get('rules', []))} diagnostic rules")
    
    def _load_rules(self) -> Dict[str, Any]:
        """Load diagnostic rules from YAML configuration."""
        try:
            with open(self.rules_config_path, 'r') as f:
                rules = yaml.safe_load(f)
            return rules
        except Exception as e:
            self.logger.error(f"Failed to load diagnostic rules: {e}")
            return {'rules': []}
    
    def evaluate_all_rules(
        self,
        unit_id: str,
        client: str,
        equipment_model: str,
        window: EvaluationWindow,
        silver_df: pd.DataFrame,
    ) -> List[TechniqueResult]:
        """
        Evaluate all diagnostic rules for unit.
        
        Parameters
        ----------
        unit_id : str
            Equipment identifier
        client : str
            Client identifier
        equipment_model : str
            Equipment model
        window : EvaluationWindow
            Temporal evaluation window
        silver_df : pd.DataFrame
            Silver layer telemetry data
        
        Returns
        -------
        List[TechniqueResult]
            Results for all fired rules
        """
        results = []
        
        # Filter to evaluation window
        window_df = silver_df[
            (silver_df['Fecha'] >= window.start) &
            (silver_df['Fecha'] <= window.end)
        ].copy()
        
        if len(window_df) == 0:
            self.logger.warning(
                f"No data for {unit_id} in window {window.start} to {window.end}"
            )
            return results
        
        # Evaluate each rule
        for rule in self.rules.get('rules', []):
            result = self._evaluate_rule(
                rule=rule,
                unit_id=unit_id,
                client=client,
                equipment_model=equipment_model,
                window=window,
                window_df=window_df,
            )
            
            if result:
                results.append(result)
        
        return results
    
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
        Evaluate rules (not used - use evaluate_all_rules instead).
        
        This method exists to satisfy BaseTechnique interface.
        """
        # Not used - diagnostic rules evaluate multiple signals
        return None
    
    def _evaluate_rule(
        self,
        rule: Dict[str, Any],
        unit_id: str,
        client: str,
        equipment_model: str,
        window: EvaluationWindow,
        window_df: pd.DataFrame,
    ) -> Optional[TechniqueResult]:
        """
        Evaluate a single diagnostic rule.
        
        Parameters
        ----------
        rule : Dict[str, Any]
            Rule definition
        unit_id : str
            Equipment identifier
        client : str
            Client identifier
        equipment_model : str
            Equipment model
        window : EvaluationWindow
            Evaluation window
        window_df : pd.DataFrame
            Telemetry data
        
        Returns
        -------
        Optional[TechniqueResult]
            Result if rule fired, None otherwise
        """
        try:
            rule_id = rule['rule_id']
            rule_name = rule['name']
            system = rule['system']
            severity = rule['severity']
            logic = rule.get('logic', 'AND')
            conditions = rule.get('conditions', [])
            
            # Evaluate each condition
            condition_results = []
            condition_evidence = {}
            
            for condition in conditions:
                is_met, evidence = self._evaluate_condition(
                    condition, window_df, unit_id, client, equipment_model
                )
                condition_results.append(is_met)
                condition_evidence.update(evidence)
            
            # Apply rule logic
            rule_fired = self._apply_rule_logic(
                logic, condition_results, rule.get('count_threshold', 0)
            )
            
            if not rule_fired:
                return None
            
            # Calculate rule confidence
            confidence = self._calculate_rule_confidence(
                condition_evidence, rule.get('evidence_requirements', {})
            )
            
            # Check minimum confidence
            min_confidence = self.eval_params.get('min_rule_confidence', 60)
            if confidence < min_confidence:
                self.logger.debug(
                    f"Rule {rule_id} fired but confidence {confidence:.1f} < {min_confidence}"
                )
                return None
            
            # Calculate risk score
            risk_score = normalize_diagnostic_rule_score(
                rule_severity=severity,
                confidence=confidence / 100.0,
            )
            
            # Build evidence
            evidence = {
                "rule_id": rule_id,
                "rule_name": rule_name,
                "severity": severity,
                "conditions_met": sum(condition_results),
                "total_conditions": len(condition_results),
                "logic": logic,
                **condition_evidence,
            }
            
            # Generate explanation
            explanation = self._generate_rule_explanation(rule, evidence)
            
            # Status classification
            status = self._classify_status(risk_score, confidence)
            
            # Create technique result
            result = TechniqueResult(
                technique_name=self.technique_name,
                technique_version=self.technique_version,
                evaluation_timestamp=datetime.utcnow(),
                evaluation_window_start=window.start,
                evaluation_window_end=window.end,
                unit_id=unit_id,
                client=client,
                equipment_model=equipment_model,
                signal_name=rule_id,  # Use rule_id as signal_name
                system=system,
                risk_score=risk_score,
                confidence_score=confidence,
                status=status,
                validity_period_days=self.validity_period_days,
                baseline_version=None,
                evidence=evidence,
            )
            
            self.logger.info(
                f"Rule {rule_id} fired for {unit_id}: risk={risk_score:.1f}, confidence={confidence:.1f}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                f"Rule evaluation failed for {rule.get('rule_id', 'unknown')}: {e}",
                exc_info=True
            )
            return None
    
    def _evaluate_condition(
        self,
        condition: Dict[str, Any],
        window_df: pd.DataFrame,
        unit_id: str,
        client: str,
        equipment_model: str,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate a single rule condition.
        
        Parameters
        ----------
        condition : Dict[str, Any]
            Condition definition
        window_df : pd.DataFrame
            Telemetry data
        unit_id : str
            Unit identifier
        client : str
            Client identifier
        equipment_model : str
            Equipment model
        
        Returns
        -------
        Tuple[bool, Dict[str, Any]]
            (condition_met, evidence_dict)
        """
        signal_name = condition['signal']
        threshold_type = condition['threshold_type']
        operator = condition['operator']
        duration_minutes = condition.get('duration_minutes', 0)
        
        # Check if signal exists in data
        if signal_name not in window_df.columns:
            return False, {f"{signal_name}_missing": True}
        
        # Get signal values
        values = window_df[signal_name].dropna()
        
        if len(values) == 0:
            return False, {f"{signal_name}_no_data": True}
        
        # Get signal metadata
        signal = self.signal_registry.get_signal(signal_name)
        operational_state = window_df['EstadoMaquina'].mode()[0] if 'EstadoMaquina' in window_df.columns else 'Operacional'
        
        # Get baseline for threshold comparison
        if threshold_type == "percentile":
            baseline = self.baseline_manager.get_baseline(
                client=client,
                equipment_model=equipment_model,
                unit_id=unit_id,
                signal_name=signal_name,
                operational_state=operational_state,
            )
            
            if not baseline:
                return False, {f"{signal_name}_no_baseline": True}
            
            # Get threshold value from baseline
            threshold_key = condition['threshold_value']  # e.g., "p95"
            threshold_value = baseline.get(threshold_key, 0)
            
            # Evaluate condition
            if operator == ">":
                abnormal_mask = values > threshold_value
            elif operator == "<":
                abnormal_mask = values < threshold_value
            elif operator == ">=":
                abnormal_mask = values >= threshold_value
            elif operator == "<=":
                abnormal_mask = values <= threshold_value
            else:
                return False, {f"{signal_name}_invalid_operator": operator}
            
            # Check duration
            abnormal_minutes = abnormal_mask.sum()
            condition_met = abnormal_minutes >= duration_minutes
            
            evidence = {
                f"{signal_name}_value": float(values.mean()),
                f"{signal_name}_{threshold_key}": float(threshold_value),
                f"{signal_name}_abnormal_minutes": int(abnormal_minutes),
                f"{signal_name}_duration_required": int(duration_minutes),
                f"{signal_name}_condition_met": condition_met,
            }
            
            return condition_met, evidence
        
        elif threshold_type == "delta_from_signal":
            # Compare two signals (e.g., temperature imbalance)
            compare_signal = condition['compare_signal']
            
            if compare_signal not in window_df.columns:
                return False, {f"{compare_signal}_missing": True}
            
            compare_values = window_df[compare_signal].dropna()
            
            # Align timestamps
            common_idx = values.index.intersection(compare_values.index)
            values_aligned = values[common_idx]
            compare_aligned = compare_values[common_idx]
            
            if len(values_aligned) == 0:
                return False, {f"{signal_name}_no_aligned_data": True}
            
            # Calculate delta
            delta = values_aligned - compare_aligned
            abs_delta = delta.abs()
            
            threshold_value = condition['threshold_value']
            
            if operator == "delta_abs_>":
                abnormal_mask = abs_delta > threshold_value
            else:
                return False, {f"{signal_name}_invalid_delta_operator": operator}
            
            # Check duration
            abnormal_minutes = abnormal_mask.sum()
            condition_met = abnormal_minutes >= duration_minutes
            
            evidence = {
                f"{signal_name}_value": float(values_aligned.mean()),
                f"{compare_signal}_value": float(compare_aligned.mean()),
                f"temp_delta": float(abs_delta.mean()),
                f"max_delta": float(abs_delta.max()),
                f"{signal_name}_abnormal_minutes": int(abnormal_minutes),
                f"{signal_name}_condition_met": condition_met,
            }
            
            return condition_met, evidence
        
        else:
            return False, {f"{signal_name}_invalid_threshold_type": threshold_type}
    
    def _apply_rule_logic(
        self,
        logic: str,
        condition_results: List[bool],
        count_threshold: int = 0,
    ) -> bool:
        """
        Apply rule logic to condition results.
        
        Parameters
        ----------
        logic : str
            Logic type ("AND", "OR", "SINGLE", "COUNT_THRESHOLD")
        condition_results : List[bool]
            Condition evaluation results
        count_threshold : int
            Threshold for COUNT_THRESHOLD logic
        
        Returns
        -------
        bool
            True if rule fires
        """
        if logic == "AND":
            return all(condition_results)
        elif logic == "OR":
            return any(condition_results)
        elif logic == "SINGLE":
            return condition_results[0] if len(condition_results) > 0 else False
        elif logic == "COUNT_THRESHOLD":
            return sum(condition_results) >= count_threshold
        else:
            self.logger.warning(f"Unknown logic type: {logic}")
            return False
    
    def _calculate_rule_confidence(
        self,
        evidence: Dict[str, Any],
        requirements: Dict[str, Any],
    ) -> float:
        """
        Calculate confidence score for rule firing.
        
        Parameters
        ----------
        evidence : Dict[str, Any]
            Condition evidence
        requirements : Dict[str, Any]
            Evidence requirements
        
        Returns
        -------
        float
            Confidence score (0-100)
        """
        confidence = 100.0
        
        # Check minimum samples
        min_samples = requirements.get('min_samples', 10)
        
        # Find sample counts in evidence
        sample_counts = [v for k, v in evidence.items() if k.endswith('_abnormal_minutes')]
        
        if sample_counts:
            avg_samples = sum(sample_counts) / len(sample_counts)
            if avg_samples < min_samples:
                confidence *= (avg_samples / min_samples) * 0.7 + 0.3  # Scale down but not below 30%
        
        return min(confidence, 100.0)
    
    def _generate_rule_explanation(
        self,
        rule: Dict[str, Any],
        evidence: Dict[str, Any],
    ) -> str:
        """
        Generate natural language explanation for rule firing.
        
        Parameters
        ----------
        rule : Dict[str, Any]
            Rule definition
        evidence : Dict[str, Any]
            Evidence dictionary
        
        Returns
        -------
        str
            Explanation text
        """
        template = rule.get('explanation_template', '')
        
        try:
            # Fill template with evidence values
            explanation = template.format(**evidence)
            return explanation
        except KeyError as e:
            self.logger.warning(f"Missing template variable: {e}")
            return f"{rule['name']}: Rule fired with {evidence.get('conditions_met', 0)} conditions met"
    
    def _calculate_risk_score(self, evidence: Dict[str, Any]) -> float:
        """
        Convert rule evidence to risk score (0-100).
        
        Parameters
        ----------
        evidence : Dict[str, Any]
            Evidence dictionary
        
        Returns
        -------
        float
            Risk score (0-100)
        """
        severity = evidence.get('severity', 'medium')
        confidence = evidence.get('final_confidence', 80.0) / 100.0
        
        return normalize_diagnostic_rule_score(
            rule_severity=severity,
            confidence=confidence,
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
        # Confidence calculated in _calculate_rule_confidence
        # This is placeholder to satisfy abstract method
        return 80.0
