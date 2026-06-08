# Historical Data Analysis Guide

**Script**: `run_historical_analysis.py`  
**Purpose**: Process all available Silver layer data to generate comprehensive analysis  
**Uses**: Phase 1 infrastructure (baselines + profiling)

---

## 📊 What It Does

The historical analysis script performs **three main operations**:

### 1. **Multi-Week Data Profiling** 
- Discovers all available weeks in your Silver layer
- Profiles data quality for each week individually
- Generates HTML + JSON reports per week
- Creates signal availability heatmaps across time

### 2. **Comprehensive Baseline Generation**
- Uses ALL available historical data (up to lookback days)
- Generates multi-level baselines (unit/model/client)
- Calculates percentiles across entire history
- Much more robust than single-week baselines

### 3. **Summary Report**
- Coverage trends across all weeks
- Quality score evolution
- Baseline statistics and distribution
- HTML dashboard with visualizations

---

## 🚀 Quick Start

### Basic Usage (Recommended)

```bash
# Analyze all data for client CDA
python run_historical_analysis.py --client CDA
```

This will:
1. ✅ Discover all available weeks automatically
2. ✅ Profile each week's data quality
3. ✅ Generate baselines from 90 days of history
4. ✅ Create comprehensive summary reports

### Output Files

```
outputs/historical_analysis/
├── profile_CDA_week15_2026.json
├── profile_CDA_week15_2026.html
├── profile_CDA_week16_2026.json
├── profile_CDA_week16_2026.html
├── ... (one per week)
├── historical_analysis_summary_CDA.json
└── historical_analysis_summary_CDA.html  ← Main dashboard

dataDep/telemetry/analytical_results/baselines/
├── baseline_20260528.parquet  ← Generated baselines
└── baseline_metadata.json
```

---

## 🎯 Use Cases

### 1. Initial Data Assessment

**When**: First time working with client data  
**Command**:
```bash
python run_historical_analysis.py --client CDA
```

**What you get**:
- Complete picture of data availability
- Quality trends over time
- Robust baselines for Phase 2

---

### 2. Baseline-Only Generation

**When**: You only need baselines, skip profiling  
**Command**:
```bash
python run_historical_analysis.py --client CDA --skip-profiling
```

**What you get**:
- Fast baseline generation
- Uses all available data
- No individual week reports

---

### 3. Extended Historical Baselines

**When**: Want to use more than 90 days  
**Command**:
```bash
python run_historical_analysis.py --client CDA --lookback-days 180
```

**What you get**:
- Baselines from 180 days of data
- More robust percentiles
- Better coverage for sparse signals

---

### 4. Profiling-Only (No Baselines)

**When**: Baselines already exist, just audit data quality  
**Command**:
```bash
python run_historical_analysis.py --client CDA --skip-baselines
```

**What you get**:
- Quality report for each week
- Coverage trends
- No baseline regeneration

---

## 📋 Command-Line Options

```bash
python run_historical_analysis.py [OPTIONS]
```

### Required Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--client` | Client identifier | `--client CDA` |

### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--skip-profiling` | False | Skip weekly profiling |
| `--skip-baselines` | False | Skip baseline generation |
| `--lookback-days` | 90 | Days for baseline generation |
| `--silver-dir` | `dataDep/telemetry/silver` | Silver data location |
| `--config-dir` | `dataDep/telemetry/config` | Config file location |
| `--output-dir` | `outputs/historical_analysis` | Output location |
| `--log-level` | INFO | DEBUG, INFO, WARNING, ERROR |

---

## 📊 Understanding the Outputs

### 1. Weekly Profile Reports

**Files**: `profile_{client}_week{WW}_{YYYY}.html`

**Contains**:
- Signal-level coverage percentages
- Min/max/mean values per signal
- Operational state distribution
- Unit-level availability matrix

**Use for**:
- Identifying data gaps
- Spotting quality issues
- Understanding signal behavior

---

### 2. Summary Dashboard

**File**: `historical_analysis_summary_{client}.html`

**Contains**:
- **Coverage Statistics**
  - Total weeks analyzed
  - Success/failure rates
  - Average coverage across time
  
- **Data Volume Metrics**
  - Total rows processed
  - Min/max coverage weeks
  
- **Baseline Statistics**
  - Total baseline records
  - Signals covered
  - Fallback level distribution (unit/model/client)
  
- **Week-by-Week Details Table**
  - Coverage trends
  - Quality scores
  - Row counts

**Use for**:
- Executive summaries
- Data quality reports
- Baseline validation

---

### 3. Baseline Files

**File**: `baseline_{YYYYMMDD}.parquet`

**Contains**:
- Percentiles (P1, P2, P5, P10, P50, P90, P95, P98, P99) per signal/state
- Statistical moments (mean, std, MAD)
- Sample counts
- Quality scores
- Fallback hierarchy

**Use for**:
- Phase 2 analytical techniques
- Anomaly detection
- Threshold setting

---

## 🔍 Example Scenarios

### Scenario 1: New Client Onboarding

```bash
# Step 1: Analyze all historical data
python run_historical_analysis.py --client NEWCLIENT

# Step 2: Review summary dashboard
# Open: outputs/historical_analysis/historical_analysis_summary_NEWCLIENT.html

# Step 3: Check baselines
# Check: dataDep/telemetry/analytical_results/baselines/baseline_metadata.json
```

**What to look for**:
- ✅ Coverage > 80% across most weeks
- ✅ Baseline fallback distribution (>50% unit-level is good)
- ✅ Quality score = "Good" or "Excellent"
- ⚠️ Failed weeks (investigate data issues)

---

