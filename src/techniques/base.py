"""
Abstract base class for all analytical techniques.

All techniques must inherit from BaseTechnique and implement:
- evaluate() method to perform analysis
- _calculate_risk_score() to compute risk (0-100)
- _calculate_confidence_score() to compute confidence (0-100)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
from pathlib import Path

from src.models.entities import TechniqueResult, EvaluationWindow
from src.config.signal_registry import SignalRegistry
from src.baselines.baseline_manager import BaselineManager
from src.utils.logger import get_logger


class BaseTechnique(ABC):
    """
    Abstract base class for all analytical techniques.
    
    Design Principles
    -----------------
    1. Technique independence: Each technique is autonomous
    2. Risk + Confidence separation: Always produce both scores
    3. Explainability first: Every score must have evidence
    4. State-specific baselines: Match operational state when comparing
    
    Attributes
    ----------
    technique_name : str
        Unique technique identifier
    technique_version : str
        Semantic version
    validity_period_days : int
        How many days this result remains valid
    
    Methods
    -------
    evaluate(unit_id, client, signal_name, window) -> TechniqueResult
        Execute technique analysis
    _calculate_risk_score(evidence) -> float
        Convert native metrics to 0-100 risk score
    _calculate_confidence_score(data, baseline) -> float
        Calculate confidence based on data quality
    """
    
    def __init__(
        self,
        technique_name: str,
        technique_version: str,
        validity_period_days: int,
        signal_registry: SignalRegistry,
        baseline_manager: BaselineManager,
        output_dir: Path,
    ):
        """
        Initialize technique.
        
        Parameters
        ----------
        technique_name : str
            Technique identifier (e.g., "threshold_deviation")
        technique_version : str
            Semantic version (e.g., "1.0.0")
        validity_period_days : int
            Days result remains valid
        signal_registry : SignalRegistry
            Signal metadata registry
        baseline_manager : BaselineManager
            Baseline retrieval manager
        output_dir : Path
            Directory for technique results
        """
        self.technique_name = technique_name
        self.technique_version = technique_version
        self.validity_period_days = validity_period_days
        self.signal_registry = signal_registry
        self.baseline_manager = baseline_manager
        self.output_dir = output_dir
        self.logger = get_logger(f"technique.{technique_name}")
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
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
        Execute technique evaluation.
        
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
            Silver layer telemetry data
        
        Returns
        -------
        Optional[TechniqueResult]
            Result object or None if evaluation failed
        """
        pass
    
    @abstractmethod
    def _calculate_risk_score(self, evidence: Dict[str, Any]) -> float:
        """
        Convert technique-specific evidence into normalized risk score (0-100).
        
        Parameters
        ----------
        evidence : Dict[str, Any]
            Technique-specific evidence dictionary
        
        Returns
        -------
        float
            Risk score between 0-100
            - 0-30: Low risk / Normal variation
            - 30-60: Moderate risk / Monitoring recommended
            - 60-80: High risk / Inspection recommended
            - 80-100: Critical risk / Immediate action required
        """
        pass
    
    @abstractmethod
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
            Baseline statistics (if applicable)
        
        Returns
        -------
        float
            Confidence score between 0-100
            Based on: coverage, baseline quality, sample size, state matching
        """
        pass
    
    def _classify_status(self, risk_score: float, confidence_score: float) -> str:
        """
        Classify status based on risk and confidence scores.
        
        Parameters
        ----------
        risk_score : float
            Risk score (0-100)
        confidence_score : float
            Confidence score (0-100)
        
        Returns
        -------
        str
            Status: "Normal", "Alerta", "Anormal", "InsufficientData"
        """
        # Insufficient data check
        if confidence_score < 50:
            return "InsufficientData"
        
        # Risk-based classification
        if risk_score < 30:
            return "Normal"
        elif risk_score < 60:
            return "Alerta"
        else:
            return "Anormal"
    
    def _get_signal_metadata(self, signal_name: str) -> Dict[str, Any]:
        """
        Retrieve signal metadata from registry.
        
        Parameters
        ----------
        signal_name : str
            Signal identifier
        
        Returns
        -------
        Dict[str, Any]
            Signal metadata
        """
        signal = self.signal_registry.get_signal(signal_name)
        if not signal:
            self.logger.warning(f"Signal {signal_name} not found in registry")
            return {}
        
        return {
            "system": signal.system,
            "subsystem": signal.subsystem,
            "unit": signal.unit,
            "risk_direction": signal.risk_direction,
            "criticality": signal.criticality,
        }
    
    def _write_results(
        self,
        results: List[TechniqueResult],
        partition_keys: Dict[str, Any],
    ) -> None:
        """
        Write technique results to partitioned Parquet.
        
        Parameters
        ----------
        results : List[TechniqueResult]
            Results to write
        partition_keys : Dict[str, Any]
            Partition keys (e.g., {'year': 2026, 'month': 6, 'day': 5})
        """
        if not results:
            self.logger.warning("No results to write")
            return
        
        # Convert results to DataFrame
        df = pd.DataFrame([r.to_dict() for r in results])
        
        # Build partition path
        partition_path = self.output_dir
        for key, value in partition_keys.items():
            partition_path = partition_path / f"{key}={value}"
        
        partition_path.mkdir(parents=True, exist_ok=True)
        
        # Write to Parquet
        output_file = partition_path / f"{self.technique_name}_results.parquet"
        df.to_parquet(output_file, index=False, compression="snappy")
        
        self.logger.info(
            f"Wrote {len(results)} results to {output_file.relative_to(self.output_dir.parent.parent)}"
        )
    
    def _filter_by_operational_state(
        self,
        df: pd.DataFrame,
        signal_name: str,
        valid_states: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Filter data to valid operational states for signal.
        
        Parameters
        ----------
        df : pd.DataFrame
            Input data with 'EstadoMaquina' column
        signal_name : str
            Signal name for state validation
        valid_states : Optional[List[str]]
            Override valid states (uses signal registry if None)
        
        Returns
        -------
        pd.DataFrame
            Filtered dataframe
        """
        if valid_states is None:
            signal = self.signal_registry.get_signal(signal_name)
            if signal:
                valid_states = signal.valid_states
            else:
                # Default to Operacional only
                valid_states = ["Operacional"]
        
        if "EstadoMaquina" in df.columns:
            df_filtered = df[df["EstadoMaquina"].isin(valid_states)].copy()
            self.logger.debug(
                f"Filtered {signal_name}: {len(df)} -> {len(df_filtered)} rows "
                f"(states: {valid_states})"
            )
            return df_filtered
        else:
            self.logger.warning("EstadoMaquina column not found, skipping state filter")
            return df.copy()
