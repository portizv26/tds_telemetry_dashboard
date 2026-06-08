# S3 Sync Guide

**Purpose**: Upload and download telemetry data, baselines, and analysis results to/from AWS S3.

---

## 📋 Prerequisites

### 1. AWS Credentials

Create a `.env` file in the project root with your AWS credentials:

```env
# AWS S3 Configuration
BUCKET_NAME=your-bucket-name
ACCESS_KEY=your-access-key-id
SECRET_KEY=your-secret-access-key

# Optional: Set if using IAM role (e.g., on EC2)
# STAGE_NAME=production
```

### 2. Dependencies

All required packages are already in `requirements.txt`:
- `boto3>=1.42.40` - AWS SDK
- `python-dotenv>=1.0.0` - Environment variables
- `tqdm>=4.65.0` - Progress bars

---

## 🔽 Downloading Data from S3

### Download Silver Layer Data

```bash
# Download Silver layer for specific client
python -m src.s3_downloader --data-type silver --client CDA

# Output: dataDep/telemetry/silver/CDA/
```

### Download Baselines

```bash
# Download all baseline files
python -m src.s3_downloader --data-type baselines

# Output: dataDep/telemetry/analytical_results/baselines/
```

### Download Profiles

```bash
# Download data quality profiles
python -m src.s3_downloader --data-type profiles

# Output: outputs/historical_analysis/
```

### Download Config Files

```bash
# Download configuration files
python -m src.s3_downloader --data-type config

# Output: dataDep/telemetry/config/
```

### Download from Custom S3 Path

```bash
# Download from any S3 prefix to any local path
python -m src.s3_downloader \
    --s3-prefix "custom/path/in/s3" \
    --local-path "./local/destination"
```

### Advanced Options

```bash
# Flatten directory structure (no nested folders)
python -m src.s3_downloader --data-type silver --client CDA --flatten

# Enable debug logging
python -m src.s3_downloader --data-type baselines --log-level DEBUG
```

---

## 🔼 Uploading Data to S3

### Upload Baselines

```bash
# Upload baseline files (only new/changed)
python -m src.s3_uploader --data-type baselines

# Source: dataDep/telemetry/analytical_results/baselines/
# Uploads: *.parquet, *.json
```

### Upload Profiles

```bash
# Upload data quality profiles
python -m src.s3_uploader --data-type profiles

# Source: outputs/historical_analysis/
# Uploads: *.html, *.json
```

### Upload Silver Layer Data

```bash
# Upload Silver layer for specific client
python -m src.s3_uploader --data-type silver --client CDA

# Source: dataDep/telemetry/silver/CDA/
# Uploads: *.parquet, *.csv
```

### Upload Config Files

```bash
# Upload configuration files
python -m src.s3_uploader --data-type config

# Source: dataDep/telemetry/config/
# Uploads: *.yaml, *.yml, *.json
```

### Upload from Custom Path

```bash
# Upload from any local path to any S3 prefix
python -m src.s3_uploader \
    --s3-prefix "custom/path/in/s3" \
    --local-path "./local/source"
```

### Advanced Options

```bash
# Force re-upload all files (ignore existing)
python -m src.s3_uploader --data-type baselines --force

# Upload specific file patterns
python -m src.s3_uploader \
    --data-type baselines \
    --file-patterns "*.parquet" "baseline_202605*.parquet"

# Enable debug logging
python -m src.s3_uploader --data-type profiles --log-level DEBUG
```

---

## 🔄 Common Workflows

### Workflow 1: Backup Analysis Results

After running historical analysis, upload results to S3:

```bash
# Upload baselines
python -m src.s3_uploader --data-type baselines

# Upload profiles
python -m src.s3_uploader --data-type profiles
```

### Workflow 2: Sync to New Environment

Set up a new environment with data from S3:

```bash
# Download config files first
python -m src.s3_downloader --data-type config

# Download Silver layer data
python -m src.s3_downloader --data-type silver --client CDA

# Download existing baselines
python -m src.s3_downloader --data-type baselines
```

### Workflow 3: Incremental Backup

Upload only new files (default behavior):

```bash
# Only uploads files that don't exist in S3
python -m src.s3_uploader --data-type baselines
python -m src.s3_uploader --data-type profiles
```