### Scenario 2: Baseline Refresh

```bash
# Regenerate baselines with extended lookback
python run_historical_analysis.py --client CDA --lookback-days 180 --skip-profiling
```

**When to do this**:
- After data quality improvements
- When adding new signals
- Monthly baseline refresh
- After significant time period

---

### Scenario 3: Data Quality Audit

```bash
# Profile all weeks without regenerating baselines
python run_historical_analysis.py --client CDA --skip-baselines
```

**Use for**:
- Quarterly data quality reviews
- Identifying coverage trends
- Spotting degrading signals
- Planning data improvements

---

## 📈 What Phase 1 Provides

### ✅ You Can Use Right Now

| Feature | Script | Output |
|---------|--------|--------|
| **Data Quality Profiling** | `run_historical_analysis.py` | HTML/JSON quality reports |
| **Baseline Generation** | `run_historical_analysis.py` | Multi-level baselines |
| **Coverage Analysis** | Summary dashboard | Coverage trends |
| **Signal Availability** | Weekly profiles | Signal-by-signal metrics |
| **Historical Trends** | Summary JSON | Time-series quality data |

### 🔄 What Phase 2 Will Add

| Feature | Phase | Uses Phase 1 Output |
|---------|-------|---------------------|
| Threshold Deviation | Phase 2 | ✅ Uses baselines |
| Event Detection | Phase 2 | ✅ Uses baselines |
| Trend Analysis | Phase 2 | ✅ Uses weekly data |
| Risk Scoring | Phase 2 | ✅ Uses profiling data |
| System/Unit Health | Phase 3 | ✅ Uses all above |

---

## 💡 Best Practices

### 1. Start with Default Settings

```bash
python run_historical_analysis.py --client CDA
```

Run with defaults first to understand your data before customizing.

---

### 2. Use Extended Lookback for Baselines

```bash
# Use 180 days if you have the data
python run_historical_analysis.py --client CDA --lookback-days 180
```

More data = more robust baselines, especially for:
- Sparse signals
- Rare operational states
- Seasonal variations

---

### 3. Regenerate Baselines Monthly

```bash
# Set up as a monthly job
python run_historical_analysis.py --client CDA --skip-profiling
```

Keep baselines fresh as equipment ages and patterns change.

---

### 4. Review Failed Weeks

Check summary report for failed weeks and investigate:
- Missing files
- Corrupted data
- Schema changes
- Date range issues

---

## 🐛 Troubleshooting

### Error: "Client directory not found"

**Problem**: Silver data directory doesn't exist

**Solution**:
```bash
# Check your Silver directory structure
ls dataDep/telemetry/silver/

# Specify custom path if needed
python run_historical_analysis.py --client CDA --silver-dir /path/to/silver
```

---

### Error: "No data found"

**Problem**: No Week*.parquet files in client directory

**Solution**:
```bash
# Verify files exist
ls dataDep/telemetry/silver/CDA/Telemetry_Wide_With_States/

# Check file naming (should be: WeekNNYearYYYY.parquet)
```

---

### Low Coverage in Report

**Problem**: Signals showing <60% coverage

**Investigation**:
1. Check individual week profiles
2. Identify problematic signals
3. Review Silver layer data quality
4. Consider excluding low-coverage signals

---

### Baseline Fallback Distribution

**Ideal**: >50% unit-level baselines

**If mostly client-level**:
- Insufficient data per unit
- Consider longer lookback period
- May need to accept model/client baselines

---

## 📊 Sample Output

### Console Output

```
================================================================================
HISTORICAL ANALYSIS COMPLETE
================================================================================
End time: 2026-05-28 15:30:45

Outputs saved to: outputs/historical_analysis
  - Week profiles: 24 files
  - Summary report: historical_analysis_summary_CDA.html
  - Summary JSON: historical_analysis_summary_CDA.json
  - Baselines: dataDep/telemetry/analytical_results/baselines/baseline_20260528.parquet

✅ Historical analysis successful!
```

### Summary Dashboard Preview

```
📊 Historical Data Analysis Summary
Analysis Date: 2026-05-28T15:30:45
Client: CDA

Coverage Statistics
Total Weeks: 24
Successful: 23
Failed: 1
Avg Coverage: 87.5%

Data Volume
Total Rows: 45,234,567
Min Coverage: 62.3%
Max Coverage: 95.8%

Baseline Statistics
Total Baseline Records: 1,234
Signals Covered: 18
Operational States: 3

Baseline Fallback Distribution
- unit: 856 (69.4%)
- model: 312 (25.3%)
- client: 66 (5.3%)
```

---

## 🎯 Next Steps After Analysis

1. **Review Summary Dashboard**
   - Open `historical_analysis_summary_{client}.html`
   - Check coverage trends
   - Identify data quality issues

2. **Validate Baselines**
   - Check `baseline_metadata.json`
   - Ensure adequate sample counts
   - Review fallback distribution

3. **Proceed to Phase 2**
   - If coverage > 80%: ✅ Ready for techniques
   - If coverage < 60%: ⚠️ Address data quality first

4. **Set Up Regular Runs**
   - Monthly baseline refresh
   - Quarterly quality audits
   - After data pipeline changes

---

## 📞 Quick Reference

```bash
# Most common use case
python run_historical_analysis.py --client CDA

# Just baselines
python run_historical_analysis.py --client CDA --skip-profiling

# Extended lookback
python run_historical_analysis.py --client CDA --lookback-days 180

# Just quality check
python run_historical_analysis.py --client CDA --skip-baselines
```

---

**Ready to analyze your data!** 🚀

Run `python run_historical_analysis.py --client CDA` to get started.
