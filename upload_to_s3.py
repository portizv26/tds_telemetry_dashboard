"""
Upload Telemetry Results to S3

This script uploads Golden layer analysis results to AWS S3.
It can be run standalone or as part of the pipeline workflow.

Usage:
    # Upload specific weeks
    python upload_to_s3.py --client cda --year 2026 --weeks 23 24 25 26
    
    # Upload all results for a client
    python upload_to_s3.py --client cda --all
    
    # Upload from specific directory
    python upload_to_s3.py --client cda --golden-path ./data/telemetry/golden --year 2026 --weeks 23
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

from src.utils.s3_uploader import create_uploader_from_env
from src.config.settings import build_config


def setup_logging():
    """Configure logging."""
    from pathlib import Path
    
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                logs_dir / f"s3_upload_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.log",
                encoding="utf-8",
            ),
        ],
    )


def main():
    parser = argparse.ArgumentParser(
        description="Upload Telemetry Analysis Results to S3"
    )
    parser.add_argument(
        "--client", type=str, required=True,
        help="Client identifier (e.g., cda, emin)"
    )
    parser.add_argument(
        "--year", type=int, default=None,
        help="Year to upload (e.g., 2026)"
    )
    parser.add_argument(
        "--weeks", nargs="*", type=int, default=None,
        help="Week numbers to upload (e.g., 23 24 25 26)"
    )
    parser.add_argument(
        "--golden-path", type=str, default=None,
        help="Path to golden layer directory (default: from config)"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Upload all available results for the client"
    )
    
    args = parser.parse_args()
    setup_logging()
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("S3 Upload Tool for Telemetry Analysis Results")
    logger.info("=" * 60)
    
    # Load configuration
    config = build_config(args.client)
    
    # Determine golden path
    golden_path = Path(args.golden_path) if args.golden_path else config.golden_path
    
    if not golden_path.exists():
        logger.error(f"Golden layer path not found: {golden_path}")
        return 1
    
    # Create S3 uploader
    try:
        uploader = create_uploader_from_env()
    except ValueError as e:
        logger.error(f"Failed to create S3 uploader: {e}")
        logger.error("Please configure AWS credentials in .env file")
        return 1
    
    # Validate upload configuration
    if not args.all and (args.year is None or args.weeks is None):
        logger.error("Must specify either --all or both --year and --weeks")
        return 1
    
    # Execute upload
    successful = 0
    try:
        if args.all:
            logger.info(f"Uploading all results for {args.client}...")
            results = uploader.upload_golden_layer(
                client=args.client,
                golden_path=golden_path
            )
            
            # Summary
            total_files = sum(len(category_results) for category_results in results.values())
            successful = sum(
                sum(1 for success in category_results.values() if success)
                for category_results in results.values()
            )
            
            logger.info("=" * 60)
            logger.info(f"UPLOAD SUMMARY")
            logger.info("=" * 60)
            logger.info(f"  Client: {args.client}")
            logger.info(f"  Total files: {total_files}")
            logger.info(f"  Successful: {successful}")
            logger.info(f"  Failed: {total_files - successful}")
            
        else:
            logger.info(f"Uploading weeks {args.weeks} of year {args.year} for {args.client}...")
            summary = uploader.upload_specific_weeks(
                client=args.client,
                golden_path=golden_path,
                year=args.year,
                weeks=args.weeks
            )
            
            successful = summary['successful']
            
            logger.info("=" * 60)
            logger.info(f"UPLOAD SUMMARY")
            logger.info("=" * 60)
            logger.info(f"  Client: {summary['client']}")
            logger.info(f"  Year: {summary['year']}")
            logger.info(f"  Weeks: {summary['weeks']}")
            logger.info(f"  Total files: {summary['total_files']}")
            logger.info(f"  Successful: {summary['successful']}")
            logger.info(f"  Failed: {summary['failed']}")
        
        return 0 if successful > 0 else 1
        
    except Exception as e:
        logger.error(f"Upload failed with error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