### Workflow 4: Full Re-upload

Force upload all files:

```bash
# Re-upload everything
python -m src.s3_uploader --data-type baselines --force
```

---

## 📂 Default S3 Structure

The scripts use the following S3 structure by default:

```
s3://your-bucket/
├── telemetry/
│   ├── silver/
│   │   ├── CDA/
│   │   │   └── Telemetry_Wide_With_States/
│   │   │       ├── Week01Year2025.parquet
│   │   │       └── Week02Year2025.parquet
│   │   ├── EMIN/
│   │   └── ENEX/
│   ├── golden/
│   │   └── CDA/
│   ├── config/
│   │   ├── signal_registry_v1.yaml
│   │   └── technique_config.yaml
│   ├── profiles/
│   │   ├── profile_CDA_week1_2025.html
│   │   └── profile_CDA_week1_2025.json
│   └── analytical_results/
│       └── baselines/
│           ├── baseline_20260528.parquet
│           └── baseline_metadata.json
```

---

## 🎯 Usage Examples

### Example 1: First-Time Setup

```bash
# On a new machine, download everything you need
python -m src.s3_downloader --data-type config
python -m src.s3_downloader --data-type silver --client CDA
python -m src.s3_downloader --data-type baselines
```

### Example 2: Daily Backup Routine

```bash
# After running analysis, backup results
python -m src.s3_uploader --data-type baselines
python -m src.s3_uploader --data-type profiles
```

### Example 3: Share Results with Team

```bash
# Upload your latest analysis
python -m src.s3_uploader --data-type profiles

# Team member downloads
python -m src.s3_downloader --data-type profiles
```

### Example 4: Multi-Client Processing

```bash
# Upload Silver data for multiple clients
python -m src.s3_uploader --data-type silver --client CDA
python -m src.s3_uploader --data-type silver --client EMIN
python -m src.s3_uploader --data-type silver --client ENEX
```

---

## 🔍 Troubleshooting

### Error: "BUCKET_NAME not found in .env file"

**Solution**: Create a `.env` file in the project root with your AWS credentials.

```env
BUCKET_NAME=your-bucket-name
ACCESS_KEY=your-access-key-id
SECRET_KEY=your-secret-access-key
```

### Error: "AWS credentials not found"

**Solutions**:

1. **Use .env file** (recommended):
   ```env
   ACCESS_KEY=your-access-key-id
   SECRET_KEY=your-secret-access-key
   ```

2. **Use AWS CLI credentials**:
   ```bash
   aws configure
   ```

3. **Use environment variables**:
   ```bash
   export AWS_ACCESS_KEY_ID=your-key
   export AWS_SECRET_ACCESS_KEY=your-secret
   ```

4. **Use IAM role** (on EC2):
   ```env
   STAGE_NAME=production
   ```

### Error: "--client is required"

**Solution**: Provide the client identifier for silver/golden data types.

```bash
python -m src.s3_downloader --data-type silver --client CDA
```

### Files Not Uploading

**Check**:

1. **Skipped due to existing files**:
   ```bash
   # Use --force to re-upload
   python -m src.s3_uploader --data-type baselines --force
   ```

2. **Wrong file patterns**:
   ```bash
   # Specify correct patterns
   python -m src.s3_uploader --data-type baselines --file-patterns "*.parquet"
   ```

3. **Directory doesn't exist**:
   ```bash
   # Verify local path exists
   ls dataDep/telemetry/analytical_results/baselines/
   ```

### Slow Uploads/Downloads

**Tips**:

1. Upload only specific file types:
   ```bash
   python -m src.s3_uploader --data-type baselines --file-patterns "*.parquet"
   ```

2. Use debug logging to see progress:
   ```bash
   python -m src.s3_uploader --data-type baselines --log-level DEBUG
   ```

---

## 📊 Output Interpretation

### Download Output

```
================================================================================
S3 Data Download Script
================================================================================
S3 Bucket: my-telemetry-bucket
S3 Prefix: telemetry/analytical_results/baselines/
Local Path: dataDep/telemetry/analytical_results/baselines
Preserve Structure: True
================================================================================

Found 15 objects with prefix 'telemetry/analytical_results/baselines/'
Downloading files: 100%|████████████████| 15/15 [00:05<00:00,  2.75file/s]

================================================================================
Total files: 15
Successfully downloaded: 15
Failed: 0
================================================================================
✓ Downloaded 15 files to dataDep/telemetry/analytical_results/baselines
```

