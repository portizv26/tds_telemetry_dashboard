"""
Baseline management and retrieval with fallback hierarchy.
Implements baseline lookups: unit → model → client → global
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
import logging

from src.utils.file_utils import load_from_parquet, get_latest_baseline

logger = logging.getLogger(__name__)


class BaselineManager:
    """
    Manages baseline retrieval with fallback hierarchy.
    
    Implements lookup strategy:
    1. Unit-specific baseline (most specific)
    2. Equipment model baseline
    3. Client fleet baseline
    4. Global baseline (last resort)
    """
    
    def __init__(self, baselines_dir: Path):
        """
        Initialize baseline manager.
        
        Parameters
        ----------
        baselines_dir : Path
            Directory containing baseline files
        """
        self.baselines_dir = baselines_dir
        self._baseline_cache: Optional[pd.DataFrame] = None
        self._baseline_version: Optional[str] = None
    
    def load_baseline(self, baseline_version: Optional[str] = None) -> None:
        """
        Load baseline into memory.
        
        Parameters
        ----------
        baseline_version : Optional[str]
            Specific baseline version (YYYYMMDD). If None, uses latest
        """
        if baseline_version:
            baseline_file = self.baselines_dir / f"baseline_{baseline_version}.parquet"
        else:
            baseline_file = get_latest_baseline(self.baselines_dir)
        
        if not baseline_file or not baseline_file.exists():
            raise FileNotFoundError(f"Baseline not found: {baseline_file}")
        
        logger.info(f"Loading baseline: {baseline_file}")
        
        self._baseline_cache = load_from_parquet(baseline_file)
        self._baseline_version = baseline_version or baseline_file.stem.replace('baseline_', '')
        
        logger.info(f"Loaded {len(self._baseline_cache)} baseline records, version {self._baseline_version}")
    
    def get_baseline(
        self,
        client: str,
        signal_name: str,
        operational_state: str,
        unit_id: Optional[str] = None,
        equipment_model: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get baseline for signal with fallback hierarchy.
        
        Parameters
        ----------
        client : str
            Client identifier
        signal_name : str
            Signal name
        operational_state : str
            Operational state
        unit_id : Optional[str]
            Unit ID for unit-specific baseline
        equipment_model : Optional[str]
            Equipment model for model-specific baseline
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Baseline statistics or None if not found
        """
        if self._baseline_cache is None:
            raise RuntimeError("No baseline loaded. Call load_baseline() first")
        
        # Try unit-specific baseline
        if unit_id:
            baseline = self._lookup_baseline(
                client, signal_name, operational_state,
                unit_id=unit_id, equipment_model=equipment_model
            )
            if baseline is not None:
                return baseline
        
        # Try model-level baseline
        if equipment_model:
            baseline = self._lookup_baseline(
                client, signal_name, operational_state,
                equipment_model=equipment_model
            )
            if baseline is not None:
                return baseline
        
        # Try client-level baseline
        baseline = self._lookup_baseline(
            client, signal_name, operational_state
        )
        if baseline is not None:
            return baseline
        
        # No baseline found
        logger.warning(
            f"No baseline found for {client}/{signal_name}/{operational_state}"
        )
        return None
    
    def _lookup_baseline(
        self,
        client: str,
        signal_name: str,
        operational_state: str,
        unit_id: Optional[str] = None,
        equipment_model: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Internal baseline lookup."""
        # Build filter conditions
        mask = (
            (self._baseline_cache['client'] == client) &
            (self._baseline_cache['signal_name'] == signal_name) &
            (self._baseline_cache['operational_state'] == operational_state)
        )
        
        if unit_id:
            mask &= (self._baseline_cache['unit_id'] == unit_id)
        else:
            mask &= (self._baseline_cache['unit_id'].isnull())
        
        if equipment_model:
            mask &= (self._baseline_cache['equipment_model'] == equipment_model)
        
        matching_baselines = self._baseline_cache[mask]
        
        if len(matching_baselines) == 0:
            return None
        
        # Return first match (should be unique)
        baseline_row = matching_baselines.iloc[0]
        
        return baseline_row.to_dict()
    
    def get_baseline_version(self) -> Optional[str]:
        """
        Get currently loaded baseline version.
        
        Returns
        -------
        Optional[str]
            Baseline version (YYYYMMDD) or None if no baseline loaded
        """
        return self._baseline_version
    
    def get_available_signals(self, client: str) -> List[str]:
        """
        Get signals with available baselines for a client.
        
        Parameters
        ----------
        client : str
            Client identifier
            
        Returns
        -------
        List[str]
            List of signal names
        """
        if self._baseline_cache is None:
            return []
        
        client_baselines = self._baseline_cache[self._baseline_cache['client'] == client]
        return sorted(client_baselines['signal_name'].unique().tolist())
    
    def get_baseline_stats(self) -> Dict[str, Any]:
        """
        Get statistics about loaded baseline.
        
        Returns
        -------
        Dict[str, Any]
            Baseline statistics
        """
        if self._baseline_cache is None:
            return {}
        
        return {
            'version': self._baseline_version,
            'total_records': len(self._baseline_cache),
            'clients': self._baseline_cache['client'].unique().tolist(),
            'signals': len(self._baseline_cache['signal_name'].unique()),
            'states': self._baseline_cache['operational_state'].unique().tolist(),
            'fallback_distribution': self._baseline_cache['fallback_level'].value_counts().to_dict(),
        }
