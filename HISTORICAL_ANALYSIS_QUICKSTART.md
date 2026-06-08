# Historical Analysis - Quick Reference

## 🎯 What You Asked For

> "I want to create a historical data analysis. In other words run the script over all the data."

## ✅ Solution Created

**Script**: `run_historical_analysis.py`

### What It Does

```
📊 Automatically processes ALL your Silver layer data

1. Discovers Available Data
   └─ Finds all Week*.parquet files
   └─ Sorts chronologically

2. Profiles Each Week
   └─ Data quality metrics
   └─ Signal coverage
   └─ HTML + JSON reports

3. Generates Baselines
   └─ Uses ALL historical data
   └─ Multi-level (unit/model/client)
   └─ More robust than single-week

4. Creates Summary Dashboard
   └─ Coverage trends
   └─ Quality evolution
   └─ Baseline statistics
```

---

## 🚀 How to Use

### Basic Command (Recommended)

```bash
python run_historical_analysis.py --client CDA
```

That's it! It will:
- ✅ Find all your data automatically
- ✅ Process every week
- ✅ Generate comprehensive reports
- ✅ Create baselines from everything

### What You Get

```
outputs/historical_analysis/
├── historical_analysis_summary_CDA.html  ← Main dashboard
├── historical_analysis_summary_CDA.json  ← Summary data
├── profile_CDA_week15_2026.html
├── profile_CDA_week16_2026.html
└── ... (one per week)

dataDep/telemetry/analytical_results/baselines/
├── baseline_20260528.parquet  ← Comprehensive baselines
└── baseline_metadata.json
```

---

## 📊 Example Output Preview

### Console Output

```
================================================================================
HISTORICAL DATA ANALYSIS
================================================================================

Discovering available weeks...
✓ Found 24 weeks of data
  First week: Week 15/2026
  Last week: Week 38/2026

================================================================================
STEP 1: PROFILING ALL WEEKS
================================================================================

Profiling Week 15/2026 (1/24)
✓ Week 15/2026 profiled: 87.5% coverage

Profiling Week 16/2026 (2/24)
✓ Week 16/2026 profiled: 89.2% coverage
...

✓ Profiling complete: 23/24 weeks successful

================================================================================
STEP 2: GENERATING COMPREHENSIVE BASELINES
================================================================================

Generating Baselines from Historical Data
Lookback: 90 days

Loaded 3,456,789 rows for baseline generation
Generating unit-level baselines...
Generated 856 unit-level baselines
Generating model-level baselines...
Generated 312 model-level baselines
Generating client-level baselines...
Generated 66 client-level baselines

✓ Generated 1,234 baseline records
✓ Saved to: dataDep/telemetry/analytical_results/baselines/baseline_20260528.parquet

================================================================================
STEP 3: GENERATING SUMMARY REPORT
================================================================================

✓ Summary saved to: outputs/historical_analysis/historical_analysis_summary_CDA.json
✓ HTML report saved to: outputs/historical_analysis/historical_analysis_summary_CDA.html

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

### Dashboard Preview (HTML)

```
📊 Historical Data Analysis Summary
═══════════════════════════════════

Client: CDA
Analysis Date: 2026-05-28T15:30:45

Coverage Statistics
├─ Total Weeks: 24
├─ Successful: 23
├─ Failed: 1
└─ Avg Coverage: 87.5%

Data Volume
├─ Total Rows: 45,234,567
├─ Min Coverage: 62.3%
└─ Max Coverage: 95.8%

Baseline Statistics
├─ Total Records: 1,234
├─ Signals Covered: 18
└─ States: 3

Fallback Distribution
├─ Unit-level: 856 (69.4%)  ← Good!
├─ Model-level: 312 (25.3%)
└─ Client-level: 66 (5.3%)

