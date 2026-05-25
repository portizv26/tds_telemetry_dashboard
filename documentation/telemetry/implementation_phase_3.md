# Phase 3: Aggregation & Intelligence — Implementation Guide

**Duration**: Weeks 5-6 (10 working days)  
**Objective**: Build system & unit-level health scores with diagnostic intelligence  
**Status**: Not Started  
**Last Updated**: May 24, 2026  
**Prerequisites**: Phase 2 completed (threshold, event, trend techniques operational)

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

Aggregate signal-level technique results into actionable system and unit-level health assessments:
- **System-Level Aggregation**: Engine, Transmission, Brakes health scores
- **Unit-Level Aggregation**: Overall equipment health with priority rankings
- **Diagnostic Rules**: Multi-signal mechanical failure patterns
- **Explanation Generation**: Human-readable health summaries

### Why This Phase Matters

**Signal-level results are too granular for operators.** By end of Phase 3:
- Operators see: "Engine Health: 72 (Alerta) — High coolant temp + rising oil temp trend"
- Can prioritize: "Top 5 units requiring attention this week"
- Understand: "Why is this unit flagged? What signals are abnormal?"

### Key Principle

**Explain everything.** Every aggregated score must trace back to specific signals, techniques, and evidence.

---

## 📅 Timeline

### Week 5: System Aggregation & Diagnostic Rules

#### Day 21: System-Level Aggregation Framework

**Morning** (4 hours):
- Implement SystemHealth dataclass
- Create SystemAggregator class skeleton
- Define system criticality weights (Engine=3.0, Transmission=2.5, Brakes=2.0, etc.)
- Load signal-to-system mappings from signal registry

**Afternoon** (4 hours):
- Implement time-aware weighting (exponential decay)
- Calculate technique diversity bonus (3+ techniques = +10%)
- Add persistence bonus (abnormal for 3+ consecutive evaluations = +15%)
- Write unit tests for weighting logic

**Output**: `src/aggregation/system_aggregator.py` (partial)

---

#### Day 22: System Aggregation - Risk Score Calculation

**Morning** (4 hours):
- Load all technique results for evaluation window
- Filter by system (get all signals for Engine, Transmission, etc.)
- Apply signal criticality weights
- Calculate weighted mean risk score per system

**Afternoon** (4 hours):
- Implement confidence aggregation (weighted harmonic mean)
- Add status classification (Normal/Alerta/Anormal)
- Identify top 3 contributing signals per system
- Build system evidence dictionary

**Output**: `src/aggregation/system_aggregator.py` (continued)

---

#### Day 23: System Aggregation - Storage & Testing

**Morning** (4 hours):
- Write SystemHealth to `system_health/` partition (year/week/client)
- Add schema versioning
- Implement historical tracking (week-over-week trends)
- Calculate system health delta (current vs. previous week)

**Afternoon** (4 hours):
- Write unit tests for system aggregation
- Test on sample units (all 6 systems)
- Validate score reasonableness
- Review top contributing signals

**Output**: `src/aggregation/system_aggregator.py` (complete)

---

#### Day 24: Diagnostic Rules - Configuration

**Morning** (4 hours):
- Create diagnostic_rules.yaml structure
- Define 5-8 multi-signal failure patterns:
  - Engine Overheating: EngCoolTemp + TCOutTemp elevated
  - Transmission Stress: TrnLubeTemp high + TrnOilPres low
  - Brake Degradation: Multiple brake temps elevated + trend
  - Differential Warning: DiffTemp + DiffLubePres + speed correlation
  - Hydraulic Leak: StrgOilPres drop + StrgOilTemp rise

**Afternoon** (4 hours):
- Document rule logic and thresholds
- Add rule metadata (severity, confidence, systems affected)
- Define rule evaluation cadence (daily/weekly)
- Write rule validation tests

**Output**: `data/telemetry/config/diagnostic_rules.yaml`

---

#### Day 25: Diagnostic Rules - Engine Implementation

**Morning** (4 hours):
- Implement DiagnosticRulesEngine class
- Load and validate diagnostic_rules.yaml
- Create rule evaluation framework
- Implement rule matching logic

**Afternoon** (4 hours):
- Implement first 3 diagnostic rules
- Test rules on synthetic data (known patterns)
- Add rule firing history tracking
- Generate rule-based TechniqueResults

**Output**: `src/techniques/diagnostic_rules.py` (partial)

---

### Week 6: Unit Aggregation & Explanations

#### Day 26: Diagnostic Rules - Complete Implementation