### Upload Output

```
================================================================================
S3 Data Upload Script
================================================================================
S3 Bucket: my-telemetry-bucket
S3 Prefix: telemetry/analytical_results/baselines/
Local Path: dataDep/telemetry/analytical_results/baselines
File Patterns: ['*.parquet', '*.json']
Skip Existing: True
================================================================================

Found 20 files to process
Uploading files: 100%|████████████████| 20/20 [00:08<00:00,  2.35file/s]

================================================================================
Total files: 20
Uploaded: 5
Skipped (already exist): 15
Failed: 0
================================================================================
✓ Uploaded 5 files to s3://my-telemetry-bucket/telemetry/analytical_results/baselines/
```

---

## 🔐 Security Best Practices

1. **Never commit .env file**:
   ```bash
   # .gitignore should contain:
   .env
   ```

2. **Use IAM roles when possible**:
   - Preferred on EC2/ECS/Lambda
   - Set `STAGE_NAME=production` in .env
   - Remove ACCESS_KEY and SECRET_KEY

3. **Use least privilege access**:
   - Grant only necessary S3 permissions
   - Use bucket policies to restrict access

4. **Rotate credentials regularly**:
   - Update ACCESS_KEY and SECRET_KEY periodically
   - Use AWS Secrets Manager for production

---

## 🚀 Integration with Pipeline

### After Historical Analysis

```bash
# Run historical analysis
python run_historical_analysis.py --client CDA

# Upload results to S3
python -m src.s3_uploader --data-type baselines
python -m src.s3_uploader --data-type profiles
```

### Before Phase 2 Techniques

```bash
# Download latest baselines
python -m src.s3_downloader --data-type baselines

# Download Silver data if needed
python -m src.s3_downloader --data-type silver --client CDA
```

### Automated Workflow

Create a script `sync_to_s3.sh`:

```bash
#!/bin/bash
set -e

echo "Running historical analysis..."
python run_historical_analysis.py --client CDA

echo "Uploading baselines..."
python -m src.s3_uploader --data-type baselines

echo "Uploading profiles..."
python -m src.s3_uploader --data-type profiles

echo "✓ Analysis complete and synced to S3!"
```

---

## 📖 API Usage (Python)

You can also use the S3 classes programmatically:

```python
from pathlib import Path
from src.s3_uploader import S3Uploader
from src.s3_downloader import S3Downloader

# Upload baselines programmatically
uploader = S3Uploader(
    bucket_name="my-bucket",
    aws_access_key_id="your-key",
    aws_secret_access_key="your-secret"
)

stats = uploader.upload_folder(
    local_dir=Path("dataDep/telemetry/analytical_results/baselines"),
    s3_prefix="telemetry/analytical_results/baselines/",
    skip_if_exists=True,
    file_patterns=["*.parquet"]
)

print(f"Uploaded {stats['uploaded']} files")

# Download data programmatically
downloader = S3Downloader(
    bucket_name="my-bucket",
    aws_access_key_id="your-key",
    aws_secret_access_key="your-secret"
)

stats = downloader.download_folder(
    s3_prefix="telemetry/silver/CDA/",
    local_dir=Path("dataDep/telemetry/silver/CDA"),
    preserve_structure=True
)

print(f"Downloaded {stats['success']} files")
```

---

## 🎯 Quick Reference

```bash
# DOWNLOAD
python -m src.s3_downloader --data-type baselines
python -m src.s3_downloader --data-type profiles
python -m src.s3_downloader --data-type silver --client CDA
python -m src.s3_downloader --data-type config

# UPLOAD
python -m src.s3_uploader --data-type baselines
python -m src.s3_uploader --data-type profiles
python -m src.s3_uploader --data-type silver --client CDA
python -m src.s3_uploader --data-type config

# CUSTOM
python -m src.s3_downloader --s3-prefix "path" --local-path "./dir"
python -m src.s3_uploader --s3-prefix "path" --local-path "./dir" --force
```

---

**Ready to sync your telemetry data with S3!** 🚀
