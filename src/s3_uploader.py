"""
S3 Data Uploader Script

This script uploads data to S3, checking if files already exist
before uploading to avoid unnecessary transfers.

Supports uploading:
- Baselines (analytical results)
- Data quality profiles
- Silver layer telemetry
- Config files

Usage:
    # Upload baselines
    python -m src.s3_uploader --data-type baselines
    
    # Upload profiles
    python -m src.s3_uploader --data-type profiles
    
    # Upload Silver layer for specific client
    python -m src.s3_uploader --data-type silver --client CDA
    
    # Upload from custom path
    python -m src.s3_uploader --s3-prefix "path/to/upload" --local-path "local/dir"
"""

import os
import argparse
import boto3
from pathlib import Path
from typing import Optional, List, Dict
from tqdm import tqdm
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

from src.utils.logger import setup_logger, get_logger

logger = get_logger(__name__)


class S3Uploader:
    """Uploads data from local storage to S3."""
    
    def __init__(
        self, 
        bucket_name: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1"
    ):
        """
        Initialize S3 uploader.
        
        Args:
            bucket_name: Name of the S3 bucket
            aws_access_key_id: AWS access key (if None, will use default credentials)
            aws_secret_access_key: AWS secret key (if None, will use default credentials)
            region_name: AWS region name
        """
        self.bucket_name = bucket_name
        
        # Initialize S3 client
        if aws_access_key_id and aws_secret_access_key:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=region_name
            )
        else:
            # Use default credentials from environment or ~/.aws/credentials
            self.s3_client = boto3.client('s3', region_name=region_name)
    
    def file_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in S3.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            logger.debug(f"File exists in S3: {s3_key}")
            return True
        except ClientError as e:
            # If error code is 404, file doesn't exist
            if e.response['Error']['Code'] == '404':
                logger.debug(f"File does not exist in S3: {s3_key}")
                return False
            else:
                # Other error occurred
                logger.error(f"Error checking file existence: {e}")
                raise
    
    def upload_file(
        self, 
        local_path: Path, 
        s3_key: str,
        skip_if_exists: bool = True,
        extra_args: Optional[dict] = None
    ) -> bool:
        """
        Upload a single file to S3.
        
        Args:
            local_path: Local file path
            s3_key: S3 object key (destination path)
            skip_if_exists: If True, skip upload if file already exists
            extra_args: Additional arguments for upload (e.g., ContentType, Metadata)
            
        Returns:
            True if uploaded, False if skipped or failed
        """
        try:
            # Check if file exists locally
            if not local_path.exists():
                logger.error(f"Local file not found: {local_path}")
                return False
            
            # Check if file already exists in S3
            if skip_if_exists and self.file_exists(s3_key):
                logger.debug(f"Skipping upload (already exists): {s3_key}")
                return False
            
            # Upload the file
            self.s3_client.upload_file(
                str(local_path),
                self.bucket_name,
                s3_key,
                ExtraArgs=extra_args
            )
            
            logger.debug(f"Uploaded: {local_path} -> s3://{self.bucket_name}/{s3_key}")
            return True
            
        except NoCredentialsError:
            logger.error("AWS credentials not found. Please configure your credentials.")
            raise
        except ClientError as e:
            logger.error(f"Error uploading {local_path}: {e}")
            return False
    
    def upload_folder(
        self,
        local_dir: Path,
        s3_prefix: str,
        skip_if_exists: bool = True,
        file_patterns: Optional[List[str]] = None
    ) -> dict:
        """
        Upload all files from a local directory to an S3 folder.
        
        Args:
            local_dir: Local directory path
            s3_prefix: S3 prefix (folder path) where files will be uploaded
            skip_if_exists: If True, skip files that already exist in S3
            file_patterns: List of glob patterns to match files (e.g., ['*.csv', '*.json'])
                          If None, uploads all files
            
        Returns:
            Dictionary with upload statistics
        """
        logger.info(f"Starting upload to s3://{self.bucket_name}/{s3_prefix}")
        logger.info(f"Source: {local_dir}")
        
        # Check if local directory exists
        if not local_dir.exists():
            logger.error(f"Local directory not found: {local_dir}")
            return {"total": 0, "uploaded": 0, "skipped": 0, "failed": 0}
        
        # Get list of files to upload
        files_to_upload = []
        
        if file_patterns:
            for pattern in file_patterns:
                files_to_upload.extend(local_dir.rglob(pattern))
        else:
            files_to_upload = [f for f in local_dir.rglob('*') if f.is_file()]
        
        if not files_to_upload:
            logger.warning(f"No files found in {local_dir}")
            return {"total": 0, "uploaded": 0, "skipped": 0, "failed": 0}
        
        logger.info(f"Found {len(files_to_upload)} files to process")
        
        # Upload each file
        uploaded_count = 0
        skipped_count = 0
        failed_count = 0
        
        for local_path in tqdm(files_to_upload, desc="Uploading files"):
            # Create S3 key preserving folder structure
            relative_path = local_path.relative_to(local_dir)
            s3_key = f"{s3_prefix.rstrip('/')}/{relative_path.as_posix()}"
            
            result = self.upload_file(
                local_path,
                s3_key,
                skip_if_exists=skip_if_exists
            )
            
            if result:
                uploaded_count += 1
            elif skip_if_exists and self.file_exists(s3_key):
                skipped_count += 1
            else:
                failed_count += 1
        
        stats = {
            "total": len(files_to_upload),
            "uploaded": uploaded_count,
            "skipped": skipped_count,
            "failed": failed_count
        }
        
        logger.info(f"Upload complete: {uploaded_count} uploaded, {skipped_count} skipped, {failed_count} failed")
        
        return stats
    
    def sync_folder(
        self,
        local_dir: Path,
        s3_prefix: str,
        file_patterns: Optional[List[str]] = None
    ) -> dict:
        """
        Sync local folder to S3 (upload only new/changed files).
        
        Args:
            local_dir: Local directory path
            s3_prefix: S3 prefix (folder path)
            file_patterns: List of glob patterns to match files
            
        Returns:
            Dictionary with sync statistics
        """
        logger.info(f"Syncing {local_dir} to s3://{self.bucket_name}/{s3_prefix}")
        return self.upload_folder(
            local_dir=local_dir,
            s3_prefix=s3_prefix,
            skip_if_exists=True,
            file_patterns=file_patterns
        )