**Morning** (4 hours):
- Implement remaining 3-5 diagnostic rules
- Add rule prioritization (severity-based)
- Test on historical known failures
- Tune rule thresholds

**Afternoon** (4 hours):
- Integrate with Prefect flow (daily + weekly schedules)
- Schedule rule execution (03:00 daily)
- Test on full fleet
- Review rule firing statistics

**Output**: `src/techniques/diagnostic_rules.py` (complete)

---

#### Day 27: Unit-Level Aggregation Framework

**Morning** (4 hours):
- Implement UnitHealth dataclass
- Create UnitAggregator class
- Load all system health scores for unit
- Calculate weighted mean unit health score

**Afternoon** (4 hours):
- Implement multi-system impact bonus (3+ systems abnormal = +20%)
- Add critical system penalty (Engine abnormal = 1.5x weight)
- Calculate overall confidence (from system confidences)
- Identify top contributing systems

**Output**: `src/aggregation/unit_aggregator.py` (partial)

---

#### Day 28: Unit-Level Aggregation - Priority Scoring

**Morning** (4 hours):
- Implement priority score calculation
- Factors: health score + recent degradation + critical system flags + diagnostic rules
- Calculate maintenance urgency (immediate/this week/this month/monitor)
- Add fleet ranking (percentile within client fleet)

**Afternoon** (4 hours):
- Build unit evidence dictionary
- Track week-over-week health delta
- Identify degradation velocity (health dropping >10 points/week)
- Write unit tests for priority logic

**Output**: `src/aggregation/unit_aggregator.py` (continued)

---

#### Day 29: Unit Aggregation - Storage & Integration

**Morning** (4 hours):
- Write UnitHealth to `unit_health/` partition (year/week/client)
- Add schema versioning
- Store top 10 priority units per client
- Calculate fleet statistics (mean health, abnormal%, etc.)

**Afternoon** (4 hours):
- Integrate with Prefect flow (depends on system aggregation)
- Schedule weekly execution (Sunday 06:00)
- Test on full fleet
- Generate priority rankings

**Output**: `src/aggregation/unit_aggregator.py` (complete)

---

#### Day 30: Explanation Generation

**Morning** (4 hours):
- Implement ExplanationGenerator class
- Create natural language templates for each status
- Generate signal-level explanations (with values and deviations)
- Generate system-level explanations (with top contributors)

**Afternoon** (4 hours):
- Generate unit-level explanations (with affected systems)
- Add diagnostic rule explanations (pattern descriptions)
- Test explanation readability with domain expert
- Refine templates based on feedback

**Output**: `src/aggregation/explanation_generator.py`, `data/telemetry/config/explanation_templates.yaml`

---

## 📥 Inputs

### Data Inputs

| Input | Location | Format | Created By | Notes |
|-------|----------|--------|------------|-------|
| Technique results | `technique_results/*/` | Parquet | Phase 2 | Threshold, event, trend |
| Signal registry | `config/signal_registry_v1.yaml` | YAML | Phase 1 | Signal-to-system mappings |
| Technique config | `config/technique_config.yaml` | YAML | Phase 1 | Validity periods |

### Configuration Inputs

| Parameter | Source | Default | Notes |
|-----------|--------|---------|-------|
| System criticality weights | Implementation | Engine=3.0, Transmission=2.5, etc. | Adjustable |
| Time decay factor | Configuration | λ=0.3 | Exponential decay |
| Technique diversity bonus | Configuration | +10% | 3+ techniques |
| Persistence bonus | Configuration | +15% | 3+ consecutive abnormal |
| Multi-system penalty | Configuration | +20% | 3+ systems affected |

---

## 📤 Outputs

### Code Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| SystemAggregator | `src/aggregation/system_aggregator.py` | System-level health scores |
| UnitAggregator | `src/aggregation/unit_aggregator.py` | Unit-level health + priority |
| DiagnosticRulesEngine | `src/techniques/diagnostic_rules.py` | Multi-signal pattern detection |
| ExplanationGenerator | `src/aggregation/explanation_generator.py` | Natural language summaries |
| SystemHealth model | `src/models/system_health.py` | System health dataclass |
| UnitHealth model | `src/models/unit_health.py` | Unit health dataclass |

### Data Artifacts

