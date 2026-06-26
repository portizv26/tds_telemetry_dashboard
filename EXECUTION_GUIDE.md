# Telemetry Pipeline Execution Guide

## Overview
This guide provides instructions for running the telemetry analysis pipeline and uploading results to AWS S3 for weeks 23, 24, 25, and 26 of 2026.

## Prerequisites

### 1. Environment Setup
Ensure you have Python 3.12+ and all dependencies installed:

```powershell
# Install dependencies
pip install -r requirements.txt
```

### 2. AWS Credentials Configuration
Create a `.env` file in the project root with your AWS credentials:

```bash
# Copy the template
cp .env.example .env

# Edit .env and add your credentials
```

Required variables in `.env`:
```env
# OpenAI API Key (for AI Diagnosis)
OPENAI_API_KEY=your_openai_api_key_here

# AWS S3 Configuration
AWS_S3_BUCKET_NAME=your-s3-bucket-name
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_S3_PREFIX=telemetry/golden/
```

### 3. Input Data Verification
Ensure weekly data files exist in the Silver layer:
- `data/telemetry/silver/cda/Telemetry_Wide_With_States/Week23Year2026.parquet`
- `data/telemetry/silver/cda/Telemetry_Wide_With_States/Week24Year2026.parquet`
- `data/telemetry/silver/cda/Telemetry_Wide_With_States/Week25Year2026.parquet`
- `data/telemetry/silver/cda/Telemetry_Wide_With_States/Week26Year2026.parquet`

## Execution Steps

### Option 1: Run Pipeline with Integrated S3 Upload (Recommended)

The pipeline now includes integrated S3 upload functionality. Simply add the `--upload-to-s3` flag:

```powershell
# Run pipeline for specific weeks and upload to S3 automatically
python -m src.main --client cda --weeks Week23Year2026 Week24Year2026 Week25Year2026 Week26Year2026 --upload-to-s3
```

### Option 2: Run Pipeline Without S3 Upload

```powershell
# Run pipeline only (no upload)
python -m src.main --client cda --weeks Week23Year2026 Week24Year2026 Week25Year2026 Week26Year2026
```

### Option 3: Upload Separately (Manual Upload)

If you want to run the pipeline first and upload later:

```powershell
# Step 1: Run pipeline
python -m src.main --client cda --weeks Week23Year2026 Week24Year2026 Week25Year2026 Week26Year2026

# Step 2: Upload to S3 manually
python upload_to_s3.py --client cda --year 2026 --weeks 23 24 25 26
```

### Option 4: Fast Mode (Skip Expensive Operations)

If you want to skip computationally expensive operations:

```powershell
# Skip autoencoder and AI comments, with S3 upload
python -m src.main --client cda --weeks Week23Year2026 Week24Year2026 Week25Year2026 Week26Year2026 --skip-autoencoder --skip-ai-comments --upload-to-s3
```

## Pipeline Outputs

The pipeline generates the following outputs in the Golden layer:

### 1. Technique Results
Located in: `data/telemetry/golden/cda/technique_results/`

- **Deviation Analysis**: `deviation/year=2026/week={23,24,25,26}/deviation_results.parquet`
- **Event Analysis**: `events/year=2026/week={23,24,25,26}/events.parquet`
- **Trend Analysis**: `trend/year=2026/week={23,24,25,26}/trend_results.parquet`
- **Distribution Shift**: `distribution/year=2026/week={23,24,25,26}/distribution_results.parquet`

### 2. Health Assessments
- **System Health**: `system_health/year=2026/week={23,24,25,26}/system_health.parquet`
- **Unit Health**: `unit_health/year=2026/week={23,24,25,26}/unit_health.parquet`

### 3. AI Diagnosis Comments
Located in: `data/telemetry/golden/cda/ai_comments/year=2026/week={23,24,25,26}/`

- `signal_comments.parquet` - Signal-level AI diagnosis
- `system_comments.parquet` - System-level AI diagnosis
- `unit_comments.parquet` - Unit-level AI diagnosis

## S3 Upload Structure

Files will be uploaded to S3 with the following structure:

