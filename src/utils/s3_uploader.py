"""
S3 Uploader for Telemetry Dashboard Pipeline

Handles uploading Golden layer telemetry analysis results to AWS S3.
Supports uploading technique results, health assessments, and AI comments.
"""

import boto3
from pathlib import Path
from typing import Optional, Dict, List
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
import logging

logger = logging.getLogger(__name__)


class TelemetryS3Uploader:
    """Handles uploading telemetry analysis results to AWS S3."""
    
    def __init__(
        self, 
        bucket_name: str,
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
        s3_prefix: str = "MultiTechnique Alerts/telemetry/golden/"
    ):
        """
        Initialize S3 client with credentials.
        
        Args:
            bucket_name: Target S3 bucket name
            aws_access_key: AWS Access Key ID (if None, uses default credentials)
            aws_secret_key: AWS Secret Access Key (if None, uses default credentials)
            s3_prefix: Prefix path in S3 bucket (default: "MultiTechnique Alerts/telemetry/golden/")
        """
        self.bucket_name = bucket_name
        self.s3_prefix = s3_prefix.rstrip("/") + "/"  # Ensure trailing slash
        
        if not self._validate_credentials(aws_access_key, aws_secret_key):
            logger.warning("S3 credentials not configured - uploads will be skipped")
            self.s3_client = None
            return
        
        try:
            if aws_access_key and aws_secret_key:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key
                )
            else:
                # Use default credentials (from ~/.aws/credentials or IAM role)
                self.s3_client = boto3.client('s3')
            
            logger.info(f"S3 client initialized for bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.s3_client = None
    
    def _validate_credentials(self, access_key: Optional[str], secret_key: Optional[str]) -> bool:
        """Check if AWS credentials are configured or available."""
        # If both keys provided, they must be non-empty
        if access_key is not None and secret_key is not None:
            return bool(access_key and secret_key and self.bucket_name)
        # If neither provided, assume default credentials will work
        return bool(self.bucket_name)
    
    def upload_file(
        self, 
        file_path: str | Path, 
        s3_key: Optional[str] = None
    ) -> bool:
        """
        Upload a file to S3.
        
        Args:
            file_path: Path to local file
            s3_key: S3 object key (path in bucket). If None, uses relative path from golden layer
        
        Returns:
            True if upload successful, False otherwise
        """
        if self.s3_client is None:
            logger.warning(f"S3 client not available - skipping upload of {file_path}")
            return False
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return False
        
        # Generate S3 key if not provided
        if s3_key is None:
            s3_key = f"{self.s3_prefix}{file_path.name}"
        
        try:
            logger.info(f"Uploading {file_path} to s3://{self.bucket_name}/{s3_key}")
            
            self.s3_client.upload_file(
                str(file_path), 
                self.bucket_name, 
                s3_key
            )
            
            file_size_kb = file_path.stat().st_size / 1024
            logger.info(f"✓ Successfully uploaded {file_path.name} ({file_size_kb:.2f} KB)")
            return True
            
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            return False
        except NoCredentialsError:
            logger.error("AWS credentials not available")
            return False
        except PartialCredentialsError:
            logger.error("Incomplete AWS credentials provided")
            return False
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {e}")
            return False
    
    def upload_directory(
        self,
        directory_path: str | Path,
        preserve_structure: bool = True
    ) -> Dict[str, bool]:
        """
        Upload all files in a directory to S3.
        
        Args:
            directory_path: Path to directory containing files
            preserve_structure: If True, preserves subdirectory structure in S3
        
        Returns:
            Dictionary mapping file paths to upload success status
        """
        directory_path = Path(directory_path)
        results = {}
        
        if not directory_path.exists() or not directory_path.is_dir():
            logger.error(f"Directory not found: {directory_path}")
            return results
        
        # Find all parquet files recursively
        parquet_files = list(directory_path.rglob("*.parquet"))
        
        if not parquet_files:
            logger.warning(f"No parquet files found in {directory_path}")
            return results
        
        logger.info(f"Found {len(parquet_files)} files to upload from {directory_path}")
        
        for file_path in parquet_files:
            if preserve_structure:
                # Preserve directory structure relative to base directory
                relative_path = file_path.relative_to(directory_path)
                s3_key = f"{self.s3_prefix}{relative_path.as_posix()}"
            else:
                s3_key = f"{self.s3_prefix}{file_path.name}"
            
            success = self.upload_file(file_path, s3_key)
            results[str(file_path)] = success
        
        return results
    
    def upload_golden_layer(
        self,
        client: str,
        golden_path: str | Path,
        year: Optional[int] = None,
        weeks: Optional[List[int]] = None
    ) -> Dict[str, Dict[str, bool]]:
        """
        Upload Golden layer outputs for a specific client.
        
        Uploads:
        - technique_results/ (deviation, events, trend, distribution)
        - system_health/
        - unit_health/
        - ai_comments/
        
        Args:
            client: Client identifier (e.g., 'cda', 'emin')
            golden_path: Path to golden layer base directory
            year: If specified, only upload files for this year
            weeks: If specified, only upload files for these weeks
        
        Returns:
            Dictionary with upload results organized by category
        """
        golden_path = Path(golden_path) / client
        
        if not golden_path.exists():
            logger.error(f"Golden layer path not found: {golden_path}")
            return {}
        
        logger.info(f"Uploading Golden layer outputs for client: {client}")
        logger.info(f"Source: {golden_path}")
        
        results = {
            "technique_results": {},
            "system_health": {},
            "unit_health": {},
            "ai_comments": {}
        }
        
        # Define categories to upload
        categories = [
            "technique_results",
            "system_health",
            "unit_health",
            "ai_comments"
        ]
        
        for category in categories:
            category_path = golden_path / category
            
            if not category_path.exists():
                logger.warning(f"Category path not found: {category_path}")
                continue
            
            # Filter by year and weeks if specified
            files_to_upload = []
            
            if year is not None and weeks is not None:
                # Upload specific year/week combinations
                for week in weeks:
                    if category == "technique_results":
                        # technique_results has subcategories
                        for subcategory in ["deviation", "events", "trend", "distribution"]:
                            week_path = category_path / subcategory / f"year={year}" / f"week={week}"
                            if week_path.exists():
                                files_to_upload.extend(list(week_path.glob("*.parquet")))
                    else:
                        week_path = category_path / f"year={year}" / f"week={week}"
                        if week_path.exists():
                            files_to_upload.extend(list(week_path.glob("*.parquet")))
            else:
                # Upload all files
                files_to_upload = list(category_path.rglob("*.parquet"))
            
            # Upload files
            for file_path in files_to_upload:
                relative_path = file_path.relative_to(golden_path)
                s3_key = f"{self.s3_prefix}{client}/{relative_path.as_posix()}"
                success = self.upload_file(file_path, s3_key)
                results[category][str(relative_path)] = success
        
        # Summary
        total_files = sum(len(category_results) for category_results in results.values())
        successful = sum(
            sum(1 for success in category_results.values() if success)
            for category_results in results.values()
        )
        
        logger.info(f"Upload complete for {client}: {successful}/{total_files} files uploaded successfully")
        
        return results
    
    def upload_specific_weeks(
        self,
        client: str,
        golden_path: str | Path,
        year: int,
        weeks: List[int]
    ) -> Dict[str, int]:
        """
        Upload Golden layer outputs for specific weeks.
        
        Args:
            client: Client identifier
            golden_path: Path to golden layer base directory
            year: Year to upload
            weeks: List of week numbers to upload
        
        Returns:
            Summary dictionary with counts
        """
        logger.info(f"Uploading weeks {weeks} of year {year} for {client}")
        
        results = self.upload_golden_layer(
            client=client,
            golden_path=golden_path,
            year=year,
            weeks=weeks
        )
        
        # Build summary
        summary = {
            "client": client,
            "year": year,
            "weeks": weeks,
            "total_files": 0,
            "successful": 0,
            "failed": 0
        }
        
        for category_results in results.values():
            summary["total_files"] += len(category_results)
            summary["successful"] += sum(1 for success in category_results.values() if success)
            summary["failed"] += sum(1 for success in category_results.values() if not success)
        
        logger.info(f"Summary: {summary['successful']} successful, {summary['failed']} failed")
        
        return summary


def create_uploader_from_env() -> TelemetryS3Uploader:
    """
    Create S3 uploader using environment variables.
    
    Supported environment variable names (with fallbacks for backward compatibility):
    - AWS_S3_BUCKET_NAME or BUCKET_NAME: Target S3 bucket
    - AWS_ACCESS_KEY_ID or ACCESS_KEY: AWS access key (optional if using default credentials)
    - AWS_SECRET_ACCESS_KEY or SECRET_KEY: AWS secret key (optional if using default credentials)
    - AWS_S3_PREFIX: S3 prefix path (optional, default: "telemetry/golden/")
    
    Returns:
        TelemetryS3Uploader instance
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Support both naming conventions for backward compatibility
    bucket_name = os.getenv("AWS_S3_BUCKET_NAME") or os.getenv("BUCKET_NAME", "")
    access_key = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("ACCESS_KEY")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("SECRET_KEY")
    s3_prefix = os.getenv("AWS_S3_PREFIX", "MultiTechnique Alerts/telemetry/golden/")
    
    if not bucket_name:
        logger.error("AWS_S3_BUCKET_NAME (or BUCKET_NAME) not configured in environment")
        raise ValueError("AWS_S3_BUCKET_NAME or BUCKET_NAME environment variable is required")
    
    return TelemetryS3Uploader(
        bucket_name=bucket_name,
        aws_access_key=access_key,
        aws_secret_key=secret_key,
        s3_prefix=s3_prefix
    )