| Artifact | Location | Format | Cadence | Purpose |
|----------|----------|--------|---------|---------|
| System health | `system_health/year=*/week=*/client=*/` | Parquet | Weekly | System-level scores |
| Unit health | `unit_health/year=*/week=*/client=*/` | Parquet | Weekly | Unit-level scores + priority |
| Diagnostic rule results | `technique_results/diagnostic_rules/` | Parquet | Daily/Weekly | Rule firing records |
| Fleet summary | `fleet_summary/year=*/week=*/client=*/` | Parquet | Weekly | Aggregate fleet statistics |

### Documentation Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| Aggregation methodology | `documentation/aggregation_methodology.md` | Weighting formulas |
| Diagnostic rules guide | `documentation/diagnostic_rules_guide.md` | Rule definitions and tuning |
| Explanation templates | `data/telemetry/config/explanation_templates.yaml` | NL generation templates |

---

## ✅ Task Checklist

### Week 5: System Aggregation & Diagnostic Rules

**Day 21: System Aggregation Framework**
- [ ] Implement SystemHealth dataclass
- [ ] Create SystemAggregator class skeleton
- [ ] Define system criticality weights (6 systems)
- [ ] Load signal-to-system mappings
- [ ] Implement time-aware weighting (exponential decay)
- [ ] Add technique diversity bonus logic
- [ ] Add persistence bonus logic
- [ ] Write unit tests for weighting formulas

**Day 22: System Risk Score Calculation**
- [ ] Load technique results for evaluation window
- [ ] Filter results by system (signal-to-system mapping)
- [ ] Apply signal criticality weights
- [ ] Calculate weighted mean risk score
- [ ] Implement confidence aggregation (harmonic mean)
- [ ] Apply status classification thresholds
- [ ] Identify top 3 contributing signals per system
- [ ] Build system evidence dictionary
- [ ] Test on sample systems

**Day 23: System Storage & Testing**
- [ ] Write SystemHealth to `system_health/` partition
- [ ] Add schema versioning
- [ ] Implement historical tracking (week-over-week)
- [ ] Calculate system health delta
- [ ] Write comprehensive unit tests
- [ ] Test on all 6 systems for sample units
- [ ] Validate score distributions
- [ ] Review top contributing signals for reasonableness

**Day 24: Diagnostic Rules Configuration**
- [ ] Create diagnostic_rules.yaml structure
- [ ] Define Engine Overheating rule
- [ ] Define Transmission Stress rule
- [ ] Define Brake Degradation rule
- [ ] Define Differential Warning rule
- [ ] Define Hydraulic Leak rule
- [ ] Add 2-3 additional rules
- [ ] Document rule logic and thresholds
- [ ] Add rule metadata (severity, confidence, systems)
- [ ] Define evaluation cadence per rule
- [ ] Write rule validation tests

**Day 25: Diagnostic Rules Implementation**
- [ ] Implement DiagnosticRulesEngine class
- [ ] Load and validate diagnostic_rules.yaml
- [ ] Create rule evaluation framework
- [ ] Implement rule matching logic
- [ ] Implement first 3 rules (Engine, Transmission, Brakes)
- [ ] Test rules on synthetic known patterns
- [ ] Add rule firing history tracking
- [ ] Generate TechniqueResults for fired rules
- [ ] Test on sample data

### Week 6: Unit Aggregation & Explanations

**Day 26: Complete Diagnostic Rules**
- [ ] Implement remaining 3-5 diagnostic rules
- [ ] Add rule prioritization (severity-based)
- [ ] Test on historical known failures (if available)
- [ ] Tune rule thresholds based on testing
- [ ] Create Prefect task for diagnostic rules
- [ ] Schedule daily execution (03:00)
- [ ] Schedule weekly execution (Sunday 05:00)
- [ ] Test on full fleet
- [ ] Calculate rule firing statistics
- [ ] Review most common rules fired

**Day 27: Unit Aggregation Framework**
- [ ] Implement UnitHealth dataclass
- [ ] Create UnitAggregator class
- [ ] Load all system health scores for unit
- [ ] Calculate weighted mean unit health score
- [ ] Implement multi-system impact bonus (3+ systems)
- [ ] Add critical system penalty (Engine = 1.5x)
- [ ] Calculate overall confidence
- [ ] Identify top contributing systems (top 3)
- [ ] Write unit tests for unit aggregation

**Day 28: Unit Priority Scoring**
- [ ] Implement priority score calculation
- [ ] Add recent degradation factor (week-over-week delta)
- [ ] Add critical system flags bonus
- [ ] Add diagnostic rule firing bonus
- [ ] Calculate maintenance urgency classification
- [ ] Calculate fleet ranking (percentile)
- [ ] Build unit evidence dictionary
- [ ] Track health velocity (points/week change)
- [ ] Write unit tests for priority logic
- [ ] Test on sample units with various health states

