"""
Technique Configuration management.
Loads and provides access to technique parameters from technique_config.yaml
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml


class TechniqueConfig:
    """
    Manages technique execution parameters and baseline configuration.
    
    Attributes
    ----------
    version : str
        Config version
    techniques : Dict[str, Dict[str, Any]]
        Technique name to configuration mapping
    baseline_config : Dict[str, Any]
        Baseline generation parameters
    """
    
    def __init__(self, config_path: Path):
        """
        Initialize technique configuration from YAML file.
        
        Parameters
        ----------
        config_path : Path
            Path to technique_config.yaml
            
        Raises
        ------
        FileNotFoundError
            If config file doesn't exist
        ValueError
            If configuration validation fails
        """
        self.config_path = config_path
        self.version = ""
        self.techniques: Dict[str, Dict[str, Any]] = {}
        self.baseline_config: Dict[str, Any] = {}
        
        self._load_config()
        self._validate_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Technique config not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Extract metadata
        self.version = data.get('version', '1.0')
        
        # Load technique configurations
        for technique_data in data.get('techniques', []):
            technique_name = technique_data['name']
            self.techniques[technique_name] = technique_data
        
        # Load baseline configuration
        self.baseline_config = data.get('baseline', {})
    
    def _validate_config(self) -> None:
        """
        Validate configuration consistency.
        
        Raises
        ------
        ValueError
            If validation fails
        """
        if not self.techniques:
            raise ValueError("No techniques defined in configuration")
        
        # Validate required technique fields
        required_fields = ['name', 'version', 'enabled', 'cadence']
        for technique_name, config in self.techniques.items():
            for field in required_fields:
                if field not in config:
                    raise ValueError(
                        f"Technique {technique_name} missing required field: {field}"
                    )
    
    def get_technique_config(self, technique_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a technique.
        
        Parameters
        ----------
        technique_name : str
            Technique identifier
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Technique configuration if found, None otherwise
        """
        return self.techniques.get(technique_name)
    
    def get_technique_parameter(
        self, 
        technique_name: str, 
        parameter_name: str, 
        default: Any = None
    ) -> Any:
        """
        Get specific parameter for a technique.
        
        Parameters
        ----------
        technique_name : str
            Technique identifier
        parameter_name : str
            Parameter name
        default : Any, optional
            Default value if parameter not found
            
        Returns
        -------
        Any
            Parameter value or default
        """
        config = self.get_technique_config(technique_name)
        if not config:
            return default
        
        # Check in parameters section first
        params = config.get('parameters', {})
        if parameter_name in params:
            return params[parameter_name]
        
        # Check at top level
        return config.get(parameter_name, default)
    
    def is_technique_enabled(self, technique_name: str) -> bool:
        """
        Check if technique is enabled.
        
        Parameters
        ----------
        technique_name : str
            Technique identifier
            
        Returns
        -------
        bool
            True if technique is enabled
        """
        config = self.get_technique_config(technique_name)
        if not config:
            return False
        return config.get('enabled', False)
    
    def get_technique_cadence(self, technique_name: str) -> str:
        """
        Get execution cadence for technique.
        
        Parameters
        ----------
        technique_name : str
            Technique identifier
            
        Returns
        -------
        str
            Cadence (e.g., "daily", "weekly", "6h")
        """
        config = self.get_technique_config(technique_name)
        if not config:
            return "daily"  # default
        return config.get('cadence', 'daily')
    
    def get_lookback_window(self, technique_name: str) -> str:
        """
        Get lookback window for technique.
        
        Parameters
        ----------
        technique_name : str
            Technique identifier
            
        Returns
        -------
        str
            Lookback window (e.g., "24h", "7d")
        """
        config = self.get_technique_config(technique_name)
        if not config:
            return "24h"  # default
        return config.get('lookback_window', '24h')
    
    def get_validity_period(self, technique_name: str) -> int:
        """
        Get result validity period in days.
        
        Parameters
        ----------
        technique_name : str
            Technique identifier
            
        Returns
        -------
        int
            Validity period in days
        """
        config = self.get_technique_config(technique_name)
        if not config:
            return 1  # default
        return config.get('validity_period_days', 1)
    
    def get_baseline_lookback_days(self) -> int:
        """
        Get baseline training window in days.
        
        Returns
        -------
        int
            Lookback days for baseline generation
        """
        return self.baseline_config.get('lookback_days', 90)
    
    def get_baseline_min_samples(self) -> int:
        """
        Get minimum samples required for valid baseline.
        
        Returns
        -------
        int
            Minimum sample count
        """
        return self.baseline_config.get('min_samples_required', 1000)
    
    def get_baseline_percentiles(self) -> List[int]:
        """
        Get percentiles to calculate in baseline.
        
        Returns
        -------
        List[int]
            Percentile values (e.g., [1, 5, 50, 95, 99])
        """
        return self.baseline_config.get('percentiles', [1, 2, 5, 10, 50, 90, 95, 98, 99])
    
    def get_baseline_fallback_hierarchy(self) -> List[str]:
        """
        Get baseline fallback hierarchy.
        
        Returns
        -------
        List[str]
            Fallback levels (e.g., ["unit", "model", "client", "global"])
        """
        return self.baseline_config.get('fallback_hierarchy', ['unit', 'model', 'client', 'global'])
    
    def get_all_technique_names(self) -> List[str]:
        """
        Get all technique names.
        
        Returns
        -------
        List[str]
            List of technique names
        """
        return list(self.techniques.keys())
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"TechniqueConfig(version={self.version}, "
            f"techniques={len(self.techniques)})"
        )
