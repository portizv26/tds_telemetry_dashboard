# S3 Sync - Quick Start

## ✅ Updated & Ready to Use!

Your S3 uploader and downloader have been **updated and integrated** with the Phase 1 framework.

---

## 🎯 What Changed

### Before (Legacy)
- Hardcoded to "MultiTechnique Alerts/" folder
- Used generic "data/" directory
- No CLI arguments
- Manual path editing required

### After (Updated)
- ✅ Flexible S3 paths (baselines, profiles, silver, golden, config)
- ✅ CLI arguments for easy use
- ✅ Integrated with Phase 1 directory structure
- ✅ Support for multiple clients
- ✅ Convenience wrapper script (`sync_s3.py`)

---

## 🚀 Quick Usage

### Setup
Create a `.env` file in project root:
```env
BUCKET_NAME=your-bucket-name
ACCESS_KEY=your-aws-access-key
SECRET_KEY=your-aws-secret-key
```

### Common Commands

```bash
# UPLOAD (After running analysis)
python sync_s3.py backup-all          # Upload baselines + profiles

# DOWNLOAD (Setup new environment)
python sync_s3.py setup               # Download config + baselines + profiles
python sync_s3.py download silver CDA # Download Silver data

# SPECIFIC OPERATIONS
python sync_s3.py upload baselines
python sync_s3.py download profiles
python sync_s3.py sync-client CDA     # Upload & download for client
```

### Direct Module Usage

```bash
# Download baselines
python -m src.s3_downloader --data-type baselines

# Upload profiles
python -m src.s3_uploader --data-type profiles

# Download Silver data for CDA
python -m src.s3_downloader --data-type silver --client CDA
```

---

## 📂 Default Paths

| Data Type | S3 Prefix | Local Path |
|-----------|-----------|------------|
| **baselines** | `telemetry/analytical_results/baselines/` | `dataDep/telemetry/analytical_results/baselines/` |
| **profiles** | `telemetry/profiles/` | `outputs/historical_analysis/` |
| **silver** | `telemetry/silver/{client}/` | `dataDep/telemetry/silver/{client}/` |
| **golden** | `telemetry/golden/{client}/` | `dataDep/telemetry/golden/{client}/` |
| **config** | `telemetry/config/` | `dataDep/telemetry/config/` |

---

## 💡 Common Workflows

### Workflow 1: After Historical Analysis
```bash
# Run analysis
python run_historical_analysis.py --client CDA

# Backup to S3
python sync_s3.py backup-all
```

### Workflow 2: New Team Member Setup
```bash
# Setup environment
python sync_s3.py setup

# Download client data
python sync_s3.py download silver CDA

# Ready to work!
```

### Workflow 3: Share Latest Baselines
```bash
# Upload your baselines
python sync_s3.py upload baselines

# Team downloads
python sync_s3.py download baselines
```

---

## 🔧 Advanced Usage

### Custom S3 Paths
```bash
# Download from custom path
python -m src.s3_downloader \
    --s3-prefix "custom/path" \
    --local-path "./my/dir"

# Upload to custom path
python -m src.s3_uploader \
    --s3-prefix "custom/path" \
    --local-path "./my/dir"
```

### Force Re-upload
```bash
# Re-upload all files (ignore existing)
python -m src.s3_uploader --data-type baselines --force
```

### Debug Logging
```bash
python -m src.s3_downloader --data-type baselines --log-level DEBUG
```

---

## 📖 Full Documentation

- **[S3_SYNC_GUIDE.md](S3_SYNC_GUIDE.md)** - Complete usage guide with examples
- **[PHASE_1_README.md](PHASE_1_README.md)** - Phase 1 overview with S3 section

---

## ✅ Verification

Test that everything works:

```bash
# Test imports
python -c "from src.s3_downloader import S3Downloader; from src.s3_uploader import S3Uploader; print('✓ Success')"

# Test CLI
python sync_s3.py --help
```

---

## 🎉 What You Can Do Now

1. **Backup analysis results** after running historical analysis
2. **Share baselines** with team members via S3
3. **Set up new environments** quickly with one command
4. **Sync Silver data** for multiple clients
5. **Version control** your analysis outputs

---

## 🚀 Next Steps

1. **Create .env file** with AWS credentials
2. **Run historical analysis**: `python run_historical_analysis.py --client CDA`
3. **Backup results**: `python sync_s3.py backup-all`
4. **Share with team**: They run `python sync_s3.py download baselines`

---

**Your S3 integration is ready!** 🎊
