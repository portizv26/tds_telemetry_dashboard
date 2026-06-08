"""
Convenient CLI wrapper for S3 sync operations.
Provides easy commands for common upload/download scenarios.

Usage:
    python sync_s3.py download baselines
    python sync_s3.py upload profiles
    python sync_s3.py backup-all
    python sync_s3.py sync-client CDA
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

from src.utils.logger import setup_logger, get_logger

logger = get_logger(__name__)


def run_command(cmd: List[str]) -> int:
    """Run a command and return exit code."""
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


def download_baselines() -> int:
    """Download baselines from S3."""
    logger.info("Downloading baselines from S3...")
    return run_command(["python", "-m", "src.s3_downloader", "--data-type", "baselines"])


def download_profiles() -> int:
    """Download profiles from S3."""
    logger.info("Downloading profiles from S3...")
    return run_command(["python", "-m", "src.s3_downloader", "--data-type", "profiles"])


def download_config() -> int:
    """Download config files from S3."""
    logger.info("Downloading config files from S3...")
    return run_command(["python", "-m", "src.s3_downloader", "--data-type", "config"])


def download_silver(client: str) -> int:
    """Download Silver layer data for a client."""
    logger.info(f"Downloading Silver layer data for {client} from S3...")
    return run_command(["python", "-m", "src.s3_downloader", "--data-type", "silver", "--client", client])


def upload_baselines() -> int:
    """Upload baselines to S3."""
    logger.info("Uploading baselines to S3...")
    return run_command(["python", "-m", "src.s3_uploader", "--data-type", "baselines"])


def upload_profiles() -> int:
    """Upload profiles to S3."""
    logger.info("Uploading profiles to S3...")
    return run_command(["python", "-m", "src.s3_uploader", "--data-type", "profiles"])


def upload_config() -> int:
    """Upload config files to S3."""
    logger.info("Uploading config files to S3...")
    return run_command(["python", "-m", "src.s3_uploader", "--data-type", "config"])


def upload_silver(client: str) -> int:
    """Upload Silver layer data for a client."""
    logger.info(f"Uploading Silver layer data for {client} to S3...")
    return run_command(["python", "-m", "src.s3_uploader", "--data-type", "silver", "--client", client])


def backup_all() -> int:
    """Backup all analysis results to S3."""
    logger.info("=" * 60)
    logger.info("BACKING UP ALL ANALYSIS RESULTS TO S3")
    logger.info("=" * 60)
    
    # Upload baselines
    result = upload_baselines()
    if result != 0:
        logger.error("Failed to upload baselines")
        return result
    
    # Upload profiles
    result = upload_profiles()
    if result != 0:
        logger.error("Failed to upload profiles")
        return result
    
    logger.info("=" * 60)
    logger.info("✓ All analysis results backed up successfully!")
    logger.info("=" * 60)
    return 0


def sync_client(client: str, direction: str = "both") -> int:
    """
    Sync all data for a specific client.
    
    Args:
        client: Client identifier (e.g., 'CDA')
        direction: 'download', 'upload', or 'both'
    """
    logger.info("=" * 60)
    logger.info(f"SYNCING CLIENT: {client}")
    logger.info("=" * 60)
    
    if direction in ["download", "both"]:
        logger.info("Downloading Silver layer data...")
        result = download_silver(client)
        if result != 0:
            logger.error(f"Failed to download Silver data for {client}")
            return result
    
    if direction in ["upload", "both"]:
        logger.info("Uploading Silver layer data...")
        result = upload_silver(client)
        if result != 0:
            logger.error(f"Failed to upload Silver data for {client}")
            return result
    
    logger.info("=" * 60)
    logger.info(f"✓ Client {client} synced successfully!")
    logger.info("=" * 60)
    return 0


def setup_new_environment() -> int:
    """Set up a new environment by downloading all necessary data from S3."""
    logger.info("=" * 60)
    logger.info("SETTING UP NEW ENVIRONMENT FROM S3")
    logger.info("=" * 60)
    
    # Download config files
    logger.info("Step 1: Downloading config files...")
    result = download_config()
    if result != 0:
        logger.error("Failed to download config files")
        return result
    
    # Download baselines
    logger.info("Step 2: Downloading baselines...")
    result = download_baselines()
    if result != 0:
        logger.warning("Failed to download baselines (may not exist yet)")
    
    # Download profiles
    logger.info("Step 3: Downloading profiles...")
    result = download_profiles()
    if result != 0:
        logger.warning("Failed to download profiles (may not exist yet)")
    
    logger.info("=" * 60)
    logger.info("✓ New environment setup complete!")
    logger.info("=" * 60)
    logger.info("Next steps:")
    logger.info("  1. Download Silver data: python sync_s3.py download silver CDA")
    logger.info("  2. Run historical analysis: python run_historical_analysis.py --client CDA")
    logger.info("=" * 60)
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convenient S3 sync operations for telemetry data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download operations
  python sync_s3.py download baselines
  python sync_s3.py download profiles
  python sync_s3.py download config
  python sync_s3.py download silver CDA
  
  # Upload operations
  python sync_s3.py upload baselines
  python sync_s3.py upload profiles
  python sync_s3.py upload silver CDA
  
  # Combined operations
  python sync_s3.py backup-all              # Upload all results
  python sync_s3.py sync-client CDA         # Download & upload Silver data
  python sync_s3.py setup                   # Set up new environment
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download data from S3')
    download_parser.add_argument(
        'data_type',
        choices=['baselines', 'profiles', 'config', 'silver'],
        help='Type of data to download'
    )
    download_parser.add_argument(
        'client',
        nargs='?',
        help='Client identifier (required for silver data type)'
    )
    
    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload data to S3')
    upload_parser.add_argument(
        'data_type',
        choices=['baselines', 'profiles', 'config', 'silver'],
        help='Type of data to upload'
    )
    upload_parser.add_argument(
        'client',
        nargs='?',
        help='Client identifier (required for silver data type)'
    )
    
    # Backup all command
    subparsers.add_parser('backup-all', help='Backup all analysis results (baselines + profiles)')
    
    # Sync client command
    sync_parser = subparsers.add_parser('sync-client', help='Sync Silver data for a client')
    sync_parser.add_argument('client', help='Client identifier')
    sync_parser.add_argument(
        '--direction',
        choices=['download', 'upload', 'both'],
        default='both',
        help='Sync direction (default: both)'
    )
    
    # Setup command
    subparsers.add_parser('setup', help='Set up new environment from S3')
    
    args = parser.parse_args()
    
    # Setup logger
    import logging
    setup_logger(__name__, level=logging.INFO)
    
    # Execute command
    if args.command == 'download':
        if args.data_type == 'baselines':
            return download_baselines()
        elif args.data_type == 'profiles':
            return download_profiles()
        elif args.data_type == 'config':
            return download_config()
        elif args.data_type == 'silver':
            if not args.client:
                parser.error("Client identifier is required for silver data type")
            return download_silver(args.client)
    
    elif args.command == 'upload':
        if args.data_type == 'baselines':
            return upload_baselines()
        elif args.data_type == 'profiles':
            return upload_profiles()
        elif args.data_type == 'config':
            return upload_config()
        elif args.data_type == 'silver':
            if not args.client:
                parser.error("Client identifier is required for silver data type")
            return upload_silver(args.client)
    
    elif args.command == 'backup-all':
        return backup_all()
    
    elif args.command == 'sync-client':
        return sync_client(args.client, args.direction)
    
    elif args.command == 'setup':
        return setup_new_environment()
    
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