Week-by-Week Details
┌──────┬──────┬──────────┬───────────┬────────────┐
│ Week │ Year │ Status   │ Coverage  │ Quality    │
├──────┼──────┼──────────┼───────────┼────────────┤
│  15  │ 2026 │ ✓ Success│   87.5%   │ Excellent  │
│  16  │ 2026 │ ✓ Success│   89.2%   │ Excellent  │
│  17  │ 2026 │ ✗ Failed │     -     │ Error      │
│  18  │ 2026 │ ✓ Success│   91.3%   │ Excellent  │
│  ... │  ... │    ...   │    ...    │    ...     │
└──────┴──────┴──────────┴───────────┴────────────┘
```

---

## 💡 Common Use Cases

### 1. First Time Setup

```bash
# Get complete picture of your data
python run_historical_analysis.py --client CDA
```

**Use the outputs to**:
- Understand data availability
- Identify quality issues
- Generate robust baselines
- Plan Phase 2 implementation

### 2. Baseline Refresh

```bash
# Use more historical data for better baselines
python run_historical_analysis.py --client CDA --lookback-days 180
```

### 3. Quality Audit Only

```bash
# Skip baseline generation if already exists
python run_historical_analysis.py --client CDA --skip-baselines
```

### 4. Fast Baseline Update

```bash
# Skip profiling if you just need baselines
python run_historical_analysis.py --client CDA --skip-profiling
```

---

## 🎯 What Phase 1 Outputs Enable

### Immediate Use

| Output | What You Can Do |
|--------|-----------------|
| **Weekly Profiles** | Identify data gaps, spot quality issues |
| **Summary Dashboard** | Executive reporting, trend analysis |
| **Baselines (Parquet)** | **Ready for Phase 2 techniques** ✅ |
| **Coverage Metrics** | Plan data improvements |
| **Quality Scores** | Track data health over time |

### Phase 2 Will Use

| Phase 2 Feature | Uses This Output |
|-----------------|------------------|
| Threshold Deviation | ✅ Baselines (P95, P5) |
| Event Detection | ✅ Baselines + Profiles |
| Trend Analysis | ✅ Weekly profiles |
| Risk Scoring | ✅ All outputs |

---

## 🔍 Quick Validation

After running, check:

1. **Summary Dashboard**
   ```bash
   # Open in browser
   outputs/historical_analysis/historical_analysis_summary_CDA.html
   ```
   
   ✅ Look for:
   - Coverage > 80%
   - Most weeks successful
   - Unit-level baselines > 50%

2. **Baseline Metadata**
   ```bash
   cat dataDep/telemetry/analytical_results/baselines/baseline_metadata.json
   ```
   
   ✅ Check:
   - Total records > 500
   - All signals covered
   - Sample counts adequate

3. **Logs**
   ```bash
   cat logs/historical_analysis_YYYYMMDD.log
   ```

---

## 📖 Full Documentation

- **[HISTORICAL_ANALYSIS_GUIDE.md](HISTORICAL_ANALYSIS_GUIDE.md)** - Complete usage guide
- **[PHASE_1_README.md](PHASE_1_README.md)** - Phase 1 overview
- **[PHASE_1_COMPLETION_REPORT.md](documentation/telemetry/PHASE_1_COMPLETION_REPORT.md)** - Implementation details

---

## ✅ Summary

**You asked**: "Run script over all data"

**You got**:
- ✅ `run_historical_analysis.py` - Batch processor
- ✅ Automatic week discovery
- ✅ Multi-week profiling
- ✅ Comprehensive baselines
- ✅ Summary dashboard
- ✅ Ready to use NOW

**Next step**: 
```bash
python run_historical_analysis.py --client CDA
```

**Then**: Open `outputs/historical_analysis/historical_analysis_summary_CDA.html` to see results!

---

**Questions?** Check [HISTORICAL_ANALYSIS_GUIDE.md](HISTORICAL_ANALYSIS_GUIDE.md) for detailed examples and troubleshooting.
