# Phase 5: Optional Enhancements — Implementation Guide

**Duration**: Week 8+ (flexible, 2-10 days)  
**Objective**: Implement advanced techniques based on Phase 4 validation results  
**Status**: Not Started  
**Last Updated**: May 24, 2026  
**Prerequisites**: Phase 4 completed (validation report approved, thresholds calibrated)

---

## 📋 Table of Contents

1. [Phase Overview](#phase-overview)
2. [Enhancement Options](#enhancement-options)
3. [Option A: Peer Deviation Analysis](#option-a-peer-deviation-analysis)
4. [Option B: AutoEncoder Anomaly Detection](#option-b-autoencoder-anomaly-detection)
5. [Option C: Advanced Diagnostic Rules](#option-c-advanced-diagnostic-rules)
6. [Option D: Change-Point Detection](#option-d-change-point-detection)
7. [Task Checklist](#task-checklist)
8. [Deliverables](#deliverables)
9. [Success Criteria](#success-criteria)
10. [Implementation Notes](#implementation-notes)

---

## 🎯 Phase Overview

### Purpose

Phase 5 is **optional and selective**. Based on Phase 4 validation results, implement 1-2 advanced techniques that address specific gaps or opportunities:

**Enhancement Options**:
1. **Peer Deviation Analysis** — Compare unit against fleet to detect relative underperformance
2. **AutoEncoder Anomaly Detection** — Multivariate black-box technique for complex patterns
3. **Advanced Diagnostic Rules** — Add sophisticated multi-signal rules (10-15 rules total)
4. **Change-Point Detection** — Identify sudden regime shifts in signal behavior

### Why This Phase Is Optional

**Only pursue enhancements if**:
- Phase 4 validation shows specific gaps (e.g., missed a failure type)
- Business requests specific capability (e.g., peer comparison)
- Time and resources available (POC constraints met)

**Do NOT pursue if**:
- Phase 4 performance is sufficient (detection ≥80%, FP ≤20%, advance warning ≥3d)
- Timeline or budget constraints exist
- Core techniques (Phase 2) already meet business needs

### Key Principle

**Incremental value only.** Each enhancement must provide measurable improvement over Phase 2-3 techniques. Avoid complexity for complexity's sake.

---

## 🔄 Enhancement Options

### Selection Guidance

Review Phase 4 validation report and select **1-2 enhancements** based on:

| Gap/Opportunity | Recommended Enhancement | Estimated Effort |
|-----------------|------------------------|------------------|
| Missed failures due to "slow drift" | Peer Deviation | 2-3 days |
| Missed failures with multivariate patterns | AutoEncoder | 4-5 days |
| Need more explainable complex rules | Advanced Diagnostic Rules | 2-3 days |
| Missed failures with sudden regime shifts | Change-Point Detection | 3-4 days |
| Detection rate ≥80%, FP ≤20% | None — go to production | 0 days |

**Recommendation**: Start with **Peer Deviation** (explainable, fast) OR **Advanced Diagnostic Rules** (explainable, domain-driven). Use AutoEncoder only if explainable techniques fail.

---

## 🔹 Option A: Peer Deviation Analysis

**Duration**: 2-3 days  
**Complexity**: Medium  
**Explainability**: High  
**Use Case**: Detect units underperforming relative to fleet

### Timeline

#### Day 37-38: Peer Deviation Implementation

**Day 37 Morning** (4 hours):
- Implement PeerDeviation technique class
- Load weekly aggregates for fleet (all units with same model)
- Calculate fleet statistics per signal (P25, P50, P75, mean, std)
- Exclude outliers (remove top/bottom 5% from fleet stats)

**Day 37 Afternoon** (4 hours):
- Compare unit against fleet percentiles
- Calculate z-score (distance from fleet mean in standard deviations)
- Calculate percentile rank (where does unit sit in fleet?)
- Apply risk score normalization (z-score > 2 = high risk)

**Day 38 Morning** (4 hours):
- Build evidence dictionary (fleet percentile, z-score, rank)
- Write results to `technique_results/peer_deviation/`
- Integrate with Prefect flow (weekly, 08:00 Sunday)
- Test on full fleet

**Day 38 Afternoon** (4 hours):
- Validate peer comparison accuracy (manual review)
- Identify units flagged by peer but not by other techniques
- Measure incremental detection value
- Document peer deviation patterns observed

### Deliverables
- `src/techniques/peer_deviation.py`
- Peer deviation results in `technique_results/peer_deviation/`
- Validation analysis: did peer deviation catch missed failures?

### Success Criteria
- Peer comparison runs successfully for all units
- Identifies ≥5% of units as outliers (relative underperformers)
- Catches ≥1 failure missed by other techniques (if applicable)

---

## 🔹 Option B: AutoEncoder Anomaly Detection

**Duration**: 4-5 days  
**Complexity**: High  
**Explainability**: Low  
**Use Case**: Detect complex multivariate patterns (when explainable techniques fail)

### Timeline

#### Day 37-41: AutoEncoder Implementation

**Day 37 Morning** (4 hours):
- Design AutoEncoder architecture (input: 10-15 signals, latent: 4-6 dims)
- Select Engine system signals for pilot (EngCoolTemp, EngOilPres, EngSpd, etc.)
- Prepare training data (6-hour windows from healthy units)
- Split train/validation (80/20)

**Day 37 Afternoon** (4 hours):
- Implement AutoEncoder model (TensorFlow/Keras or PyTorch)
- Add input normalization (min-max or z-score)
- Define reconstruction loss (MSE)
- Train on healthy baseline data

**Day 38 Morning** (4 hours):
- Validate model performance (reconstruction error on validation set)
- Define anomaly threshold (e.g., P95 of reconstruction errors)
- Test on sample normal and abnormal windows
- Tune threshold for optimal detection

**Day 38 Afternoon** (4 hours):
- Implement AutoEncoderAnomaly technique class
- Load 6-hour windows from Silver data
- Run inference (calculate reconstruction error)
- Apply threshold and generate risk score

**Day 39 Morning** (4 hours):
- Build evidence dictionary (reconstruction error, signals contributing most)
- Write results to `technique_results/autoencoder/`
- Integrate with Prefect flow (every 6 hours)
- Test on sample units

**Day 39 Afternoon** (4 hours):
- Run backtest on known Engine failures
- Measure detection rate and advance warning
- Compare against Phase 2 techniques
- Identify multivariate patterns detected

**Day 40-41: Explainability & Validation** (2 days):
- Implement SHAP or attention mechanism for signal importance
- Generate partial explanations ("High reconstruction error driven by EngCoolTemp")
- Validate on full fleet (check for excessive false positives)
- Document AutoEncoder performance and limitations

### Deliverables
- `src/techniques/autoencoder.py`
- Trained AutoEncoder model weights
- AutoEncoder results in `technique_results/autoencoder/`
- Backtest validation report
- Explainability analysis (SHAP values)

### Success Criteria
- Model trains successfully on healthy data
- Anomaly detection runs every 6 hours without errors
- Catches ≥2 failures missed by other techniques
- False positive rate ≤30% (acceptable for black-box technique)
- Partial explainability provided (top contributing signals)

---

## 🔹 Option C: Advanced Diagnostic Rules

**Duration**: 2-3 days  
**Complexity**: Medium  
**Explainability**: High  
**Use Case**: Capture sophisticated mechanical patterns with domain knowledge

### Timeline

#### Day 37-39: Advanced Rules Implementation

**Day 37 Morning** (4 hours):
- Review Phase 3 diagnostic rules (5-8 basic rules)
- Brainstorm with domain expert: what patterns are we missing?
- Design 5-8 advanced rules:
  - Engine Pre-Failure Pattern: Coolant temp rising + Oil pres dropping + Speed stable
  - Transmission Overload: TrnLubeTemp > P95 + High speed + Heavy load (if available)
  - Brake Imbalance: Left brake temps >> Right brake temps (asymmetry)
  - Cooling System Failure: Coolant temp rising + Aftercooler temps rising
  - Hydraulic Cavitation: Oil pres low + Oil temp low (cold oil = high viscosity)

**Day 37 Afternoon** (4 hours):
- Add advanced rules to diagnostic_rules.yaml
- Document rule logic and thresholds
- Define severity and confidence per rule
- Add rule metadata (expected advance warning, failure type)

**Day 38 Morning** (4 hours):
- Implement advanced rules in DiagnosticRulesEngine
- Add multi-step logic (e.g., "if A rising AND B dropping over 3 days")
- Add temporal conditions (e.g., "persistent for 2+ days")
- Test rules on synthetic data

**Day 38 Afternoon** (4 hours):
- Run backtest on known failures (did advanced rules detect them?)
- Measure incremental detection value
- Tune thresholds for optimal performance
- Document rule firing patterns

**Day 39: Validation & Integration** (1 day):
- Integrate advanced rules with Prefect flow
- Test on full fleet (check for false positives)
- Compare against basic rules (which rules fire most often?)
- Generate rule performance report

### Deliverables
- Updated `diagnostic_rules.yaml` with 10-15 total rules
- Updated `src/techniques/diagnostic_rules.py`
- Backtest validation report for advanced rules
- Rule performance comparison (basic vs. advanced)

### Success Criteria
- 10-15 total rules implemented and tested
- Advanced rules catch ≥2 failures missed by basic rules
- False positive rate for advanced rules ≤20%
- Rules are explainable and actionable

---

## 🔹 Option D: Change-Point Detection

**Duration**: 3-4 days  
**Complexity**: Medium-High  
**Explainability**: Medium  
**Use Case**: Detect sudden regime shifts (e.g., abrupt temperature increase after maintenance)

### Timeline

#### Day 37-40: Change-Point Detection Implementation

**Day 37 Morning** (4 hours):
- Research change-point detection algorithms (CUSUM, PELT, Bayesian)
- Select algorithm (recommendation: PELT from ruptures library)
- Design detection strategy (per signal, per unit, weekly cadence)
- Define minimum segment length (e.g., 7 days)

**Day 37 Afternoon** (4 hours):
- Implement ChangePointDetection technique class
- Load weekly aggregates (mean per week per signal)
- Run PELT algorithm to detect change-points
- Identify significant regime shifts (mean change > 15%)

**Day 38 Morning** (4 hours):
- Calculate risk score (magnitude of shift + persistence)
- Build evidence dictionary (before/after means, change-point date)
- Write results to `technique_results/change_point/`
- Test on sample signals with known regime shifts

**Day 38 Afternoon** (4 hours):
- Integrate with Prefect flow (weekly, 09:00 Sunday)
- Test on full fleet
- Review detected change-points (validate with maintenance records)
- Identify false positives (benign shifts, e.g., seasonal changes)

**Day 39-40: Validation & Tuning** (2 days):
- Run backtest on known failures (did regime shifts precede failures?)
- Measure advance warning provided by change-points
- Tune minimum segment length and significance threshold
- Document change-point patterns (maintenance events, failure precursors)
- Generate validation report

### Deliverables
- `src/techniques/change_point_detection.py`
- Change-point results in `technique_results/change_point/`
- Backtest validation report
- Pattern analysis (maintenance vs. failure change-points)

### Success Criteria
- Change-point detection runs weekly without errors
- Detects ≥10 significant regime shifts per client per month
- Catches ≥1 failure missed by other techniques
- False positive rate ≤40% (acceptable for exploratory technique)

---

## ✅ Task Checklist

### Option A: Peer Deviation (2-3 days)

**Day 37: Implementation**
- [ ] Implement PeerDeviation class
- [ ] Load weekly aggregates for fleet
- [ ] Calculate fleet statistics (P25, P50, P75, mean, std)
- [ ] Exclude outliers from fleet stats
- [ ] Compare unit against fleet percentiles
- [ ] Calculate z-score and percentile rank
- [ ] Apply risk score normalization
- [ ] Write unit tests

**Day 38: Integration & Validation**
- [ ] Build evidence dictionary
- [ ] Write results to `peer_deviation/` partition
- [ ] Integrate with Prefect flow (weekly)
- [ ] Test on full fleet
- [ ] Validate peer comparison accuracy
- [ ] Identify units flagged by peer only
- [ ] Measure incremental detection value
- [ ] Document peer deviation patterns

### Option B: AutoEncoder (4-5 days)

**Day 37: Model Design & Training**
- [ ] Design AutoEncoder architecture
- [ ] Select Engine system signals (10-15)
- [ ] Prepare training data (healthy units)
- [ ] Split train/validation (80/20)
- [ ] Implement AutoEncoder model
- [ ] Add input normalization
- [ ] Train on healthy baseline data

**Day 38: Anomaly Detection**
- [ ] Validate model performance
- [ ] Define anomaly threshold (P95 reconstruction error)
- [ ] Test on normal and abnormal windows
- [ ] Tune threshold
- [ ] Implement AutoEncoderAnomaly class
- [ ] Load 6-hour windows and run inference
- [ ] Apply threshold and generate risk score

**Day 39: Integration & Testing**
- [ ] Build evidence dictionary
- [ ] Write results to `autoencoder/` partition
- [ ] Integrate with Prefect flow (every 6 hours)
- [ ] Test on sample units
- [ ] Run backtest on Engine failures
- [ ] Measure detection rate and advance warning
- [ ] Compare against Phase 2 techniques
- [ ] Identify multivariate patterns detected

**Day 40-41: Explainability**
- [ ] Implement SHAP or attention mechanism
- [ ] Generate signal importance scores
- [ ] Create partial explanations
- [ ] Validate on full fleet
- [ ] Check false positive rate
- [ ] Document AutoEncoder performance
- [ ] Document limitations and use cases

### Option C: Advanced Diagnostic Rules (2-3 days)

**Day 37: Rule Design**
- [ ] Review existing basic rules
- [ ] Brainstorm with domain expert
- [ ] Design 5-8 advanced rules
- [ ] Add rules to diagnostic_rules.yaml
- [ ] Document rule logic and thresholds
- [ ] Define severity and confidence per rule
- [ ] Add rule metadata

**Day 38: Implementation & Testing**
- [ ] Implement advanced rules in engine
- [ ] Add multi-step and temporal logic
- [ ] Test rules on synthetic data
- [ ] Run backtest on known failures
- [ ] Measure incremental detection value
- [ ] Tune thresholds
- [ ] Document rule firing patterns

**Day 39: Integration**
- [ ] Integrate with Prefect flow
- [ ] Test on full fleet
- [ ] Check false positive rate
- [ ] Compare basic vs. advanced rules
- [ ] Generate rule performance report

### Option D: Change-Point Detection (3-4 days)

**Day 37: Algorithm Selection & Implementation**
- [ ] Research change-point algorithms
- [ ] Select algorithm (PELT)
- [ ] Design detection strategy
- [ ] Implement ChangePointDetection class
- [ ] Load weekly aggregates
- [ ] Run PELT algorithm
- [ ] Identify significant regime shifts

**Day 38: Integration & Testing**
- [ ] Calculate risk score
- [ ] Build evidence dictionary
- [ ] Write results to `change_point/` partition
- [ ] Test on signals with known shifts
- [ ] Integrate with Prefect flow (weekly)
- [ ] Test on full fleet
- [ ] Review detected change-points
- [ ] Identify false positives

**Day 39-40: Validation**
- [ ] Run backtest on known failures
- [ ] Measure advance warning
- [ ] Tune minimum segment length
- [ ] Tune significance threshold
- [ ] Document change-point patterns
- [ ] Distinguish maintenance vs. failure shifts
- [ ] Generate validation report

---

## 📦 Deliverables

### Option A: Peer Deviation

- **Code**: `src/techniques/peer_deviation.py`
- **Data**: Peer deviation results (partitioned Parquet)
- **Documentation**: Peer comparison methodology, validation analysis

### Option B: AutoEncoder

- **Code**: `src/techniques/autoencoder.py`, trained model weights
- **Data**: AutoEncoder results (partitioned Parquet)
- **Documentation**: Model architecture, training process, explainability analysis, validation report

### Option C: Advanced Diagnostic Rules

- **Code**: Updated `src/techniques/diagnostic_rules.py`
- **Configuration**: Updated `diagnostic_rules.yaml` with 10-15 rules
- **Documentation**: Rule definitions, backtest validation, rule performance comparison

### Option D: Change-Point Detection

- **Code**: `src/techniques/change_point_detection.py`
- **Data**: Change-point results (partitioned Parquet)
- **Documentation**: Algorithm selection rationale, pattern analysis, validation report

---

## 🎯 Success Criteria

### Incremental Value Criteria

| Criterion | Target | Validation Method |
|-----------|--------|-------------------|
| Incremental detection | Catch ≥1 failure missed by Phase 2-3 | Backtest |
| False positive impact | FP rate increase ≤10% vs. baseline | FP analysis |
| Execution reliability | 100% success rate for new technique | Prefect logs |
| Integration | Seamlessly integrated with existing flows | End-to-end test |

### Technique-Specific Criteria

**Peer Deviation**:
- Identifies ≥5% of units as relative outliers
- Z-scores are statistically valid (fleet stats correct)
- Explanations reference fleet percentiles clearly

**AutoEncoder**:
- Reconstruction error threshold is well-calibrated
- Catches ≥2 multivariate failures missed by other techniques
- Partial explainability provided (top contributing signals)

**Advanced Diagnostic Rules**:
- 10-15 total rules implemented
- Advanced rules fire appropriately (not too often, not never)
- Catches ≥2 failures with complex multi-signal patterns

**Change-Point Detection**:
- Detects ≥10 significant regime shifts per client per month
- Distinguishes maintenance events from failure precursors
- Advance warning ≥5 days for failure-related shifts

---

## 📝 Implementation Notes

### Enhancement Selection Decision

```
Date: ___________
Team: ___________

Phase 4 Validation Results Summary:
- Detection rate: _____%
- Advance warning: _____ days
- False positive rate: _____%

Gaps Identified:
1. _____
2. _____

Enhancements Selected:
1. _____ (rationale: _____)
2. _____ (rationale: _____)

Enhancements Rejected:
- _____ (reason: _____)
- _____ (reason: _____)

Estimated Effort: _____ days
Target Completion: _____
```

### Option A: Peer Deviation Notes

**Day 37-38:**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Fleet Statistics (Sample):
Signal | P25 | P50 | P75 | Mean | Std
_______|_____|_____|_____|______|____


Units Flagged as Outliers:
Unit | Signal | Z-Score | Percentile Rank
_____|________|_________|________________


Incremental Value:
- Failures detected by peer only: _____
- False positives introduced: _____

Next Steps:
- 
```

### Option B: AutoEncoder Notes

**Day 37-41:**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Model Architecture:
- Input signals: _____
- Latent dimensions: _____
- Layers: _____
- Activation: _____

Training Performance:
- Training loss: _____
- Validation loss: _____
- Anomaly threshold (P95): _____

Backtest Results:
- Failures detected: _____ / _____
- Advance warning (avg): _____ days
- False positives: _____%

Multivariate Patterns Discovered:
1. _____
2. _____

Explainability:
- SHAP analysis: Completed / Pending
- Top contributing signals: _____

Next Steps:
- 
```

### Option C: Advanced Rules Notes

**Day 37-39:**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Advanced Rules Added:
1. _____ (severity: _____)
2. _____ (severity: _____)
3. _____ (severity: _____)
(...)

Backtest Results:
Rule | Failures Detected | Advance Warning | FP Rate
_____|___________________|_________________|________


Rule Firing Frequency:
- Most common: _____
- Least common: _____

Incremental Value:
- Failures detected by advanced rules only: _____

Next Steps:
- 
```

### Option D: Change-Point Notes

**Day 37-40:**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Algorithm Selected: _____
Parameters:
- Minimum segment length: _____
- Significance threshold: _____

Change-Points Detected:
- Total: _____
- Per unit (avg): _____
- Per signal (avg): _____

Pattern Analysis:
- Maintenance-related shifts: _____
- Failure-related shifts: _____
- Unknown shifts: _____

Backtest Results:
- Failures preceded by change-point: _____ / _____
- Advance warning (avg): _____ days

False Positive Rate: _____%

Next Steps:
- 
```

---

### Phase 5 Retrospective

**To be completed at end of Phase 5:**

```
Date Completed: ___________
Team: ___________

Enhancements Implemented:
1. _____
2. _____

What Went Well:
- 
- 

What Didn't Go Well:
- 
- 

Performance Impact:
- Detection rate improvement: _____%
- Advance warning improvement: _____ days
- False positive impact: _____%

Incremental Value Assessment:
- Worth the effort: Yes / No
- Recommendation: Keep / Disable / Tune further

Key Learnings:
- 
- 

Technique Preferences:
- Most valuable: _____
- Least valuable: _____
- Surprising finding: _____

Production Readiness:
- New techniques reliable: Yes / No
- Integration successful: Yes / No
- Documentation complete: Yes / No

Final Recommendation:
- Go to production: Yes / No
- Further iteration needed: Yes / No
- Enhancements to keep: _____
- Enhancements to disable: _____
```

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-05-24 | Senior Data Scientist | Initial Phase 5 implementation guide |

---

**Related Documents**
- [Implementation Plan (Main)](implementation_plan.md)
- [Phase 4 Guide](implementation_phase_4.md)
- [Validation Report](validation_report.md) (Phase 4 output)