**Day 29: Unit Storage & Integration**
- [ ] Write UnitHealth to `unit_health/` partition
- [ ] Add schema versioning
- [ ] Store top 10 priority units per client
- [ ] Calculate fleet statistics (mean, std, percentiles)
- [ ] Create Prefect task for unit aggregation
- [ ] Add dependency on system aggregation
- [ ] Schedule weekly execution (Sunday 06:00)
- [ ] Test on full fleet
- [ ] Generate priority rankings for all clients
- [ ] Review top priority units

**Day 30: Explanation Generation**
- [ ] Implement ExplanationGenerator class
- [ ] Create NL templates for Normal status
- [ ] Create NL templates for Alerta status
- [ ] Create NL templates for Anormal status
- [ ] Generate signal-level explanations (value + deviation)
- [ ] Generate system-level explanations (top contributors)
- [ ] Generate unit-level explanations (affected systems)
- [ ] Add diagnostic rule explanations (pattern descriptions)
- [ ] Test explanation readability with domain expert
- [ ] Refine templates based on feedback
- [ ] Create explanation_templates.yaml
- [ ] Add explanation generation to aggregation flows

---

## 📦 Deliverables

### Critical Deliverables (Must-Have)

1. **System-Level Health Scores**
   - All 6 systems scored for all units
   - Stored in `system_health/` partition
   - Top contributing signals identified
   - Week-over-week tracking functional

2. **Unit-Level Health Scores**
   - Overall health score for all units
   - Priority rankings generated
   - Maintenance urgency classified
   - Stored in `unit_health/` partition

3. **Diagnostic Rules Engine**
   - 5-8 rules defined and implemented
   - Rules firing correctly on test data
   - Results stored as TechniqueResults
   - Integrated with daily/weekly flows

4. **Explanation Generation**
   - Natural language summaries for all health levels
   - Explanations reference specific signals and values
   - Readable by non-technical operators

### Important Deliverables (Should-Have)

5. **Fleet-Level Statistics**
   - Mean health per client
   - Abnormal unit percentage
   - System-level fleet trends

6. **Priority Rankings**
   - Top 10 units per client
   - Sorted by maintenance urgency
   - Updated weekly

7. **Documentation**
   - Aggregation methodology documented
   - Diagnostic rules guide created
   - Explanation templates documented

### Nice-to-Have Deliverables

8. **Advanced Analytics**
   - Fleet benchmarking
   - Equipment model comparisons
   - System reliability trends

---

## 🎯 Success Criteria

### Functional Success Criteria

| Criterion | Target | Validation Method |
|-----------|--------|-------------------|
| System aggregation coverage | 100% of units | Query system_health table |
| Unit aggregation coverage | 100% of units | Query unit_health table |
| Diagnostic rule firing | ≥2 rules fire per week | Query rule results |
| Explanation completeness | 100% of results have explanations | Manual review |

### Technical Success Criteria

| Criterion | Target | Validation Method |
|-----------|--------|-------------------|
| Unit test coverage | ≥70% for aggregation code | pytest-cov |
| Aggregation execution time | <45 min weekly | Time Prefect tasks |
| Score consistency | No sudden jumps (>30 points) without evidence | Validation query |
| Confidence propagation | Unit confidence ≤ min(system confidences) | Unit tests |

### Data Quality Success Criteria

| Criterion | Target | Validation Method |
|-----------|--------|-------------------|
| Top contributor accuracy | Manual review passes | Expert validation |
| Status classification | Matches signal-level severity | Cross-check query |
| Priority ranking accuracy | Top 10 units have explainable issues | Manual review |

### Exit Gates (Must Pass to Proceed to Phase 4)

**Gate 1: Aggregation Reliability**
- [ ] System aggregation runs weekly without errors
- [ ] Unit aggregation runs weekly without errors
- [ ] All units have system and unit health scores
- [ ] No missing or null scores

**Gate 2: Diagnostic Rules**
- [ ] At least 5 rules defined and tested
- [ ] Rules fire on known patterns
- [ ] False positive rate acceptable (<50% on review)
- [ ] Rule results stored correctly

**Gate 3: Explainability**
- [ ] Every score has a natural language explanation
- [ ] Explanations reference specific signals/systems
- [ ] Domain expert confirms readability
- [ ] Top contributors are correct and relevant