```
s3://your-bucket/MultiTechnique Alerts/telemetry/golden/cda/
├── technique_results/
│   ├── deviation/year=2026/week=23/deviation_results.parquet
│   ├── deviation/year=2026/week=24/deviation_results.parquet
│   ├── deviation/year=2026/week=25/deviation_results.parquet
│   ├── deviation/year=2026/week=26/deviation_results.parquet
│   ├── events/year=2026/week=23/events.parquet
│   ├── events/year=2026/week=24/events.parquet
│   ├── events/year=2026/week=25/events.parquet
│   ├── events/year=2026/week=26/events.parquet
│   ├── trend/year=2026/week=23/trend_results.parquet
│   ├── trend/year=2026/week=24/trend_results.parquet
│   ├── trend/year=2026/week=25/trend_results.parquet
│   ├── trend/year=2026/week=26/trend_results.parquet
│   ├── distribution/year=2026/week=23/distribution_results.parquet
│   ├── distribution/year=2026/week=24/distribution_results.parquet
│   ├── distribution/year=2026/week=25/distribution_results.parquet
│   └── distribution/year=2026/week=26/distribution_results.parquet
├── system_health/
│   ├── year=2026/week=23/system_health.parquet
│   ├── year=2026/week=24/system_health.parquet
│   ├── year=2026/week=25/system_health.parquet
│   └── year=2026/week=26/system_health.parquet
├── unit_health/
│   ├── year=2026/week=23/unit_health.parquet
│   ├── year=2026/week=24/unit_health.parquet
│   ├── year=2026/week=25/unit_health.parquet
│   └── year=2026/week=26/unit_health.parquet
└── ai_comments/
    ├── year=2026/week=23/signal_comments.parquet
    ├── year=2026/week=23/system_comments.parquet
    ├── year=2026/week=23/unit_comments.parquet
    ├── year=2026/week=24/signal_comments.parquet
    ├── year=2026/week=24/system_comments.parquet
    ├── year=2026/week=24/unit_comments.parquet
    ├── year=2026/week=25/signal_comments.parquet
    ├── year=2026/week=25/system_comments.parquet
    ├── year=2026/week=25/unit_comments.parquet
    ├── year=2026/week=26/signal_comments.parquet
    ├── year=2026/week=26/system_comments.parquet
    └── year=2026/week=26/unit_comments.parquet
```

## Command Reference

### Pipeline Execution

```powershell
# Basic usage
python -m src.main --client <client_name>

# Specific weeks
python -m src.main --client cda --weeks Week23Year2026 Week24Year2026

# With S3 upload
python -m src.main --client cda --upload-to-s3

# Skip expensive operations
python -m src.main --client cda --skip-autoencoder   # Skip LSTM training
python -m src.main --client cda --skip-llm           # Skip legacy LLM explanations
python -m src.main --client cda --skip-ai-comments   # Skip AI Diagnosis generation

# Combine options
python -m src.main --client cda --weeks Week23Year2026 --skip-autoencoder --upload-to-s3

# Adjust logging
python -m src.main --client cda --log-level DEBUG
```

### S3 Upload (Standalone)

The standalone upload tool is still available if you need to upload existing results:

```powershell
# Upload specific weeks
python upload_to_s3.py --client cda --year 2026 --weeks 23 24 25 26

# Upload all results
python upload_to_s3.py --client cda --all

# Custom golden path
python upload_to_s3.py --client cda --golden-path ./data/telemetry/golden --year 2026 --weeks 23
```

## Monitoring and Logs

All logs are automatically saved to the `logs/` folder in the project root for better organization.

### Pipeline Logs
Execution logs are saved to:
- Console output (real-time)
- `logs/telemetry_pipeline_YYYYMMDD.log` (daily log file)

### S3 Upload Logs
Upload logs are saved to:
- Console output (real-time)
- `logs/s3_upload_YYYYMMDD_HHMMSS.log` (per-execution log file)

### Pipeline Summary
After execution, a summary JSON is generated in the project root:
- `pipeline_summary_YYYYMMDD_HHMMSS.json`

