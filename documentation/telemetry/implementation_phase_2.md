# Phase 2: Core Analytics — Implementation Guide

**Duration**: Weeks 3-4 (10 working days)  
**Objective**: Implement explainable, high-value analytical techniques  
**Status**: Not Started  
**Last Updated**: May 24, 2026  
**Prerequisites**: Phase 1 completed (baselines, signal registry, orchestration ready)

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

Implement the first production-quality analytical techniques:
- **Threshold Deviation**: Detect repeated limit violations
- **Event Detection**: Identify persistent abnormal episodes
- **Trend Analysis**: Detect progressive degradation
- **Score Normalization**: Convert native metrics to 0-100 scales

### Why This Phase Matters

This is where the framework **proves value**. By end of Phase 2:
- Can detect abnormal behavior using explainable methods
- Can identify degradation trends before failure
- Can generate risk and confidence scores
- Can explain every score with evidence

### Key Principle

**Start simple, prove value.** These techniques are statistical, transparent, and explainable. No black boxes.

---

## 📅 Timeline

### Week 3: Threshold & Event Detection

#### Day 11: Threshold Deviation - Daily Analysis

**Morning** (4 hours):
- Implement TechniqueResult dataclass
- Create abstract BaseTechnique class
- Build ThresholdDeviation class skeleton
- Implement data loading for 24h window

**Afternoon** (4 hours):
- Implement baseline retrieval with state matching
- Add comparison logic (P1, P5, P95, P99)
- Calculate exceedance percentages
- Compute max/mean deviation

**Output**: `src/techniques/base.py`, `src/techniques/threshold_deviation.py` (partial)

---

#### Day 12: Threshold Deviation - Scoring & Output

**Morning** (4 hours):
- Implement risk score normalization
- Add confidence score calculation
- Apply status classification (Normal/Alerta/Anormal)
- Build evidence dictionary

**Afternoon** (4 hours):
- Implement result writer to `technique_results/threshold_deviation/`
- Add partitioning by year/month/day
- Write unit tests for threshold logic
- Test on sample unit data

**Output**: `src/techniques/threshold_deviation.py` (complete)

---

#### Day 13: Threshold Deviation - Weekly Summary

**Morning** (4 hours):
- Implement weekly aggregation of daily threshold results
- Calculate weekly metrics (total abnormal%, peak deviation, event count)
- Generate weekly summary TechniqueResult
- Add validity period metadata (2 days for daily, 1 week for weekly)

**Afternoon** (4 hours):
- Integrate with Prefect flow
- Schedule daily execution (01:00)
- Test execution on full fleet (all units)
- Review and fix any issues

**Output**: Threshold deviation running in production mode

---

#### Day 14: Event Detection - Grouping Logic

**Morning** (4 hours):
- Implement Event dataclass
- Load minute-level abnormal flags from threshold results
- Group consecutive abnormal minutes into events
- Handle gaps (<5min apart → merge)

**Afternoon** (4 hours):
- Calculate event metadata (start, end, duration, peak, mean)
- Classify event type (spike <5min, episode 5-60min, sustained >60min)
- Compute event severity score
- Add operational state tracking

**Output**: `src/techniques/event_detection.py` (partial), `src/models/event.py`

---

#### Day 15: Event Detection - Storage & Integration

**Morning** (4 hours):
- Implement event writer to `events/` partition
- Add event deduplication logic
- Store event references in TechniqueResult
- Write event detection unit tests

**Afternoon** (4 hours):
- Integrate with Prefect flow (depends on threshold)
- Schedule daily execution (02:00, after threshold)
- Test on full fleet
- Review event statistics (how many per day per unit?)

**Output**: `src/techniques/event_detection.py` (complete), events stored

---

### Week 4: Trend Analysis & Normalization

#### Day 16: Weekly Signal Aggregation

**Morning** (4 hours):
- Implement weekly aggregator
- Group by unit + signal + state + week
- Calculate statistics: mean, median, std, P5, P50, P95, P99
- Add hours_in_state, sample_count, coverage

**Afternoon** (4 hours):
- Calculate derived metrics: abnormal%, event_count, longest_event
- Write to `aggregates/weekly/` partition
- Add week number (ISO week) handling
- Test aggregation on sample data

**Output**: `src/techniques/weekly_aggregator.py`