**Gate 4: Priority Ranking**
- [ ] Top 10 units per client have explainable issues
- [ ] Maintenance urgency classifications are reasonable
- [ ] Fleet rankings update correctly week-over-week

---

## 📝 Implementation Notes

### Week 5 Notes

**Day 21 (System Aggregation Framework):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

System Criticality Weights Chosen:
- Engine: _____
- Transmission: _____
- Brakes: _____
- Differential: _____
- Hydraulics: _____
- Electrical: _____

Weighting Formula Decisions:
- Time decay factor (λ): _____
- Diversity bonus: _____
- Persistence bonus: _____

Next Steps:
- 
```

**Day 22 (System Risk Calculation):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Sample System Scores:
Unit | Engine | Transmission | Brakes | Differential
_____|________|______________|________|_____________


Top Contributors Validation:
- Engine: _____
- Transmission: _____
- Brakes: _____

Next Steps:
- 
```

**Day 23 (System Storage):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Fleet System Health Statistics:
- Mean Engine health: _____
- Mean Transmission health: _____
- Mean Brakes health: _____
- Units with abnormal Engine: _____

Week-over-Week Deltas:
- Largest improvement: Unit _____ System _____
- Largest degradation: Unit _____ System _____

Next Steps:
- 
```

**Day 24 (Diagnostic Rules Config):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Rules Defined:
1. _____: _____
2. _____: _____
3. _____: _____
4. _____: _____
5. _____: _____

Thresholds Chosen:
Rule | Threshold | Rationale
_____|___________|__________


Next Steps:
- 
```

**Day 25 (Rules Implementation):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Rules Tested:
Rule | Test Pattern | Fired | Result
_____|______________|_______|_______


Next Steps:
- 
```

### Week 6 Notes

**Day 26 (Complete Rules):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Fleet Rule Statistics:
- Total rules fired: _____
- Most common rule: _____
- Units with rule fires: _____

Rule Firing by Type:
Rule | Count | % of Units
_____|_______|___________


Next Steps:
- 
```

**Day 27 (Unit Aggregation Framework):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Unit Health Distribution:
- Normal (0-40): _____% of fleet
- Alerta (40-70): _____% of fleet
- Anormal (70-100): _____% of fleet

Multi-System Impact Cases:
- Units with 1 system abnormal: _____
- Units with 2 systems abnormal: _____
- Units with 3+ systems abnormal: _____

Next Steps:
- 
```

**Day 28 (Priority Scoring):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Maintenance Urgency Distribution:
- Immediate: _____
- This week: _____
- This month: _____
- Monitor: _____

Top 5 Priority Units:
Rank | Unit | Health | Urgency | Primary Issue
_____|______|________|_________|______________


Next Steps:
- 
```

**Day 29 (Unit Storage):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Fleet Statistics:
- Mean unit health: _____
- Std deviation: _____
- P95 health: _____
- Units requiring attention (>70): _____

Top 10 Priority Units Per Client:
Client | Unit | Score | Urgency
_______|______|_______|________


Next Steps:
- 
```

**Day 30 (Explanation Generation):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 

Sample Explanations Generated:
Normal: _____

Alerta: _____

Anormal: _____

Expert Feedback:
- Clarity: _____
- Actionability: _____
- Improvements needed: _____

Next Steps:
- 
```

---

### Phase 3 Retrospective

**To be completed at end of Phase 3:**

```
Date Completed: ___________
Team: ___________

What Went Well:
- 
- 

What Didn't Go Well:
- 
- 

Aggregation Accuracy:
- System scores reasonable: Yes/No
- Unit scores reasonable: Yes/No
- Priority rankings useful: Yes/No

Diagnostic Rules Performance:
- Rules firing appropriately: Yes/No
- False positive rate: _____%
- Most useful rule: _____
- Least useful rule: _____

Explanation Quality:
- Operator feedback: _____
- Clarity rating (1-5): _____
- Actionability rating (1-5): _____

Key Learnings:
- 
- 

Unexpected Patterns Discovered:
- 
- 

Recommendations for Phase 4:
- 
- 

Readiness for Phase 4:
- Aggregation reliable: Ready / Needs Work
- Rules tuned: Ready / Needs Work
- Explanations clear: Ready / Needs Work
```

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-05-24 | Senior Data Scientist | Initial Phase 3 implementation guide |

---

**Related Documents**
- [Implementation Plan (Main)](implementation_plan.md)
- [Phase 2 Guide](implementation_phase_2.md)
- [Phase 4 Guide](implementation_phase_4.md)
