# Phase 4: Validation — Implementation Guide

**Duration**: Week 7 (5 working days)  
**Objective**: Validate framework performance against known failures and calibrate thresholds  
**Status**: Not Started  
**Last Updated**: May 24, 2026  
**Prerequisites**: Phase 3 completed (system/unit health, diagnostic rules operational)

---

## 📋 Table of Contents

1. [Phase Overview](#phase-overview)
2. [Timeline](#timeline)
3. [Inputs](#inputs)
4. [Outputs](#outputs)
5. [Task Checklist](#task-checklist)
6. [Deliverables](#deliverables)
7. [Success Criteria](#success-criteria)
8. [Implementation Notes](#implementation-notes)

---

## 🎯 Phase Overview

### Purpose

**Prove the framework works** before calling it production-ready:
- Collect ≥10 known failure events from historical data
- Run backtest: did we detect these events in advance?
- Measure detection rate, advance warning time, false positive rate
- Calibrate thresholds to optimize performance
- Generate validation report with recommendations

### Why This Phase Matters

**Without validation, we're flying blind.** This phase answers:
- Does our framework actually predict failures?
- How much advance warning do we provide?
- Are false positives manageable?
- Which techniques work best?
- Do we need to adjust thresholds?

### Key Principle

**Be brutally honest.** If detection rate is low, acknowledge it. If false positives are high, document it. Use findings to improve.

---

## 📅 Timeline

### Week 7: Validation & Calibration

#### Day 31: Known Event Collection

**Morning** (4 hours):
- Review maintenance records for past 6 months
- Identify confirmed failure events (≥10 events)
- Collect event metadata:
  - Unit ID, failure date, failure type (engine, transmission, brakes, etc.)
  - Maintenance action taken
  - Downtime duration
  - Root cause (if documented)

**Afternoon** (4 hours):
- Categorize events by system (Engine, Transmission, etc.)
- Map events to signal registry (which signals should have alerted?)
- Document expected detection windows (e.g., 7 days before failure)
- Create known_events.csv validation dataset

**Output**: `data/validation/known_events.csv` (≥10 events)

---

#### Day 32: Backtest Execution - Part 1

**Morning** (4 hours):
- Implement backtest script
- For each known event:
  - Load technique results for 30 days before failure
  - Load system health for 4 weeks before failure
  - Load unit health for 4 weeks before failure
- Extract timeline of alerts (when did scores exceed thresholds?)

**Afternoon** (4 hours):
- Calculate advance warning time per event
- Identify which techniques detected which events
- Detect missed events (no alerts before failure)
- Document detection timeline per event

**Output**: `scripts/backtest_validation.py`, `data/validation/backtest_results.csv` (partial)

---

#### Day 33: Backtest Execution - Part 2

**Morning** (4 hours):
- Continue backtest for all events
- Calculate detection metrics:
  - Detection rate: % of events detected
  - Mean advance warning: days before failure
  - Median advance warning
  - Minimum advance warning
- Break down by system type (Engine, Transmission, etc.)

**Afternoon** (4 hours):
- Analyze false negatives (missed events)
  - Why were they missed? (low signal coverage, state mismatch, insufficient data)
  - Could they have been detected with different thresholds?
- Document failure modes (which types of failures are hardest to detect?)

**Output**: `data/validation/backtest_results.csv` (complete)

---

#### Day 34: False Positive Analysis

**Morning** (4 hours):
- Sample 50-100 high-score units from past 3 months
- Check: did these units actually have issues?
- Cross-reference with maintenance records
- Calculate false positive rate: (false alerts / total alerts)

**Afternoon** (4 hours):
- Analyze false positive patterns:
  - Which techniques produce most false positives?
  - Which signals are most noisy?
  - Which systems have highest FP rate?
- Identify threshold tuning opportunities

**Output**: `data/validation/false_positive_analysis.csv`

---

#### Day 35: Threshold Calibration

**Morning** (4 hours):
- Analyze ROC curves for threshold tuning
- Test alternative thresholds:
  - Alerta threshold (current: 40-70, test: 35-75, 45-65)
  - Anormal threshold (current: 70+, test: 65+, 75+)
- Measure impact on detection rate and FP rate

**Afternoon** (4 hours):
- Select optimal thresholds (balance detection vs. FP)
- Update technique_config.yaml with calibrated values
- Re-run backtest with new thresholds
- Document threshold calibration decisions

**Output**: `data/validation/threshold_calibration.csv`, updated `technique_config.yaml`

---

#### Day 36: Validation Report & Recommendations

**Morning** (4 hours):
- Generate comprehensive validation report:
  - Executive summary (key findings)
  - Detection performance (rate, advance warning)
  - False positive analysis
  - Technique performance comparison
  - Threshold calibration results
  - Known limitations and failure modes

**Afternoon** (4 hours):
- Add recommendations for production deployment
- Document model confidence (where are we confident? where are we uncertain?)
- Create presentation slides for stakeholders
- Review report with domain expert

**Output**: `documentation/telemetry/validation_report.md`, `outputs/validation_presentation.pptx`

---

## 📥 Inputs

### Data Inputs

| Input | Location | Format | Created By | Notes |
|-------|----------|--------|------------|-------|
| Maintenance records | External system | CSV/Excel | Maintenance team | Past 6 months |
| Technique results | `technique_results/*/` | Parquet | Phase 2 | All techniques |
| System health | `system_health/` | Parquet | Phase 3 | Weekly system scores |
| Unit health | `unit_health/` | Parquet | Phase 3 | Weekly unit scores |
| Silver telemetry | `data/telemetry/silver/` | Parquet | Upstream | For manual review |

### Configuration Inputs

| Parameter | Source | Current Value | Notes |
|-----------|--------|---------------|-------|
| Alerta threshold | technique_config.yaml | 40-70 | To be calibrated |
| Anormal threshold | technique_config.yaml | 70+ | To be calibrated |
| Minimum advance warning | Business requirement | 3 days | Success criterion |
| Maximum false positive rate | Business requirement | 25% | Success criterion |

---

## 📤 Outputs

### Code Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| Backtest script | `scripts/backtest_validation.py` | Replay events and measure detection |
| Validation analyzer | `scripts/validation_analyzer.py` | Calculate metrics and generate report |
| ROC curve generator | `scripts/roc_analysis.py` | Threshold optimization |

### Data Artifacts

| Artifact | Location | Format | Purpose |
|----------|----------|--------|---------|
| Known events | `data/validation/known_events.csv` | CSV | Ground truth failure records |
| Backtest results | `data/validation/backtest_results.csv` | CSV | Detection timeline per event |
| False positive analysis | `data/validation/false_positive_analysis.csv` | CSV | FP rate analysis |
| Threshold calibration | `data/validation/threshold_calibration.csv` | CSV | Optimal threshold testing |
| Validation metrics | `data/validation/validation_metrics.json` | JSON | Summary statistics |

### Documentation Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| Validation report | `documentation/telemetry/validation_report.md` | Comprehensive validation findings |
| Validation presentation | `outputs/validation_presentation.pptx` | Stakeholder summary |
| Calibration decisions log | `data/validation/calibration_decisions.md` | Threshold tuning rationale |

---

## ✅ Task Checklist

### Week 7: Validation & Calibration

**Day 31: Known Event Collection**
- [ ] Request maintenance records from past 6 months
- [ ] Review records and identify ≥10 confirmed failures
- [ ] Collect event metadata (unit, date, type, root cause)
- [ ] Categorize events by system
- [ ] Map events to signal registry (expected alerts)
- [ ] Document expected detection windows
- [ ] Create known_events.csv dataset
- [ ] Validate event data quality (complete metadata)

**Day 32: Backtest Execution - Part 1**
- [ ] Implement backtest_validation.py script
- [ ] Load technique results for 30 days before each failure
- [ ] Load system health for 4 weeks before each failure
- [ ] Load unit health for 4 weeks before each failure
- [ ] Extract alert timeline (when scores exceeded thresholds)
- [ ] Calculate advance warning time per event
- [ ] Identify which techniques detected which events
- [ ] Detect missed events (false negatives)
- [ ] Document detection timeline for first 5 events

**Day 33: Backtest Execution - Part 2**
- [ ] Complete backtest for all ≥10 events
- [ ] Calculate overall detection rate
- [ ] Calculate mean advance warning (days)
- [ ] Calculate median advance warning
- [ ] Calculate minimum advance warning
- [ ] Break down metrics by system type
- [ ] Analyze false negatives (why were they missed?)
- [ ] Document failure modes (hardest-to-detect types)
- [ ] Generate backtest_results.csv

**Day 34: False Positive Analysis**
- [ ] Sample 50-100 high-score units from past 3 months
- [ ] Cross-reference with maintenance records
- [ ] Identify true positives (real issues)
- [ ] Identify false positives (no issues found)
- [ ] Calculate false positive rate
- [ ] Analyze FP patterns by technique
- [ ] Analyze FP patterns by signal
- [ ] Analyze FP patterns by system
- [ ] Identify threshold tuning opportunities
- [ ] Generate false_positive_analysis.csv

**Day 35: Threshold Calibration**
- [ ] Implement ROC curve analysis
- [ ] Test Alerta threshold variations (35-75, 40-70, 45-65)
- [ ] Test Anormal threshold variations (65+, 70+, 75+)
- [ ] Measure detection rate for each threshold set
- [ ] Measure FP rate for each threshold set
- [ ] Select optimal thresholds (balance detection vs. FP)
- [ ] Update technique_config.yaml
- [ ] Re-run backtest with new thresholds
- [ ] Document calibration decisions
- [ ] Generate threshold_calibration.csv

**Day 36: Validation Report**
- [ ] Write executive summary (key findings)
- [ ] Document detection performance (rate + advance warning)
- [ ] Document false positive analysis
- [ ] Compare technique performance (which works best?)
- [ ] Document threshold calibration results
- [ ] Document known limitations and failure modes
- [ ] Add recommendations for production deployment
- [ ] Document model confidence (strengths/weaknesses)
- [ ] Create presentation slides for stakeholders
- [ ] Review report with domain expert
- [ ] Finalize validation_report.md

---

## 📦 Deliverables

### Critical Deliverables (Must-Have)

1. **Known Events Dataset**
   - At least 10 confirmed failure events
   - Complete metadata (unit, date, type, root cause)
   - Categorized by system

2. **Backtest Results**
   - Detection rate calculated
   - Advance warning time measured
   - False negative analysis complete
   - Technique performance compared

3. **False Positive Analysis**
   - FP rate calculated from sample
   - FP patterns identified
   - Threshold tuning opportunities documented

4. **Validation Report**
   - Comprehensive findings documented
   - Recommendations for production
   - Known limitations disclosed
   - Stakeholder presentation prepared

### Important Deliverables (Should-Have)

5. **Calibrated Thresholds**
   - Optimal thresholds identified
   - technique_config.yaml updated
   - Backtest re-run with new thresholds

6. **Validation Metrics**
   - Summary statistics in JSON format
   - System-level breakdown
   - Technique-level breakdown

### Nice-to-Have Deliverables

7. **ROC Curves**
   - Visual threshold analysis
   - Trade-off plots (detection vs. FP)

8. **Confidence Intervals**
   - Statistical significance of metrics
   - Uncertainty quantification

---

## 🎯 Success Criteria

### Functional Success Criteria

| Criterion | Target | Validation Method |
|-----------|--------|-------------------|
| Detection rate | ≥70% of known events | Backtest results |
| Advance warning time | ≥3 days (median) | Backtest results |
| False positive rate | ≤25% | FP analysis sample |
| Known events collected | ≥10 events | Count in dataset |

### Technical Success Criteria

| Criterion | Target | Validation Method |
|-----------|--------|-------------------|
| Backtest execution | Completes successfully for all events | Script logs |
| Event categorization | 100% of events mapped to systems | Manual review |
| Metrics calculation | All metrics computed correctly | Unit tests |
| Threshold calibration | Optimal values identified | ROC analysis |

### Documentation Success Criteria

| Criterion | Target | Validation Method |
|-----------|--------|-------------------|
| Validation report completeness | All sections filled | Manual review |
| Findings clarity | Stakeholder can understand | Presentation review |
| Recommendations actionability | Clear next steps | Expert review |
| Limitations transparency | Weaknesses documented | Honesty check |

### Exit Gates (Must Pass to Proceed to Phase 5 or Production)

**Gate 1: Performance Validation**
- [ ] Detection rate ≥70% (ideally ≥80%)
- [ ] Advance warning ≥3 days median
- [ ] False positive rate ≤25% (ideally ≤20%)
- [ ] At least 10 known events tested

**Gate 2: Technique Validation**
- [ ] At least 2 techniques show good performance
- [ ] Technique failure modes understood
- [ ] Best-performing techniques identified
- [ ] Weak techniques documented (improve or disable)

**Gate 3: Threshold Calibration**
- [ ] Thresholds tested with ROC analysis
- [ ] Optimal thresholds selected and documented
- [ ] Backtest re-run with new thresholds
- [ ] Improvement demonstrated (if thresholds changed)

**Gate 4: Stakeholder Approval**
- [ ] Validation report reviewed by domain expert
- [ ] Findings accepted as reasonable
- [ ] Recommendations agreed upon
- [ ] Decision made: proceed to Phase 5, go to production, or iterate

---

## 📝 Implementation Notes

### Week 7 Notes

**Day 31 (Known Event Collection):**
```
Date: ___________
Analyst: ___________

Work Completed:
- 
- 

Known Events Collected:
Count: _____
Date range: _____ to _____

Events by System:
- Engine: _____
- Transmission: _____
- Brakes: _____
- Differential: _____
- Hydraulics: _____
- Other: _____

Event Examples:
Unit | Date | System | Failure Type | Root Cause
_____|______|________|______________|___________


Data Quality Issues:
- 
- 

Next Steps:
- 
```

**Day 32 (Backtest Part 1):**
```
Date: ___________
Analyst: ___________

Work Completed:
- 
- 

Events Processed: _____ / _____

Detection Summary (First 5 Events):
Event | Detected | Technique | Advance Warning (days)
______|__________|___________|_______________________


Missed Events:
Event | Reason
______|_______


Next Steps:
- 
```

**Day 33 (Backtest Part 2):**
```
Date: ___________
Analyst: ___________

Work Completed:
- 
- 

Overall Detection Metrics:
- Detection rate: _____%
- Mean advance warning: _____ days
- Median advance warning: _____ days
- Min advance warning: _____ days
- Max advance warning: _____ days

Detection by System:
System | Detection Rate | Avg Advance Warning
_______|________________|____________________


False Negatives Analysis:
- Insufficient data: _____ events
- State mismatch: _____ events
- Low signal coverage: _____ events
- Other: _____ events

Hardest-to-Detect Failure Types:
1. _____
2. _____

Next Steps:
- 
```

**Day 34 (False Positive Analysis):**
```
Date: ___________
Analyst: ___________

Work Completed:
- 
- 

Sample Statistics:
- Units sampled: _____
- True positives: _____
- False positives: _____
- False positive rate: _____%

FP by Technique:
Technique | FP Count | FP Rate
__________|__________|________


FP by Signal:
Signal | FP Count | Frequency
_______|__________|__________


FP by System:
System | FP Rate
_______|________


Threshold Tuning Opportunities:
- 
- 

Next Steps:
- 
```

**Day 35 (Threshold Calibration):**
```
Date: ___________
Analyst: ___________

Work Completed:
- 
- 

Threshold Variations Tested:
Config | Alerta | Anormal | Detection Rate | FP Rate
_______|________|_________|________________|________


Selected Optimal Thresholds:
- Alerta: _____
- Anormal: _____
- Rationale: _____

Backtest with New Thresholds:
- Detection rate: _____%
- FP rate: _____%
- Improvement: _____

Calibration Decisions:
- 
- 

Next Steps:
- 
```

**Day 36 (Validation Report):**
```
Date: ___________
Analyst: ___________

Work Completed:
- 
- 

Key Findings:
1. _____
2. _____
3. _____

Performance Summary:
- Detection rate: _____%
- Advance warning: _____ days (median)
- False positive rate: _____%
- Assessment: Meets criteria / Needs improvement

Best Performing Techniques:
1. _____
2. _____

Weakest Techniques:
1. _____
2. _____

Recommendations for Production:
1. _____
2. _____
3. _____

Known Limitations:
1. _____
2. _____

Stakeholder Feedback:
- 
- 

Decision: Proceed to Phase 5 / Go to Production / Iterate

Next Steps:
- 
```

---

### Phase 4 Retrospective

**To be completed at end of Phase 4:**

```
Date Completed: ___________
Team: ___________

What Went Well:
- 
- 

What Didn't Go Well:
- 
- 

Validation Results:
- Detection rate: _____
- Advance warning: _____
- FP rate: _____
- Met success criteria: Yes / No

Surprises:
- 
- 

Key Learnings:
- 
- 

Technique Performance Insights:
- Most effective: _____
- Least effective: _____
- Unexpected finding: _____

False Positive Insights:
- Main sources: _____
- Mitigation strategies: _____

Known Event Quality:
- Dataset quality: Good / Fair / Poor
- Need more events: Yes / No
- Event diversity: Good / Fair / Poor

Recommendations for Phase 5 (if applicable):
- 
- 

Production Readiness:
- Framework performance: Ready / Needs Work
- Thresholds calibrated: Yes / No
- Documentation complete: Yes / No
- Stakeholder approval: Yes / No / Pending
```

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-05-24 | Senior Data Scientist | Initial Phase 4 implementation guide |

---

**Related Documents**
- [Implementation Plan (Main)](implementation_plan.md)
- [Phase 3 Guide](implementation_phase_3.md)
- [Phase 5 Guide](implementation_phase_5.md)
- [Validation Report](validation_report.md) (to be created in Phase 4)