---

#### Day 17: Trend Analysis - Regression Logic

**Morning** (4 hours):
- Implement TrendAnalysis class
- Load weekly aggregates for lookback windows (4w, 8w, 12w)
- Fit linear regression (scipy.stats.linregress)
- Calculate slope, intercept, R², p-value

**Afternoon** (4 hours):
- Implement robust regression (Theil-Sen) as alternative
- Calculate recent vs. baseline delta
- Test statistical significance (require p<0.05)
- Classify trend direction (improving/stable/degrading)

**Output**: `src/techniques/trend_analysis.py` (partial)

---

#### Day 18: Trend Analysis - Scoring & Output

**Morning** (4 hours):
- Implement trend risk score normalization
- Formula: magnitude (delta%) + persistence (R²) + significance bonus
- Calculate confidence based on valid weeks, R², p-value
- Build trend evidence dictionary

**Afternoon** (4 hours):
- Write results to `technique_results/trend_analysis/`
- Partition by year/week
- Write unit tests for trend logic
- Handle edge cases (<4 weeks data)

**Output**: `src/techniques/trend_analysis.py` (complete)

---

#### Day 19: Trend Analysis - Integration & Testing

**Morning** (4 hours):
- Integrate with Prefect flow
- Add dependency on weekly aggregation task
- Schedule weekly execution (Sunday 04:00)
- Test on full fleet

**Afternoon** (4 hours):
- Review trend results for all units
- Identify units with degrading trends
- Validate against known issues (if available)
- Document typical trend patterns observed

**Output**: Trend analysis running in production mode

---

#### Day 20: Score Normalization & Quality Assurance

**Morning** (4 hours):
- Review all technique outputs
- Implement score band validation (0-30, 30-60, 60-80, 80-100)
- Add normalization version tracking
- Document normalization logic per technique

**Afternoon** (4 hours):
- Create sample technique results for all 3 techniques
- Generate example explanations
- Review score distributions (histograms)
- Run end-to-end tests (Silver → technique results)

**Output**: `documentation/normalization_guide.md`, quality assurance report

---

## 📥 Inputs

### Data Inputs

| Input | Location | Format | Created By | Notes |
|-------|----------|--------|------------|-------|
| Silver telemetry | `data/telemetry/silver/{client}/` | Parquet | Upstream pipeline | Minute-level |
| Baselines | `data/telemetry/analytical_results/baselines/` | Parquet + JSON | Phase 1 | State-specific percentiles |
| Signal registry | `data/telemetry/config/signal_registry_v1.yaml` | YAML | Phase 1 | Signal metadata |
| Technique config | `data/telemetry/config/technique_config.yaml` | YAML | Phase 1 | Cadence, windows, thresholds |

### Configuration Inputs

| Parameter | Source | Default | Notes |
|-----------|--------|---------|-------|
| Threshold percentiles | Baseline file | P1, P5, P95, P99 | State-specific |
| Event merge gap | Technique config | 5 minutes | Consecutive abnormal minutes |
| Minimum trend weeks | Technique config | 4 weeks | For reliable regression |
| Trend p-value threshold | Technique config | 0.05 | Statistical significance |

---

## 📤 Outputs

### Code Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| BaseTechnique | `src/techniques/base.py` | Abstract base class for all techniques |
| TechniqueResult | `src/models/technique_result.py` | Standardized result schema |
| ThresholdDeviation | `src/techniques/threshold_deviation.py` | Daily/weekly threshold analysis |
| EventDetection | `src/techniques/event_detection.py` | Abnormal episode detection |
| WeeklyAggregator | `src/techniques/weekly_aggregator.py` | Weekly signal summaries |
| TrendAnalysis | `src/techniques/trend_analysis.py` | Degradation trend detection |
| Event model | `src/models/event.py` | Event dataclass |

### Data Artifacts

| Artifact | Location | Format | Cadence | Purpose |
|----------|----------|--------|---------|---------|
| Threshold results (daily) | `technique_results/threshold_deviation/year=*/month=*/day=*/` | Parquet | Daily | 24h threshold analysis |
| Threshold summary (weekly) | `technique_results/threshold_deviation/year=*/week=*/` | Parquet | Weekly | 7-day aggregated view |
| Events | `events/year=*/month=*/day=*/` | Parquet | Daily | Abnormal episode records |
| Weekly aggregates | `aggregates/weekly/year=*/week=*/` | Parquet | Weekly | Signal summaries per week |
| Trend results | `technique_results/trend_analysis/year=*/week=*/` | Parquet | Weekly | Degradation trends |

