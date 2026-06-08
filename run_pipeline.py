"""
Main entry point for Telemetry Health Evaluation Pipeline.
Supports Phase 1 baseline generation and data profiling.
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestration import generate_baselines_flow, profile_data_flow
from src.utils.logger import setup_logger


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Telemetry Health Evaluation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate baselines for client CDA with 90 days of history
  python run_pipeline.py --generate-baselines --client CDA --lookback-days 90
  
  # Profile data quality for specific week
  python run_pipeline.py --profile-data --client CDA --week 21 --year 2026
  
  # Run full pipeline (Phase 1 only for now)
  python run_pipeline.py --client CDA --week 21 --year 2026
        """
    )
    
    # Mode selection
    parser.add_argument(
        '--generate-baselines',
        action='store_true',
        help='Generate baselines from historical data'
    )
    parser.add_argument(
        '--profile-data',
        action='store_true',
        help='Profile data quality for a week'
    )
    
    # Required parameters
    parser.add_argument(
        '--client',
        type=str,
        required=True,
        help='Client identifier (e.g., CDA, EMIN)'
    )
    
    # Week/year for profiling or evaluation
    parser.add_argument(
        '--week',
        type=int,
        help='ISO week number (1-53)'
    )
    parser.add_argument(
        '--year',
        type=int,
        help='Year'
    )
    
    # Baseline generation parameters
    parser.add_argument(
        '--lookback-days',
        type=int,
        default=90,
        help='Days of historical data for baseline generation (default: 90)'
    )
    
    # Directory paths
    parser.add_argument(
        '--silver-dir',
        type=Path,
        default=Path('data/telemetry/silver'),
        help='Silver data directory (default: data/telemetry/silver)'
    )
    parser.add_argument(
        '--config-dir',
        type=Path,
        default=Path('data/telemetry/config'),
        help='Config directory (default: data/telemetry/config)'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        help='Output directory (default: depends on operation)'
    )
    
    # Logging
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    parser.add_argument(
        '--log-dir',
        type=Path,
        default=Path('logs'),
        help='Log directory (default: logs)'
    )
    
    return parser.parse_args()


def main():
    """Main pipeline execution."""
    args = parse_args()
    
    # Setup logging
    log_level = getattr(logging, args.log_level)
    logger = setup_logger(
        name='telemetry_pipeline',
        log_dir=args.log_dir,
        level=log_level
    )
    
    logger.info("=" * 80)
    logger.info("Telemetry Health Evaluation Pipeline - Phase 1")
    logger.info("=" * 80)
    logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Client: {args.client}")
    logger.info("")
    
    try:
        # Generate baselines
        if args.generate_baselines:
            logger.info("Mode: Generate Baselines")
            logger.info(f"Lookback days: {args.lookback_days}")
            
            output_dir = args.output_dir or Path('data/telemetry/analytical_results/baselines')
            
            baseline_file = generate_baselines_flow(
                client=args.client,
                lookback_days=args.lookback_days,
                silver_dir=args.silver_dir,
                config_dir=args.config_dir,
                output_dir=output_dir
            )
            
            logger.info(f"✓ Baseline generation complete: {baseline_file}")
        
        # Profile data quality
        elif args.profile_data:
            if not args.week or not args.year:
                logger.error("--week and --year are required for data profiling")
                sys.exit(1)
            
            logger.info("Mode: Profile Data Quality")
            logger.info(f"Week: {args.week}, Year: {args.year}")
            
            output_dir = args.output_dir or Path('outputs/profiling')
            
            profile = profile_data_flow(
                client=args.client,
                week=args.week,
                year=args.year,
                silver_dir=args.silver_dir,
                config_dir=args.config_dir,
                output_dir=output_dir
            )
            
            logger.info(f"✓ Data profiling complete")
            logger.info(f"  Coverage: {profile['data_quality']['average_coverage_pct']:.1f}%")
            logger.info(f"  Quality: {profile['data_quality']['quality_score']}")
        
        # Full pipeline (Phase 1 only for now)
        else:
            logger.info("Mode: Full Pipeline (Phase 1)")
            
            if not args.week or not args.year:
                logger.error("--week and --year are required for full pipeline")
                sys.exit(1)
            
            # Step 1: Profile data
            logger.info("\nStep 1/2: Profiling data quality...")
            profile = profile_data_flow(
                client=args.client,
                week=args.week,
                year=args.year,
                silver_dir=args.silver_dir,
                config_dir=args.config_dir,
                output_dir=Path('outputs/profiling')
            )
            logger.info(f"✓ Coverage: {profile['data_quality']['average_coverage_pct']:.1f}%")
            
            # Step 2: Check if baselines exist, if not, generate them
            logger.info("\nStep 2/2: Checking baselines...")
            baseline_dir = Path('data/telemetry/analytical_results/baselines')
            baseline_files = list(baseline_dir.glob('baseline_*.parquet')) if baseline_dir.exists() else []
            
            if not baseline_files:
                logger.info("No baselines found. Generating baselines...")
                baseline_file = generate_baselines_flow(
                    client=args.client,
                    lookback_days=args.lookback_days,
                    silver_dir=args.silver_dir,
                    config_dir=args.config_dir,
                    output_dir=baseline_dir
                )
                logger.info(f"✓ Baselines generated: {baseline_file}")
            else:
                latest_baseline = sorted(baseline_files, reverse=True)[0]
                logger.info(f"✓ Using existing baseline: {latest_baseline}")
            
            logger.info("\n✓ Phase 1 pipeline complete!")
            logger.info("  Next: Implement Phase 2 analytical techniques")
        
        # Success
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("Pipeline execution successful!")
        logger.info("=" * 80)
        
        return 0
    
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        logger.info("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
