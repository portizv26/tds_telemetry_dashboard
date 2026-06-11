"""
Configuration module — loads and validates analysis parameters,
signal registry, equipment registry, and environment settings.
"""

import os
import yaml
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Column name constants ─────────────────────────────────────────────────────
UNIT_COLNAME = "Unit"
STATE_COLNAME = "Estado"
TIME_COLNAME = "Fecha"

# ─── Default paths (relative to project root) ─────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SILVER_PATH = PROJECT_ROOT / "data" / "telemetry" / "silver"
DEFAULT_GOLDEN_PATH = PROJECT_ROOT / "data" / "telemetry" / "golden"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "data" / "telemetry" / "config"


@dataclass
class DeviationConfig:
    baseline_weeks: int = 12
    percentiles: list = field(default_factory=lambda: [1, 2, 5, 10, 25, 50, 75, 90, 95, 98, 99])
    min_unique_values: int = 10


@dataclass
class EventConfig:
    spike_max_minutes: int = 5
    anomaly_max_minutes: int = 30
    spike_max_points: int = 10
    anomaly_max_points: int = 30
    severity_weights: dict = field(default_factory=lambda: {"alert": 1, "anormal": 3, "critical": 5})


@dataclass
class TrendConfig:
    window_weeks: list = field(default_factory=lambda: [4, 8, 12])
    rolling_window_minutes: int = 30
    p_value_threshold: float = 0.05
    r2_threshold: float = 0.3
    min_data_points: int = 10


@dataclass
class DistributionConfig:
    baseline_weeks: int = 52
    observation_weeks: list = field(default_factory=lambda: [4, 8, 12])
    p_value_threshold: float = 0.05
    min_baseline_samples: int = 100
    min_observation_samples: int = 30


@dataclass
class AutoencoderConfig:
    sequence_length: int = 30
    quality_threshold: float = 0.10
    encoding_dim: int = 32
    epochs: int = 50
    batch_size: int = 32
    validation_split: float = 0.2
    early_stopping_patience: int = 10


@dataclass
class AggregationConfig:
    validity_hours_autoencoder: int = 12
    validity_days_deviation: int = 2
    validity_days_event: int = 2
    validity_days_distribution: int = 7
    validity_weeks_trend: int = 4
    weight_max_critical: float = 0.4
    weight_mean: float = 0.3
    weight_persistence: float = 0.2
    weight_trend: float = 0.1
    normal_max: int = 40
    alerta_max: int = 70


@dataclass
class LLMConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 1000
    rate_limit_delay: float = 0.5
    skip_normal_units: bool = True
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))


@dataclass
class AICommentsConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens_signal: int = 400
    max_tokens_system: int = 600
    max_tokens_unit: int = 700
    rate_limit_delay: float = 0.5
    skip_normal: bool = True
    batch_size: int = 5
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))


@dataclass
class PipelineConfig:
    """Top-level configuration aggregating all sub-configs."""
    client: str = "cda"
    silver_path: Path = field(default_factory=lambda: Path(os.getenv("SILVER_DATA_PATH", str(DEFAULT_SILVER_PATH))))
    golden_path: Path = field(default_factory=lambda: Path(os.getenv("GOLDEN_DATA_PATH", str(DEFAULT_GOLDEN_PATH))))
    config_path: Path = field(default_factory=lambda: Path(os.getenv("CONFIG_PATH", str(DEFAULT_CONFIG_PATH))))
    deviation: DeviationConfig = field(default_factory=DeviationConfig)
    event: EventConfig = field(default_factory=EventConfig)
    trend: TrendConfig = field(default_factory=TrendConfig)
    distribution: DistributionConfig = field(default_factory=DistributionConfig)
    autoencoder: AutoencoderConfig = field(default_factory=AutoencoderConfig)
    aggregation: AggregationConfig = field(default_factory=AggregationConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    ai_comments: AICommentsConfig = field(default_factory=AICommentsConfig)

    @property
    def telemetry_path(self) -> Path:
        return self.silver_path / self.client / "Telemetry_Wide_With_States"

    @property
    def baselines_path(self) -> Path:
        return self.silver_path / self.client / "baselines"

    @property
    def limits_path(self) -> Path:
        return self.silver_path / self.client / "limits"

    @property
    def signal_registry_path(self) -> Path:
        return self.config_path / self.client / "signal_registry.yaml"

    @property
    def equipment_registry_path(self) -> Path:
        return self.config_path / self.client / "equipment_registry.yaml"

    @property
    def output_path(self) -> Path:
        return self.golden_path / self.client


def load_yaml(file_path: Path) -> dict:
    """Load a YAML configuration file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error reading YAML file {file_path}: {e}")
        raise


def load_signal_registry(config: PipelineConfig) -> dict:
    """Load signal registry metadata."""
    return load_yaml(config.signal_registry_path)


def load_equipment_registry(config: PipelineConfig) -> dict:
    """Load equipment registry metadata."""
    return load_yaml(config.equipment_registry_path)


def load_analysis_config(config_path: Path, client: str) -> Optional[dict]:
    """Load analysis_config.yaml if present, else return None (use defaults)."""
    path = config_path / client / "analysis_config.yaml"
    if path.exists():
        return load_yaml(path)
    return None


def build_config(client: str = "cda") -> PipelineConfig:
    """Build full pipeline configuration, merging file-based overrides with defaults."""
    config = PipelineConfig(client=client)

    overrides = load_analysis_config(config.config_path, client)
    if overrides:
        if "deviation_analysis" in overrides:
            for k, v in overrides["deviation_analysis"].items():
                if hasattr(config.deviation, k):
                    setattr(config.deviation, k, v)
        if "trend_analysis" in overrides:
            for k, v in overrides["trend_analysis"].items():
                if hasattr(config.trend, k):
                    setattr(config.trend, k, v)
        if "distribution_analysis" in overrides:
            for k, v in overrides["distribution_analysis"].items():
                if hasattr(config.distribution, k):
                    setattr(config.distribution, k, v)
        if "anomaly_detection" in overrides:
            for k, v in overrides["anomaly_detection"].items():
                if hasattr(config.autoencoder, k):
                    setattr(config.autoencoder, k, v)
        if "llm" in overrides:
            for k, v in overrides["llm"].items():
                if hasattr(config.llm, k):
                    setattr(config.llm, k, v)
        if "ai_comments" in overrides:
            for k, v in overrides["ai_comments"].items():
                if hasattr(config.ai_comments, k):
                    setattr(config.ai_comments, k, v)

    logger.info(f"Configuration built for client={client}")
    return config