### Documentation Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| Normalization guide | `documentation/normalization_guide.md` | Score mapping logic per technique |
| Technique comparison | `documentation/technique_comparison.md` | Strengths/weaknesses of each |
| Example results | `documentation/example_results/` | Sample TechniqueResult JSONs |

---

## ✅ Task Checklist

### Week 3: Threshold & Event Detection

**Day 11: Threshold Deviation - Daily Analysis**
- [ ] Implement TechniqueResult dataclass
- [ ] Create BaseTechnique abstract class
- [ ] Build ThresholdDeviation class skeleton
- [ ] Implement 24h window data loading
- [ ] Add baseline retrieval with state matching
- [ ] Implement comparison logic (P1, P5, P95, P99)
- [ ] Calculate exceedance percentages (warning, abnormal)
- [ ] Compute max and mean deviation
- [ ] Write unit tests for data loading

**Day 12: Threshold Deviation - Scoring & Output**
- [ ] Implement risk score normalization formula
- [ ] Calculate confidence score from data quality
- [ ] Apply status classification thresholds
- [ ] Build evidence dictionary (complete metadata)
- [ ] Implement result writer with partitioning
- [ ] Add schema versioning to output
- [ ] Write unit tests for scoring logic
- [ ] Test on 3 sample units (normal, alerta, anormal)

**Day 13: Threshold Deviation - Weekly Summary**
- [ ] Implement weekly aggregation of daily results
- [ ] Calculate cumulative weekly metrics
- [ ] Generate weekly summary TechniqueResult
- [ ] Add validity period metadata (daily=2d, weekly=1w)
- [ ] Create Prefect task for threshold deviation
- [ ] Schedule daily execution at 01:00
- [ ] Test execution on full fleet (all units)
- [ ] Review results and fix any errors
- [ ] Document typical threshold violation patterns

**Day 14: Event Detection - Grouping Logic**
- [ ] Implement Event dataclass
- [ ] Load minute-level abnormal flags from threshold
- [ ] Group consecutive abnormal minutes
- [ ] Handle gaps (<5min → merge events)
- [ ] Calculate event start, end, duration
- [ ] Compute peak value and deviation
- [ ] Calculate mean deviation during event
- [ ] Classify event type (spike/episode/sustained)
- [ ] Add operational state tracking per event

**Day 15: Event Detection - Storage & Integration**
- [ ] Implement event writer to `events/` partition
- [ ] Add event deduplication logic
- [ ] Store event IDs in TechniqueResult references
- [ ] Write event detection unit tests
- [ ] Create Prefect task (depends on threshold)
- [ ] Schedule daily execution at 02:00
- [ ] Test on full fleet
- [ ] Calculate event statistics (count, avg duration)
- [ ] Review longest and most severe events

### Week 4: Trend Analysis & Normalization

**Day 16: Weekly Signal Aggregation**
- [ ] Implement WeeklyAggregator class
- [ ] Group by unit + signal + state + week
- [ ] Calculate statistics (mean, median, std, P5, P50, P95, P99)
- [ ] Add hours_in_state calculation
- [ ] Add sample_count and coverage
- [ ] Calculate abnormal%, event_count, longest_event
- [ ] Write to `aggregates/weekly/` with partitioning
- [ ] Handle ISO week number correctly
- [ ] Test aggregation on sample data
- [ ] Verify aggregates for known units

**Day 17: Trend Analysis - Regression Logic**
- [ ] Implement TrendAnalysis class
- [ ] Load weekly aggregates for lookback windows
- [ ] Fit linear regression (scipy.stats.linregress)
- [ ] Calculate slope, intercept, R², p-value
- [ ] Implement robust regression (Theil-Sen)
- [ ] Calculate recent vs. baseline delta
- [ ] Test statistical significance (p < 0.05)
- [ ] Classify trend direction
- [ ] Handle <4 weeks data gracefully
- [ ] Write regression logic unit tests

