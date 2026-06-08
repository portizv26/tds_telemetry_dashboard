"""
Signal Registry management.
Loads and provides access to signal metadata from signal_registry_v1.yaml
"""

from pathlib import Path
from typing import Dict, List, Optional, Set
import yaml

from src.models.entities import Signal, System


class SignalRegistry:
    """
    Manages signal metadata and system mappings.
    
    Provides methods to query signal information, validate signal names,
    and retrieve system-level groupings.
    
    Attributes
    ----------
    version : str
        Registry version
    signals : Dict[str, Signal]
        Signal name to Signal object mapping
    systems : Dict[str, System]
        System name to System object mapping
    system_criticality : Dict[str, float]
        System criticality weights
    operational_states : List[str]
        Valid operational states
    """
    
    def __init__(self, config_path: Path):
        """
        Initialize signal registry from YAML file.
        
        Parameters
        ----------
        config_path : Path
            Path to signal_registry_v1.yaml
            
        Raises
        ------
        FileNotFoundError
            If config file doesn't exist
        ValueError
            If registry validation fails
        """
        self.config_path = config_path
        self.version = ""
        self.signals: Dict[str, Signal] = {}
        self.systems: Dict[str, System] = {}
        self.system_criticality: Dict[str, float] = {}
        self.operational_states: List[str] = []
        
        self._load_registry()
        self._validate_registry()
    
    def _load_registry(self) -> None:
        """Load registry from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Signal registry not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Extract metadata
        self.version = data.get('version', '1.0')
        self.system_criticality = data.get('system_criticality', {})
        self.operational_states = data.get('operational_states', [])
        
        # Load signals
        for signal_data in data.get('signals', []):
            signal = Signal(
                name=signal_data['name'],
                display_name=signal_data['display_name'],
                system=signal_data['system'],
                subsystem=signal_data.get('subsystem', ''),
                unit=signal_data['unit'],
                risk_direction=signal_data['risk_direction'],
                valid_states=signal_data['valid_states'],
                physical_min=signal_data['physical_min'],
                physical_max=signal_data['physical_max'],
                criticality=signal_data['criticality'],
                enabled_techniques=signal_data.get('enabled_techniques', []),
                description=signal_data.get('description', '')
            )
            self.signals[signal.name] = signal
        
        # Build system groupings
        self._build_systems()
    
    def _build_systems(self) -> None:
        """Build system groupings from signals."""
        system_signals: Dict[str, List[str]] = {}
        
        for signal_name, signal in self.signals.items():
            system_name = signal.system
            if system_name not in system_signals:
                system_signals[system_name] = []
            system_signals[system_name].append(signal_name)
        
        # Create System objects
        for system_name, signal_list in system_signals.items():
            self.systems[system_name] = System(
                name=system_name,
                signals=signal_list,
                criticality=self.system_criticality.get(system_name, 0.5),
                description=f"{system_name} system"
            )
    
    def _validate_registry(self) -> None:
        """
        Validate registry consistency.
        
        Raises
        ------
        ValueError
            If validation fails
        """
        if not self.signals:
            raise ValueError("Signal registry is empty")
        
        if not self.systems:
            raise ValueError("No systems defined in registry")
        
        # Validate risk directions
        valid_directions = {'high', 'low', 'both'}
        for signal_name, signal in self.signals.items():
            if signal.risk_direction not in valid_directions:
                raise ValueError(
                    f"Signal {signal_name} has invalid risk_direction: {signal.risk_direction}"
                )
        
        # Validate criticality values
        for signal_name, signal in self.signals.items():
            if not 1 <= signal.criticality <= 3:
                raise ValueError(
                    f"Signal {signal_name} has invalid criticality: {signal.criticality}"
                )
    
    def get_signal(self, signal_name: str) -> Optional[Signal]:
        """
        Get signal by name.
        
        Parameters
        ----------
        signal_name : str
            Signal identifier
            
        Returns
        -------
        Optional[Signal]
            Signal object if found, None otherwise
        """
        return self.signals.get(signal_name)
    
    def get_signals_by_system(self, system_name: str) -> List[Signal]:
        """
        Get all signals for a system.
        
        Parameters
        ----------
        system_name : str
            System name
            
        Returns
        -------
        List[Signal]
            List of signals in system
        """
        if system_name not in self.systems:
            return []
        
        signal_names = self.systems[system_name].signals
        return [self.signals[name] for name in signal_names if name in self.signals]
    
    def get_signals_by_technique(self, technique_name: str) -> List[Signal]:
        """
        Get signals that enable a specific technique.
        
        Parameters
        ----------
        technique_name : str
            Technique identifier
            
        Returns
        -------
        List[Signal]
            List of signals with technique enabled
        """
        return [
            signal for signal in self.signals.values()
            if technique_name in signal.enabled_techniques
        ]
    
    def is_technique_enabled(self, signal_name: str, technique_name: str) -> bool:
        """
        Check if technique is enabled for signal.
        
        Parameters
        ----------
        signal_name : str
            Signal identifier
        technique_name : str
            Technique identifier
            
        Returns
        -------
        bool
            True if technique is enabled
        """
        signal = self.get_signal(signal_name)
        if not signal:
            return False
        return technique_name in signal.enabled_techniques
    
    def get_system_criticality(self, system_name: str) -> float:
        """
        Get system criticality weight.
        
        Parameters
        ----------
        system_name : str
            System name
            
        Returns
        -------
        float
            Criticality weight (0-1)
        """
        return self.system_criticality.get(system_name, 0.5)
    
    def get_all_systems(self) -> List[str]:
        """
        Get all system names.
        
        Returns
        -------
        List[str]
            List of system names
        """
        return list(self.systems.keys())
    
    def get_all_signal_names(self) -> List[str]:
        """
        Get all signal names.
        
        Returns
        -------
        List[str]
            List of signal names
        """
        return list(self.signals.keys())
    
    def validate_signal_name(self, signal_name: str) -> bool:
        """
        Check if signal exists in registry.
        
        Parameters
        ----------
        signal_name : str
            Signal identifier
            
        Returns
        -------
        bool
            True if signal exists
        """
        return signal_name in self.signals
    
    def get_valid_states(self, signal_name: str) -> List[str]:
        """
        Get valid operational states for signal.
        
        Parameters
        ----------
        signal_name : str
            Signal identifier
            
        Returns
        -------
        List[str]
            List of valid operational states
        """
        signal = self.get_signal(signal_name)
        if not signal:
            return []
        return signal.valid_states
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"SignalRegistry(version={self.version}, "
            f"signals={len(self.signals)}, "
            f"systems={len(self.systems)})"
        )
