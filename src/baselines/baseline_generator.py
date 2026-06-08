"""
Baseline generation for state-specific percentiles.
Based on data_contracts.md Section 4.1 (Baseline Statistics Table)
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
import numpy as np
import logging
import json

from src.config import SignalRegistry
from src.utils.file_utils import ensure_dir, save_to_parquet
from src.utils.date_utils import get_current_baseline_version

logger = logging.getLogger(__name__)


class BaselineGenerator:
    """
    Generates state-specific baseline statistics for anomaly detection.
    
    Calculates percentiles (P1, P2, P5, P10, P50, P90, P95, P98, P99) and moments (mean, std, MAD)
    grouped by: client + equipment_model + signal + operational_state
    
    Implements fallback hierarchy: unit → model → client → global
    """
    
    def __init__(
        self,
        signal_registry: SignalRegistry,
        min_samples_required: int = 1000,
        percentiles: List[int] = [1, 2, 5, 10, 50, 90, 95, 98, 99]
    ):
        """
        Initialize baseline generator.
        
        Parameters
        ----------
        signal_registry : SignalRegistry
            Signal registry for signal metadata
        min_samples_required : int
            Minimum samples for valid baseline
        percentiles : List[int]
            Percentiles to calculate
        """
        self.signal_registry = signal_registry
        self.min_samples_required = min_samples_required
        self.percentiles = percentiles
    
    def generate_baselines(
        self,
        df: pd.DataFrame,
        client: str,
        baseline_version: Optional[str] = None,
        output_dir: Optional[Path] = None
    ) -> pd.DataFrame:
        """
        Generate baselines from historical data.
        
        Parameters
        ----------
        df : pd.DataFrame
            Historical telemetry data
        client : str
            Client identifier
        baseline_version : Optional[str]
            Baseline version (YYYYMMDD). If None, uses current date
        output_dir : Optional[Path]
            Directory to save baselines. If None, baselines not saved
            
        Returns
        -------
        pd.DataFrame
            Baseline statistics table
        """
        if baseline_version is None:
            baseline_version = get_current_baseline_version()
        
        logger.info(f"Generating baselines for {client}, version {baseline_version}")
        
        # Detect column names
        timestamp_col = self._detect_column(df, ['timestamp', 'Fecha'])
        unit_col = self._detect_column(df, ['unit_id', 'Unit'])
        state_col = self._detect_column(df, ['operational_state', 'EstadoMaquina'])
        model_col = self._detect_column(df, ['equipment_model', 'ModeloEquipo'])
        
        if not timestamp_col or not unit_col or not state_col:
            raise ValueError("Missing required columns for baseline generation")
        
        # Convert timestamp
        df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors='coerce')
        
        # Get training window
        training_start = df[timestamp_col].min()
        training_end = df[timestamp_col].max()
        
        logger.info(f"Training window: {training_start} to {training_end}")
        
        # Get signal columns
        signal_cols = self.signal_registry.get_all_signal_names()
        available_signals = [col for col in signal_cols if col in df.columns]
        
        logger.info(f"Computing baselines for {len(available_signals)} signals")
        
        # Generate baselines at multiple levels
        all_baselines = []
        
        # Level 1: Unit-specific baselines
        unit_baselines = self._generate_unit_level(
            df, client, unit_col, model_col, state_col, available_signals,
            baseline_version, training_start, training_end
        )
        all_baselines.append(unit_baselines)
        
        # Level 2: Model-level baselines
        model_baselines = self._generate_model_level(
            df, client, model_col, state_col, available_signals,
            baseline_version, training_start, training_end
        )
        all_baselines.append(model_baselines)
        
        # Level 3: Client-level baselines
        client_baselines = self._generate_client_level(
            df, client, state_col, available_signals,
            baseline_version, training_start, training_end
        )
        all_baselines.append(client_baselines)
        
        # Combine all baselines
        combined_baselines = pd.concat(all_baselines, ignore_index=True)
        
        logger.info(f"Generated {len(combined_baselines)} baseline records")
        
        # Save if output directory provided
        if output_dir:
            self._save_baselines(
                combined_baselines,
                baseline_version,
                training_start,
                training_end,
                output_dir
            )
        
        return combined_baselines
    
    def _detect_column(self, df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
        """Detect column name from possible alternatives."""
        for name in possible_names:
            if name in df.columns:
                return name
        return None
    
    def _generate_unit_level(
        self,
        df: pd.DataFrame,
        client: str,
        unit_col: str,
        model_col: Optional[str],
        state_col: str,
        signals: List[str],
        baseline_version: str,
        training_start: datetime,
        training_end: datetime
    ) -> pd.DataFrame:
        """Generate unit-specific baselines."""
        logger.info("Generating unit-level baselines...")
        
        baselines = []
        
        for unit_id in df[unit_col].unique():
            unit_df = df[df[unit_col] == unit_id]
            
            # Get equipment model
            if model_col and model_col in df.columns:
                equipment_model = unit_df[model_col].mode()[0] if len(unit_df) > 0 else "Unknown"
            else:
                equipment_model = "Unknown"
            
            for state in df[state_col].unique():
                state_df = unit_df[unit_df[state_col] == state]
                
                for signal in signals:
                    if signal not in df.columns:
                        continue
                    
                    signal_data = state_df[signal].dropna()
                    
                    if len(signal_data) < self.min_samples_required:
                        continue  # Skip insufficient data
                    
                    baseline_row = self._calculate_baseline_stats(
                        signal_data,
                        baseline_version=baseline_version,
                        client=client,
                        equipment_model=str(equipment_model),
                        unit_id=str(unit_id),
                        signal_name=signal,
                        operational_state=str(state),
                        training_start=training_start,
                        training_end=training_end,
                        fallback_level="unit"
                    )
                    
                    baselines.append(baseline_row)
        
        logger.info(f"Generated {len(baselines)} unit-level baselines")
        
        return pd.DataFrame(baselines) if baselines else pd.DataFrame()
    
    def _generate_model_level(
        self,
        df: pd.DataFrame,
        client: str,
        model_col: Optional[str],
        state_col: str,
        signals: List[str],
        baseline_version: str,
        training_start: datetime,
        training_end: datetime
    ) -> pd.DataFrame:
        """Generate model-level baselines (aggregated across units)."""
        logger.info("Generating model-level baselines...")
        
        if not model_col or model_col not in df.columns:
            logger.warning("No equipment_model column, skipping model-level baselines")
            return pd.DataFrame()
        
        baselines = []
        
        for equipment_model in df[model_col].unique():
            model_df = df[df[model_col] == equipment_model]
            
            for state in df[state_col].unique():
                state_df = model_df[model_df[state_col] == state]
                
                for signal in signals:
                    if signal not in df.columns:
                        continue
                    
                    signal_data = state_df[signal].dropna()
                    
                    if len(signal_data) < self.min_samples_required:
                        continue
                    
                    baseline_row = self._calculate_baseline_stats(
                        signal_data,
                        baseline_version=baseline_version,
                        client=client,
                        equipment_model=str(equipment_model),
                        unit_id=None,  # Model-level doesn't have specific unit
                        signal_name=signal,
                        operational_state=str(state),
                        training_start=training_start,
                        training_end=training_end,
                        fallback_level="model"
                    )
                    
                    baselines.append(baseline_row)
        
        logger.info(f"Generated {len(baselines)} model-level baselines")
        
        return pd.DataFrame(baselines) if baselines else pd.DataFrame()
    
    def _generate_client_level(
        self,
        df: pd.DataFrame,
        client: str,
        state_col: str,
        signals: List[str],
        baseline_version: str,
        training_start: datetime,
        training_end: datetime
    ) -> pd.DataFrame:
        """Generate client-level baselines (aggregated across all equipment)."""
        logger.info("Generating client-level baselines...")
        
        baselines = []
        
        for state in df[state_col].unique():
            state_df = df[df[state_col] == state]
            
            for signal in signals:
                if signal not in df.columns:
                    continue
                
                signal_data = state_df[signal].dropna()
                
                if len(signal_data) < self.min_samples_required:
                    continue
                
                baseline_row = self._calculate_baseline_stats(
                    signal_data,
                    baseline_version=baseline_version,
                    client=client,
                    equipment_model="All",  # Client-level aggregates all models
                    unit_id=None,
                    signal_name=signal,
                    operational_state=str(state),
                    training_start=training_start,
                    training_end=training_end,
                    fallback_level="client"
                )
                
                baselines.append(baseline_row)
        
        logger.info(f"Generated {len(baselines)} client-level baselines")
        
        return pd.DataFrame(baselines) if baselines else pd.DataFrame()
    
    def _calculate_baseline_stats(
        self,
        data: pd.Series,
        baseline_version: str,
        client: str,
        equipment_model: str,
        unit_id: Optional[str],
        signal_name: str,
        operational_state: str,
        training_start: datetime,
        training_end: datetime,
        fallback_level: str
    ) -> Dict[str, Any]:
        """Calculate baseline statistics for a signal."""
        # Percentiles
        percentile_values = {}
        for p in self.percentiles:
            percentile_values[f'p{p}'] = float(np.percentile(data, p))
        
        # Moments
        mean_val = float(data.mean())
        std_val = float(data.std())
        mad_val = float(np.median(np.abs(data - np.median(data))))
        
        # Quality score (based on sample count)
        sample_count = len(data)
        if sample_count >= 5000:
            quality_score = 1.0
        elif sample_count >= 2000:
            quality_score = 0.8
        elif sample_count >= 1000:
            quality_score = 0.6
        else:
            quality_score = 0.4
        
        baseline_row = {
            'baseline_version': baseline_version,
            'client': client,
            'equipment_model': equipment_model,
            'unit_id': unit_id,
            'signal_name': signal_name,
            'operational_state': operational_state,
            **percentile_values,
            'mean': mean_val,
            'std': std_val,
            'mad': mad_val,
            'sample_count': sample_count,
            'training_window_start': training_start,
            'training_window_end': training_end,
            'quality_score': quality_score,
            'fallback_level': fallback_level,
        }
        
        return baseline_row
    
    def _save_baselines(
        self,
        baselines_df: pd.DataFrame,
        baseline_version: str,
        training_start: datetime,
        training_end: datetime,
        output_dir: Path
    ) -> None:
        """Save baselines to Parquet and metadata to JSON."""
        ensure_dir(output_dir)
        
        # Save Parquet file
        baseline_file = output_dir / f"baseline_{baseline_version}.parquet"
        save_to_parquet(baselines_df, baseline_file)
        
        logger.info(f"Saved baseline to: {baseline_file}")
        
        # Save metadata
        metadata = {
            'baseline_version': baseline_version,
            'generation_timestamp': datetime.now().isoformat(),
            'training_window_start': training_start.isoformat(),
            'training_window_end': training_end.isoformat(),
            'total_records': len(baselines_df),
            'clients': baselines_df['client'].unique().tolist(),
            'signals': baselines_df['signal_name'].unique().tolist(),
            'states': baselines_df['operational_state'].unique().tolist(),
            'fallback_levels': baselines_df['fallback_level'].value_counts().to_dict(),
            'min_samples_required': self.min_samples_required,
            'percentiles_calculated': self.percentiles,
        }
        
        metadata_file = output_dir / "baseline_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Saved baseline metadata: {metadata_file}")
