"""
Configuration loader for the Health Index pipeline.

Reads a YAML config file and exposes typed helpers so the rest of
the pipeline never touches raw dicts.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HealthIndexConfig:
    """Immutable, validated configuration for one pipeline run."""

    # ── identifiers ─────────────────────────────────────────────────────
    client: str

    # ── column names ────────────────────────────────────────────────────
    unit_col: str
    time_col: str
    cat_cols: List[str]

    # ── preprocessing ───────────────────────────────────────────────────
    freq: str
    gap_threshold_minutes: int
    min_duration_hours: int
    min_coverage: float
    interpolation_limit: int
    default_cat_values: Dict[str, str]
    margins: Dict[str, Tuple[float, float]]
    drop_columns: List[str]

    # ── model ───────────────────────────────────────────────────────────
    window_size: int
    impute_fill_value: float
    seed: int

    # ── training ────────────────────────────────────────────────────────
    epochs: int
    patience: int
    validation_split: float
    default_params: Dict[str, Any]

    # ── optimisation ────────────────────────────────────────────────────
    optimization_enabled: bool
    n_trials: int
    optuna_epochs: int
    optuna_patience: int

    # ── split ───────────────────────────────────────────────────────────
    test_weeks: int

    # ── health index ────────────────────────────────────────────────────
    error_quantile: float

    # ── labelling ───────────────────────────────────────────────────────
    anomaly_ratio: float

    # ── resolved paths ──────────────────────────────────────────────────
    root_dir: Path = field(repr=False)
    data_silver: Path = field(repr=False)
    data_golden: Path = field(repr=False)
    models_dir: Path = field(repr=False)
    component_mapping_path: Path = field(repr=False)

    # ── cached mapping ──────────────────────────────────────────────────
    _component_mapping: Dict = field(default_factory=dict, repr=False)

    @property
    def component_mapping(self) -> Dict:
        if not self._component_mapping:
            with open(self.component_mapping_path, "r") as f:
                self._component_mapping = json.load(f)
        return self._component_mapping

    def signal_cols_for(self, component: str, df_columns: List[str]) -> List[str]:
        """Return signal columns for *component* that exist in *df_columns*."""
        signals = self.component_mapping["components"][component]["signals"]
        return [c for c in signals if c in df_columns]


def load_config(yaml_path: str | Path) -> HealthIndexConfig:
    """Load a YAML config and return a validated ``HealthIndexConfig``."""
    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"Config not found: {yaml_path}")

    with open(yaml_path, "r") as f:
        raw = yaml.safe_load(f)

    root_dir = yaml_path.parent.parent.resolve()  # configs/ → project root

    margins = {
        k: tuple(v) for k, v in raw["preprocessing"]["margins"].items()
    }

    cfg = HealthIndexConfig(
        client=raw["client"],
        # columns
        unit_col=raw["columns"]["unit"],
        time_col=raw["columns"]["time"],
        cat_cols=raw["columns"]["categorical"],
        # preprocessing
        freq=raw["preprocessing"]["freq"],
        gap_threshold_minutes=raw["preprocessing"]["gap_threshold_minutes"],
        min_duration_hours=raw["preprocessing"]["min_duration_hours"],
        min_coverage=raw["preprocessing"]["min_coverage"],
        interpolation_limit=raw["preprocessing"]["interpolation_limit"],
        default_cat_values=raw["preprocessing"]["default_cat_values"],
        margins=margins,
        drop_columns=raw["preprocessing"].get("drop_columns", []),
        # model
        window_size=raw["model"]["window_size"],
        impute_fill_value=raw["model"]["impute_fill_value"],
        seed=raw["model"]["seed"],
        # training
        epochs=raw["training"]["epochs"],
        patience=raw["training"]["patience"],
        validation_split=raw["training"]["validation_split"],
        default_params=raw["training"]["default_params"],
        # optimisation
        optimization_enabled=raw["optimization"]["enabled"],
        n_trials=raw["optimization"]["n_trials"],
        optuna_epochs=raw["optimization"]["optuna_epochs"],
        optuna_patience=raw["optimization"]["optuna_patience"],
        # split
        test_weeks=raw["split"]["test_weeks"],
        # health index
        error_quantile=raw["health_index"]["error_quantile"],
        # labelling
        anomaly_ratio=raw["labelling"]["anomaly_ratio"],
        # paths
        root_dir=root_dir,
        data_silver=root_dir / raw["paths"]["data_silver"],
        data_golden=root_dir / raw["paths"]["data_golden"],
        models_dir=root_dir / raw["paths"]["models"],
        component_mapping_path=root_dir / raw["paths"]["component_mapping"],
    )

    logger.info(f"Config loaded: client={cfg.client}  root={cfg.root_dir}")
    return cfg