def get_default_paths(data_type: str, client: Optional[str] = None) -> Dict[str, any]:
    """Get default S3 prefix, local path, and file patterns for data type."""
    project_root = Path(__file__).parent.parent
    
    paths = {
        'silver': {
            's3_prefix': f'telemetry/silver/{client}/' if client else 'telemetry/silver/',
            'local_path': project_root / f'data/telemetry/silver/{client}' if client else project_root / 'data/telemetry/silver',
            'file_patterns': ['*.parquet', '*.csv']
        },
        'golden': {
            's3_prefix': f'telemetry/golden/{client}/' if client else 'telemetry/golden/',
            'local_path': project_root / f'data/telemetry/golden/{client}' if client else project_root / 'data/telemetry/golden',
            'file_patterns': ['*.parquet', '*.csv']
        },
        'baselines': {
            's3_prefix': 'telemetry/analytical_results/baselines/',
            'local_path': project_root / 'data/telemetry/analytical_results/baselines',
            'file_patterns': ['*.parquet', '*.json']
        },
        'profiles': {
            's3_prefix': 'telemetry/profiles/',
            'local_path': project_root / 'outputs/historical_analysis',
            'file_patterns': ['*.html', '*.json']
        },
        'config': {
            's3_prefix': 'telemetry/config/',
            'local_path': project_root / 'data/telemetry/config',
            'file_patterns': ['*.yaml', '*.yml', '*.json']
        }
    }
    
    return paths.get(data_type, {
        's3_prefix': '',
        'local_path': project_root / 'data',
        'file_patterns': None
    })


