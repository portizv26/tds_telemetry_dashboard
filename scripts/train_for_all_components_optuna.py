"""
Training script — train all components with Optuna optimisation.

Usage
-----
    python -m scripts.train_for_all_components_optuna
    python -m scripts.train_for_all_components_optuna --config configs/health_index_cda.yaml
    python -m scripts.train_for_all_components_optuna --components Motor "Tren de fuerza"
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.telemetry.health_index.config import load_config
from src.telemetry.health_index.pipeline import run_training
from src.utils.logger import get_logger

logger = get_logger("train_all")

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "health_index_cda.yaml"


def main():
    parser = argparse.ArgumentParser(
        description="Train LSTM health-index models for all (or selected) components.",
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=str(DEFAULT_CONFIG),
        help="Path to YAML config file.",
    )
    parser.add_argument(
        "--components",
        nargs="+",
        default=None,
        help="Subset of components to train (default: all).",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    logger.info(f"Config loaded: {args.config}")
    logger.info(f"Components: {args.components or 'ALL'}")

    estimators = run_training(cfg, components=args.components)

    for comp, est in estimators.items():
        logger.info(
            f"  {comp}: fitted={est.is_fitted_}  "
            f"params={est.best_params_}"
        )

    logger.info("Training pipeline finished.")


if __name__ == "__main__":
    main()
