"""
S3 Data Downloader Script

This script downloads data from S3 to local storage.
Supports downloading Silver layer telemetry, baselines, and profiles.

Usage:
    # Download Silver layer data for a client
    python -m src.s3_downloader --data-type silver --client CDA
    
    # Download baselines
    python -m src.s3_downloader --data-type baselines
    
    # Download from custom S3 prefix
    python -m src.s3_downloader --s3-prefix "path/to/data" --local-path "local/dir"
"""

import os
import argparse
import boto3
from pathlib import Path
from typing import Optional, Dict
from tqdm import tqdm
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

from src.utils.logger import setup_logger, get_logger

logger = get_logger(__name__)


class S3Downloader:
    """Downloads data from S3 to local storage."""
    
    def __init__(
        self, 
        bucket_name: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1"
    ):
        """
        Initialize S3 downloader.
        
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
    
    def list_objects(self, prefix: str) -> list:
        """
        List all objects in S3 bucket with given prefix.
        
        Args:
            prefix: S3 prefix (folder path)
            
        Returns:
            List of object keys
        """
        try:
            objects = []
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # Skip folders (objects ending with /)
                        if not obj['Key'].endswith('/'):
                            objects.append(obj['Key'])
            
            logger.info(f"Found {len(objects)} objects with prefix '{prefix}'")
            return objects
            
        except NoCredentialsError:
            logger.error("AWS credentials not found. Please configure your credentials.")
            raise
        except ClientError as e:
            logger.error(f"Error listing objects: {e}")
            raise
    
    def download_file(self, s3_key: str, local_path: Path) -> bool:
        """
        Download a single file from S3.
        
        Args:
            s3_key: S3 object key
            local_path: Local file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert to absolute path and handle Windows long paths
            local_path = local_path.resolve()
            
            # Create parent directories if they don't exist
            try:
                local_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.error(f"Failed to create directory {local_path.parent}: {e}")
                return False
            
            # Verify the directory exists
            if not local_path.parent.exists():
                logger.error(f"Directory does not exist after creation: {local_path.parent}")
                return False
            
            # Convert to string, use extended path for Windows if path is long
            local_path_str = str(local_path)
            if os.name == 'nt' and len(local_path_str) > 200:
                # Use Windows extended-length path syntax for long paths
                if not local_path_str.startswith('\\\\?\\'):
                    local_path_str = '\\\\?\\' + local_path_str
            
            # Download the file
            self.s3_client.download_file(
                self.bucket_name, 
                s3_key, 
                local_path_str
            )
            
            logger.debug(f"Downloaded: {s3_key} -> {local_path}")
            return True
            
        except ClientError as e:
            logger.error(f"Error downloading {s3_key}: {e}")
            return False
        except OSError as e:
            logger.error(f"OS error downloading {s3_key} to {local_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error downloading {s3_key}: {e}")
            return False
    
    def download_folder(
        self, 
        s3_prefix: str, 
        local_dir: Path,
        preserve_structure: bool = True
    ) -> dict:
        """
        Download all files from an S3 folder to local directory.
        
        Args:
            s3_prefix: S3 prefix (folder path)
            local_dir: Local directory path
            preserve_structure: If True, preserves the folder structure from S3
            
        Returns:
            Dictionary with download statistics
        """
        logger.info(f"Starting download from s3://{self.bucket_name}/{s3_prefix}")
        logger.info(f"Destination: {local_dir}")
        
        # Get list of objects
        objects = self.list_objects(s3_prefix)
        
        if not objects:
            logger.warning(f"No objects found with prefix '{s3_prefix}'")
            return {"total": 0, "success": 0, "failed": 0}
        
        # Download each object
        success_count = 0
        failed_count = 0
        
        for s3_key in tqdm(objects, desc="Downloading files"):
            if preserve_structure:
                # Remove the S3 prefix but keep the nested folder structure
                relative_path = s3_key.replace(s3_prefix, '', 1).lstrip('/')
            else:
                # Flatten the structure (extract just the filename)
                relative_path = os.path.basename(s3_key)
            
            local_path = local_dir / relative_path
            
            if self.download_file(s3_key, local_path):
                success_count += 1
            else:
                failed_count += 1
        
        stats = {
            "total": len(objects),
            "success": success_count,
            "failed": failed_count
        }
        
        logger.info(f"Download complete: {success_count}/{len(objects)} files successful")
        if failed_count > 0:
            logger.warning(f"{failed_count} files failed to download")
        
        return stats