def main():
    """Main function to upload data to S3."""
    
    parser = argparse.ArgumentParser(
        description='Upload telemetry data to S3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload baselines
  python -m src.s3_uploader --data-type baselines
  
  # Upload profiles
  python -m src.s3_uploader --data-type profiles
  
  # Upload Silver layer for CDA client
  python -m src.s3_uploader --data-type silver --client CDA
  
  # Upload from custom path
  python -m src.s3_uploader --s3-prefix "custom/path" --local-path "./data"
  
  # Force re-upload all files (skip existence check)
  python -m src.s3_uploader --data-type baselines --force
        """
    )
    
    parser.add_argument(
        '--data-type',
        choices=['silver', 'golden', 'baselines', 'profiles', 'config'],
        help='Type of data to upload (uses default paths)'
    )
    parser.add_argument(
        '--client',
        help='Client identifier (for silver/golden data types)'
    )
    parser.add_argument(
        '--s3-prefix',
        help='Custom S3 prefix to upload to'
    )
    parser.add_argument(
        '--local-path',
        type=Path,
        help='Custom local path to upload from'
    )
    parser.add_argument(
        '--file-patterns',
        nargs='+',
        help='File patterns to match (e.g., *.parquet *.json)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force upload even if files exist in S3'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )
    
    args = parser.parse_args()
    
    # Setup logger
    import logging
    setup_logger(__name__, level=getattr(logging, args.log_level))
    
    # Load environment variables from .env file
    project_root = Path(__file__).parent.parent
    load_dotenv(project_root / ".env")
    
    # Configuration from .env file
    BUCKET_NAME = os.getenv("BUCKET_NAME")
    ACCESS_KEY = os.getenv("ACCESS_KEY")
    SECRET_KEY = os.getenv("SECRET_KEY")
    STAGE_NAME = os.getenv("STAGE_NAME")  # Only defined when deployed to the cloud
    
    if not BUCKET_NAME:
        raise ValueError("BUCKET_NAME not found in .env file")
    if not STAGE_NAME and (not ACCESS_KEY or not SECRET_KEY):
        raise ValueError("ACCESS_KEY and SECRET_KEY not found in .env file. Set STAGE_NAME if using IAM role.")
    
    # Determine paths and patterns
    if args.s3_prefix and args.local_path:
        s3_prefix = args.s3_prefix
        local_path = args.local_path
        file_patterns = args.file_patterns
    elif args.data_type:
        if args.data_type in ['silver', 'golden'] and not args.client:
            parser.error(f"--client is required for --data-type {args.data_type}")
        
        paths = get_default_paths(args.data_type, args.client)
        s3_prefix = paths['s3_prefix']
        local_path = paths['local_path']
        file_patterns = args.file_patterns or paths.get('file_patterns')
    else:
        parser.error("Either --data-type or both --s3-prefix and --local-path are required")
    
    skip_if_exists = not args.force
    
    logger.info("=" * 60)
    logger.info("S3 Data Upload Script")
    logger.info("=" * 60)
    logger.info(f"S3 Bucket: {BUCKET_NAME}")
    logger.info(f"S3 Prefix: {s3_prefix}")
    logger.info(f"Local Path: {local_path}")
    logger.info(f"File Patterns: {file_patterns or 'All files'}")
    logger.info(f"Skip Existing: {skip_if_exists}")
    logger.info("=" * 60)
    
    try:
        # Initialize uploader with credentials from .env file
        uploader = S3Uploader(
            bucket_name=BUCKET_NAME,
            aws_access_key_id=ACCESS_KEY if not STAGE_NAME else None,
            aws_secret_access_key=SECRET_KEY if not STAGE_NAME else None
        )
        
        # Upload the folder
        stats = uploader.upload_folder(
            local_dir=local_path,
            s3_prefix=s3_prefix,
            skip_if_exists=skip_if_exists,
            file_patterns=file_patterns
        )
        
        logger.info("=" * 60)
        logger.info(f"Total files: {stats['total']}")
        logger.info(f"Uploaded: {stats['uploaded']}")
        logger.info(f"Skipped (already exist): {stats['skipped']}")
        logger.info(f"Failed: {stats['failed']}")
        logger.info("=" * 60)
        
        if stats['uploaded'] > 0:
            logger.info(f"✓ Uploaded {stats['uploaded']} files to s3://{BUCKET_NAME}/{s3_prefix}")
        
    except NoCredentialsError:
        logger.error(
            "AWS credentials not found. Please configure your credentials using one of:\n"
            "1. Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY\n"
            "2. AWS credentials file: ~/.aws/credentials\n"
            "3. IAM role (if running on EC2)\n"
            "4. Set ACCESS_KEY and SECRET_KEY in .env file"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
