"""
CLI entry point for the Telemetry Health Evaluation Pipeline.

Usage:
    python -m src.main --client cda
    python -m src.main --client cda --weeks Week22Year2026 Week23Year2026
    python -m src.main --client cda --skip-autoencoder --skip-llm
"""

import argparse
import json
import logging
import sys
from datetime import datetime

from src.pipeline import TelemetryPipeline


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                f"telemetry_pipeline_{datetime.utcnow().strftime('%Y%m%d')}.log",
                encoding="utf-8",
            ),
        ],
    )


def main():
    parser = argparse.ArgumentParser(
        description="Telemetry Health Evaluation Pipeline"
    )
    parser.add_argument(
        "--client", type=str, default="cda",
        help="Client identifier (default: cda)"
    )
    parser.add_argument(
        "--weeks", nargs="*", default=None,
        help="Specific weekly files to process (e.g., Week22Year2026)"
    )
    parser.add_argument(
        "--skip-autoencoder", action="store_true",
        help="Skip LSTM autoencoder training/inference"
    )
    parser.add_argument(
        "--skip-llm", action="store_true",
        help="Skip LLM explanation generation"
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()
    setup_logging(args.log_level)

    logger = logging.getLogger(__name__)
    logger.info("Telemetry Health Evaluation Pipeline v1.0.0")

    pipeline = TelemetryPipeline(client=args.client, weeks=args.weeks)
    summary = pipeline.run(
        skip_autoencoder=args.skip_autoencoder,
        skip_llm=args.skip_llm,
    )

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("EXECUTION SUMMARY")
    logger.info("=" * 60)
    for key, value in summary.items():
        logger.info(f"  {key}: {value}")

    # Write summary JSON
    summary_path = f"pipeline_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    logger.info(f"Summary written to {summary_path}")

    return 0 if summary.get("units_processed", 0) > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
