"""
Inference script — run predict() on the full test dataset.

Usage
-----
    python -m scripts.predict_in_test
    python -m scripts.predict_in_test --config configs/health_index_cda.yaml
    python -m scripts.predict_in_test --components Motor Frenos
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.telemetry.health_index.config import load_config
from src.telemetry.health_index.pipeline import run_inference
from src.utils.logger import get_logger

logger = get_logger("predict_test")

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "health_index_cda.yaml"


def main():
    parser = argparse.ArgumentParser(
        description="Run health-index inference on the test split for all (or selected) components.",
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
        help="Subset of components to predict (default: all).",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    logger.info(f"Config loaded: {args.config}")
    logger.info(f"Components: {args.components or 'ALL'}")

    health_df = run_inference(cfg, components=args.components)

    logger.info(f"Results shape: {health_df.shape}")
    logger.info(f"\n{health_df.groupby('component')['health_index'].describe().to_string()}")
    logger.info("Inference pipeline finished.")


if __name__ == "__main__":
    main()