Example summary:
```json
{
  "client": "cda",
  "elapsed_seconds": 3245.6,
  "input_rows": 1250000,
  "units_processed": 11,
  "baseline_version": "computed",
  "deviation_results": 4400,
  "events_detected": 856,
  "trend_results": 1320,
  "distribution_results": 880,
  "system_assessments": 176,
  "unit_assessments": 44,
  "ai_comments_signal": 650,
  "ai_comments_system": 120,
  "ai_comments_unit": 44,
  "units_anormal": 3,
  "units_alerta": 5
}
```

## Troubleshooting

### Issue: AWS Credentials Error
**Error**: `AWS credentials not available`

**Solution**:
1. Check `.env` file exists and contains valid credentials
2. Verify credentials with: `aws s3 ls s3://your-bucket/ --profile default`
3. Ensure `boto3` is installed: `pip install boto3`

### Issue: S3 Upload Permission Denied
**Error**: `S3 upload failed: Access Denied`

**Solution**:
Ensure your IAM user/role has the following S3 permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::your-bucket/telemetry/golden/*"
    }
  ]
}
```

### Issue: OpenAI API Rate Limit
**Error**: `Rate limit exceeded`

**Solution**:
1. Reduce batch size in AI Comments config
2. Increase `rate_limit_delay` in config
3. Use `--skip-ai-comments` flag to disable AI Diagnosis

### Issue: Memory Error
**Error**: `MemoryError` during pipeline execution

**Solution**:
1. Process weeks individually instead of all at once
2. Skip autoencoder: `--skip-autoencoder`
3. Increase system memory or use a machine with more RAM

### Issue: Missing Input Files
**Error**: `No files found matching pattern`

**Solution**:
1. Verify weekly files exist in Silver layer
2. Check file naming format: `WeekXXYearYYYY.parquet`
3. Ensure correct client path: `data/telemetry/silver/cda/Telemetry_Wide_With_States/`

## Performance Estimates

Based on historical data for CDA client (11 units, ~75 signals):

| Configuration | Execution Time | API Costs (approx) |
|---------------|----------------|-------------------|
| Full pipeline (4 weeks) | ~2-3 hours | $15-25 (OpenAI) |
| Skip autoencoder (4 weeks) | ~45-60 min | $15-25 (OpenAI) |
| Skip AI comments (4 weeks) | ~2-2.5 hours | $5-10 (OpenAI) |
| Skip both (4 weeks) | ~30-45 min | $5-10 (OpenAI) |

S3 Upload time: ~30-60 seconds (depends on file sizes and network speed)

## Support

For issues or questions:
1. Check logs in `logs/telemetry_pipeline_*.log` and `logs/s3_upload_*.log`
2. Review pipeline summary JSON for execution details
3. Verify configuration in `data/telemetry/config/cda/`

## Quick Reference: Full Workflow

### Integrated Workflow (Recommended)

```powershell
# 1. Configure AWS credentials
# Edit .env file with your credentials (see .env.example)

# 2. Run pipeline with integrated S3 upload
python -m src.main --client cda --weeks Week23Year2026 Week24Year2026 Week25Year2026 Week26Year2026 --upload-to-s3

# 3. Check logs and summary
# - pipeline logs: logs/telemetry_pipeline_YYYYMMDD.log
# - summary: pipeline_summary_YYYYMMDD_HHMMSS.json
```

### Two-Step Workflow (Alternative)

```powershell
# 1. Configure AWS credentials
# Edit .env file with your credentials

# 2. Run pipeline for weeks 23-26
python -m src.main --client cda --weeks Week23Year2026 Week24Year2026 Week25Year2026 Week26Year2026

# 3. Upload results to S3 separately
python upload_to_s3.py --client cda --year 2026 --weeks 23 24 25 26

# 4. Check logs and summary
# - pipeline logs: logs/telemetry_pipeline_YYYYMMDD.log
# - upload logs: logs/s3_upload_YYYYMMDD_HHMMSS.log
# - summary: pipeline_summary_YYYYMMDD_HHMMSS.json
```

## Notes

- The pipeline processes data sequentially to avoid memory issues
- All results are partitioned by year and week for efficient querying
- S3 uploads preserve the directory structure from Golden layer
- Progress is logged in real-time to console and log files