def get_default_paths(data_type: str, client: Optional[str] = None) -> Dict[str, str]:
    """Get default S3 prefix and local path for data type."""
    project_root = Path(__file__).parent.parent
    
    paths = {
        'silver': {
            's3_prefix': f'telemetry/silver/{client}/' if client else 'telemetry/silver/',
            'local_path': project_root / f'data/telemetry/silver/{client}' if client else project_root / 'data/telemetry/silver'
        },
        'golden': {
            's3_prefix': f'telemetry/golden/{client}/' if client else 'telemetry/golden/',
            'local_path': project_root / f'data/telemetry/golden/{client}' if client else project_root / 'data/telemetry/golden'
        },
        'baselines': {
            's3_prefix': 'telemetry/analytical_results/baselines/',
            'local_path': project_root / 'data/telemetry/analytical_results/baselines'
        },
        'profiles': {
            's3_prefix': 'telemetry/profiles/',
            'local_path': project_root / 'outputs/historical_analysis'
        },
        'config': {
            's3_prefix': 'telemetry/config/',
            'local_path': project_root / 'data/telemetry/config'
        }
    }
    
    return paths.get(data_type, {'s3_prefix': '', 'local_path': project_root / 'data'})


def main():
    """Main function to download data from S3."""
    
    parser = argparse.ArgumentParser(
        description='Download telemetry data from S3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download Silver layer for CDA client
  python -m src.s3_downloader --data-type silver --client CDA
  
  # Download all baselines
  python -m src.s3_downloader --data-type baselines
  
  # Download from custom S3 path
  python -m src.s3_downloader --s3-prefix "custom/path" --local-path "./data"
        """
    )
    
    parser.add_argument(
        '--data-type',
        choices=['silver', 'golden', 'baselines', 'profiles', 'config'],
        help='Type of data to download (uses default paths)'
    )
    parser.add_argument(
        '--client',
        help='Client identifier (for silver/golden data types)'
    )
    parser.add_argument(
        '--s3-prefix',
        help='Custom S3 prefix to download from'
    )
    parser.add_argument(
        '--local-path',
        type=Path,
        help='Custom local path to download to'
    )
    parser.add_argument(
        '--preserve-structure',
        action='store_true',
        default=True,
        help='Preserve folder structure from S3 (default: True)'
    )
    parser.add_argument(
        '--flatten',
        action='store_true',
        help='Flatten directory structure (download all files to same folder)'
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
    
    # Determine paths
    if args.s3_prefix and args.local_path:
        s3_prefix = args.s3_prefix
        local_path = args.local_path
    elif args.data_type:
        if args.data_type in ['silver', 'golden'] and not args.client:
            parser.error(f"--client is required for --data-type {args.data_type}")
        
        paths = get_default_paths(args.data_type, args.client)
        s3_prefix = paths['s3_prefix']
        local_path = paths['local_path']
    else:
        parser.error("Either --data-type or both --s3-prefix and --local-path are required")
    
    preserve_structure = args.preserve_structure and not args.flatten
    
    logger.info("=" * 60)
    logger.info("S3 Data Download Script")
    logger.info("=" * 60)
    logger.info(f"S3 Bucket: {BUCKET_NAME}")
    logger.info(f"S3 Prefix: {s3_prefix}")
    logger.info(f"Local Path: {local_path}")
    logger.info(f"Preserve Structure: {preserve_structure}")
    logger.info("=" * 60)
    
    try:
        # Initialize downloader with credentials from .env file
        downloader = S3Downloader(
            bucket_name=BUCKET_NAME,
            aws_access_key_id=ACCESS_KEY if not STAGE_NAME else None,
            aws_secret_access_key=SECRET_KEY if not STAGE_NAME else None
        )
        
        # Download the folder
        stats = downloader.download_folder(
            s3_prefix=s3_prefix,
            local_dir=local_path,
            preserve_structure=preserve_structure
        )
        
        logger.info("=" * 60)
        logger.info(f"Total files: {stats['total']}")
        logger.info(f"Successfully downloaded: {stats['success']}")
        logger.info(f"Failed: {stats['failed']}")
        logger.info("=" * 60)
        
        if stats['success'] > 0:
            logger.info(f"✓ Downloaded {stats['success']} files to {local_path}")
        
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