**Day 18: Trend Analysis - Scoring & Output**
- [ ] Implement trend risk score formula
- [ ] Map magnitude, persistence, significance to score
- [ ] Calculate confidence (valid weeks, R², p-value)
- [ ] Build trend evidence dictionary
- [ ] Write results to `technique_results/trend_analysis/`
- [ ] Partition by year/week
- [ ] Write unit tests for normalization
- [ ] Test on sample degrading units
- [ ] Validate score reasonableness

**Day 19: Trend Analysis - Integration & Testing**
- [ ] Create Prefect task for trend analysis
- [ ] Add dependency on weekly aggregation
- [ ] Schedule weekly execution (Sunday 04:00)
- [ ] Test execution on full fleet
- [ ] Review trend results for all units
- [ ] Identify top 10 degrading units
- [ ] Compare trends to known maintenance events
- [ ] Document common trend patterns

**Day 20: Score Normalization & QA**
- [ ] Review all technique result distributions
- [ ] Validate score bands (0-30, 30-60, 60-80, 80-100)
- [ ] Check confidence score distributions
- [ ] Add normalization version to all outputs
- [ ] Document normalization formulas per technique
- [ ] Create example results for each technique
- [ ] Generate sample explanations
- [ ] Plot score histograms
- [ ] Run end-to-end pipeline test (Silver → results)
- [ ] Create Phase 2 summary report

---

## 📦 Deliverables

### Critical Deliverables (Must-Have)

1. **Threshold Deviation Technique**
   - Daily analysis operational
   - Weekly summary operational
   - Results stored with proper partitioning
   - Unit tests passing

2. **Event Detection Technique**
   - Events detected and stored
   - Integrated with threshold results
   - Event statistics computed
   - Unit tests passing

3. **Trend Analysis Technique**
   - 4-week and 8-week trends calculated
   - Statistical significance tested
   - Results stored with proper partitioning
   - Unit tests passing

4. **Weekly Aggregates**
   - Generated for all units
   - Stored with proper partitioning
   - Used by trend analysis

### Important Deliverables (Should-Have)

5. **Prefect Integration**
   - All 3 techniques scheduled
   - Dependencies configured correctly
   - Executions logged properly

6. **Score Normalization**
   - All scores in 0-100 range
   - Confidence scores calculated
   - Evidence dictionaries complete

7. **Documentation**
   - Normalization guide complete
   - Example results generated
   - Technique comparison documented

### Nice-to-Have Deliverables

8. **Quality Assurance Artifacts**
   - Score distribution plots
   - Technique performance comparison
   - Known event validation (if data available)

---

## 🎯 Success Criteria

### Functional Success Criteria

| Criterion | Target | Validation Method |
|-----------|--------|-------------------|
| Threshold execution reliability | 100% daily success | Check Prefect logs |
| Event detection rate | ≥1 event per abnormal unit | Query events table |
| Trend detection rate | ≥10% of units show trends | Query trend results |
| Score reasonableness | Manual review passes | Expert review |

### Technical Success Criteria

| Criterion | Target | Validation Method |
|-----------|--------|-------------------|
| Unit test coverage | ≥70% for techniques | pytest-cov |
| Execution time (daily) | <15 min for threshold + event | Time Prefect tasks |
| Execution time (weekly) | <30 min for aggregation + trend | Time Prefect tasks |
| Output schema compliance | 100% | Automated validation |

### Data Quality Success Criteria

| Criterion | Target | Validation Method |
|-----------|--------|-------------------|
| Technique coverage | ≥90% of units evaluated | Count results vs. units |
| Confidence > 50 | ≥80% of results | Query confidence scores |
| InsufficientData rate | <20% of results | Query status field |

### Exit Gates (Must Pass to Proceed to Phase 3)

**Gate 1: Technique Execution**
- [ ] Threshold deviation runs daily without errors
- [ ] Event detection runs daily without errors
- [ ] Weekly aggregation runs weekly without errors
- [ ] Trend analysis runs weekly without errors

**Gate 2: Result Quality**
- [ ] All techniques produce valid TechniqueResults
- [ ] Risk scores are in 0-100 range
- [ ] Confidence scores are in 0-100 range
- [ ] Evidence dictionaries are complete

**Gate 3: Explainability**
- [ ] Can trace any score back to source data
- [ ] Evidence includes all required fields
- [ ] Status classification is consistent
- [ ] Manual review confirms results make sense

**Gate 4: Integration Readiness**
- [ ] Results stored in correct partition structure
- [ ] Schema versioning implemented
- [ ] Ready for Phase 3 aggregation to consume

---

## 📝 Implementation Notes

### Week 3 Notes

**Day 11 (Threshold Daily):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Blockers/Issues:
- 

Baseline Matching Results:
- State matches: _____%
- Fallback used: _____%

Performance:
- Processing time per unit: _____
- Memory usage: _____

Next Steps:
- 
```

**Day 12 (Threshold Scoring):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Score Distribution:
- Normal (0-40): _____%
- Alerta (40-70): _____%
- Anormal (70-100): _____%

Sample Results:
Unit | Signal | Score | Status | Confidence
_____|________|_______|________|___________


Next Steps:
- 
```

**Day 13 (Threshold Weekly):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Fleet Execution Results:
- Units processed: _____
- Total results: _____
- Errors: _____

Top Abnormal Findings:
1. Unit _____ - Signal _____ - Score _____
2. Unit _____ - Signal _____ - Score _____
3. Unit _____ - Signal _____ - Score _____

Next Steps:
- 
```

**Day 14 (Event Grouping):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Event Statistics:
- Total events detected: _____
- Spikes (<5min): _____
- Episodes (5-60min): _____
- Sustained (>60min): _____

Longest Event:
- Unit: _____
- Signal: _____
- Duration: _____

Next Steps:
- 
```

**Day 15 (Event Integration):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Fleet Event Statistics:
- Units with events: _____%
- Events per unit (avg): _____
- Most common signals: _____

Severity Distribution:
- Low: _____%
- Medium: _____%
- High: _____%

Next Steps:
- 
```

### Week 4 Notes

**Day 16 (Weekly Aggregation):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Aggregation Statistics:
- Weeks processed: _____
- Units processed: _____
- Signals aggregated: _____

Coverage:
- Units with ≥4 weeks: _____%
- Units with ≥8 weeks: _____%

Next Steps:
- 
```

**Day 17 (Trend Regression):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Regression Statistics:
- Trends calculated (4w): _____
- Trends calculated (8w): _____
- Significant trends (p<0.05): _____%

Sample Degrading Trends:
Unit | Signal | Slope | R² | p-value
_____|________|_______|____|________


Next Steps:
- 
```

**Day 18 (Trend Scoring):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Trend Score Distribution:
- Normal (0-40): _____%
- Alerta (40-70): _____%
- Anormal (70-100): _____%

Confidence Distribution:
- High (>75): _____%
- Medium (50-75): _____%
- Low (<50): _____%

Next Steps:
- 
```

**Day 19 (Trend Integration):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Top 10 Degrading Units:
1. Unit _____ - System _____ - Score _____
2. Unit _____ - System _____ - Score _____
(...)

Known Event Validation:
- Events with prior trend: _____
- False positives: _____

Next Steps:
- 
```

**Day 20 (Normalization QA):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Score Validation:
- Scores out of range: _____
- Confidence issues: _____
- Evidence incomplete: _____

End-to-End Test Results:
- Pipeline success: Yes/No
- Performance acceptable: Yes/No
- Results explainable: Yes/No

Example Explanations Generated:
1. _____
2. _____
3. _____

Next Steps:
- 
```

---

### Phase 2 Retrospective

**To be completed at end of Phase 2:**

```
Date Completed: ___________
Team: ___________

What Went Well:
- 
- 

What Didn't Go Well:
- 
- 

Technique Performance:
- Threshold: _____
- Events: _____
- Trends: _____

False Positive Concerns:
- Threshold: _____
- Trends: _____

Key Learnings:
- 
- 

Recommendations for Phase 3:
- 
- 

Readiness for Phase 3:
- Techniques reliable: Ready / Needs Work
- Results explainable: Ready / Needs Work
- Coverage sufficient: Ready / Needs Work
```

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-05-24 | Senior Data Scientist | Initial Phase 2 implementation guide |

---

**Related Documents**
- [Implementation Plan (Main)](implementation_plan.md)
- [Phase 1 Guide](implementation_phase_1.md)
- [Phase 3 Guide](implementation_phase_3.md)
