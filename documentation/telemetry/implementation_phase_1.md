# Phase 1: Foundation — Implementation Guide

**Duration**: Weeks 1-2 (10 working days)  
**Objective**: Establish the analytical infrastructure required for all techniques  
**Status**: Not Started  
**Last Updated**: May 24, 2026

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

Build the foundational infrastructure that all analytical techniques will rely on:
- Data models and schemas
- Signal metadata registry
- Data quality profiling
- Baseline generation system
- Execution orchestration

### Why This Phase Matters

**Without solid foundations**:
- Techniques will have inconsistent data structures
- No reliable baselines for comparison
- No way to assess data quality or confidence
- Difficult to schedule mixed-cadence executions

**With solid foundations**:
- Clear contracts for all data structures
- Versioned, auditable baselines
- Data quality transparently tracked
- Scalable execution framework

### Key Principle

**Fail fast, fail early.** If Silver data quality is poor or signal registry is incomplete, discover this in Phase 1, not Phase 3.

---

## 📅 Timeline

### Week 1: Core Data Infrastructure

#### Day 1: Analytical Data Model Design

**Morning** (4 hours):
- Define core entities: Signal, System, Unit, EvaluationWindow, TechniqueResult, SystemHealth, UnitHealth
- Create entity relationship diagram (ERD)
- Document entity purposes and relationships
- Define key vs. non-key attributes

**Afternoon** (4 hours):
- Create Pydantic models or dataclasses for each entity
- Define validation rules (e.g., risk_score 0-100, required fields)
- Write unit tests for entity validation
- Document schema versioning strategy

**Output**: `src/models/entities.py`, `docs/entity_diagram.md`

---

#### Day 2: Storage Architecture & Partitioning

**Morning** (4 hours):
- Design Parquet partitioning strategy for each output type
- Define directory structure (see Appendix A in implementation_plan.md)
- Create utility functions for partition path generation
- Document retention policies per output type

**Afternoon** (4 hours):
- Implement base writer classes for partitioned Parquet
- Add schema versioning to all outputs
- Write tests for partition generation and writing
- Create sample output directories

**Output**: `src/utils/storage.py`, `src/utils/partition_utils.py`

---

#### Day 3: Signal Registry Creation

**Morning** (4 hours):
- Review Silver layer to identify all available signals
- Research signal metadata (units, physical ranges, criticality)
- Draft signal_registry_v1.yaml with 10-15 key signals
- Document risk_direction logic per signal type

**Afternoon** (4 hours):
- Implement SignalRegistry class with validation
- Add methods: get_signal(), get_signals_by_system(), is_technique_enabled()
- Write unit tests for registry loading and queries
- Implement version checking on startup

**Output**: `data/telemetry/config/signal_registry_v1.yaml`, `src/config/signal_registry.py`

**Sample signals to include**:
- EngCoolTemp, EngOilPres, EngSpd (Engine)
- TrnLubeTemp, TrnOilPres (Transmission)
- LtFBrkTemp, LtRBrkTemp, RtFBrkTemp, RtRBrkTemp (Brakes)
- StrgOilTemp, StrgOilPres (Hydraulics)
- DiffTemp, DiffLubePres (Differential)
- TCOutTemp, RAftrclrTemp, LAftrclrTemp (Cooling)

---

#### Day 4: System Mapping & Technique Configuration

**Morning** (4 hours):
- Define system-to-signal mappings
- Create technique_config.yaml (cadence, window, thresholds per technique)
- Document system criticality weights (Engine=3, Transmission=2.5, etc.)
- Define operational state valid ranges per signal

**Afternoon** (4 hours):
- Implement TechniqueConfig class
- Add evaluation window definitions (24h, 7d, 4w, 8w, 12w)
- Define technique validity periods
- Write configuration validation tests

**Output**: `data/telemetry/config/technique_config.yaml`, `src/config/technique_config.py`

---

#### Day 5: Silver Data Profiling Tool

**Morning** (4 hours):
- Implement data profiling module
- Calculate metrics per unit/signal/day:
  - Sample count, valid count, missing%
  - Flatline detection (unchanged for >4h)
  - Out-of-range detection (physical_min/max violations)
  - State distribution (% time in each operational state)

**Afternoon** (4 hours):
- Generate HTML profiling report (use pandas-profiling or custom)
- Create JSON summary output
- Add signal availability heatmap (units × signals × weeks)
- Write profiling execution script

**Output**: `src/data/profiler.py`, `scripts/profile_silver_data.py`

---

### Week 2: Baselines & Orchestration

#### Day 6: Data Quality Scoring

**Morning** (4 hours):
- Implement data quality metrics per evaluation window
- Calculate coverage score (valid samples / expected samples)
- Detect data gaps (consecutive missing hours)
- Compute state consistency score

**Afternoon** (4 hours):
- Build confidence scoring function
- Penalties: coverage <80%, baseline quality, state mismatch, small sample size
- Document confidence thresholds (InsufficientData if <50)
- Write quality scoring tests

**Output**: `src/scoring/confidence.py`, `src/data/quality_metrics.py`

---

#### Day 7: Baseline Generation - Part 1

**Morning** (4 hours):
- Implement baseline calculation logic
- Group Silver data by: client + equipment_model + signal + operational_state
- Calculate percentiles: P1, P5, P50, P95, P99
- Calculate moments: mean, std, MAD

**Afternoon** (4 hours):
- Add baseline quality assessment (sample count, distribution checks)
- Implement minimum sample requirements (≥1000 per state)
- Handle insufficient data cases (fallback to aggregate)
- Test baseline calculation on sample data

**Output**: `src/baselines/baseline_generator.py`

---

#### Day 8: Baseline Generation - Part 2

**Morning** (4 hours):
- Implement baseline versioning (YYYYMMDD format)
- Create baseline metadata JSON generator
- Build baseline storage writer (Parquet + metadata)
- Add baseline staleness detection

**Afternoon** (4 hours):
- Implement baseline fallback hierarchy (unit → model → client → global)
- Create BaselineManager class for retrieval
- Write tests for baseline lookup with fallbacks
- Generate initial baselines for all clients

**Output**: `src/baselines/baseline_manager.py`, `data/telemetry/analytical_results/baselines/baseline_20260524.parquet`

---

#### Day 9: Evaluation Window System

**Morning** (4 hours):
- Implement EvaluationWindow dataclass
- Create window generator for each technique type:
  - Rolling windows (6h, 24h)
  - Tumbling windows (weekly)
  - Multi-week windows (4w, 8w, 12w)

**Afternoon** (4 hours):
- Add window metadata storage
- Implement window validity checking (start < end, lookback ≥ 0)
- Handle partial windows (e.g., mid-week unit startup)
- Write window generation tests

**Output**: `src/utils/evaluation_window.py`

---

#### Day 10: Execution Orchestration Setup

**Morning** (4 hours):
- Install and configure Prefect
- Create base flow templates
- Define dummy tasks for each technique (placeholders)
- Set up flow scheduling configuration

**Afternoon** (4 hours):
- Implement logging and monitoring
- Add retry logic for failed tasks
- Create error notification system (log to file for POC)
- Test dummy flow execution end-to-end

**Output**: `src/orchestration/flows.py`, `src/orchestration/schedules.py`, `src/utils/logger.py`

---

## 📥 Inputs

### Data Inputs

| Input | Location | Format | Volume | Notes |
|-------|----------|--------|--------|-------|
| Silver telemetry | `data/telemetry/silver/{client}/week_*.parquet` | Parquet | ~100MB/week/unit | Minute-level data |
| Equipment metadata | External or config | CSV/JSON | <1MB | Unit models, client mapping |

### Configuration Inputs

| Input | Source | Notes |
|-------|--------|-------|
| Signal definitions | Domain expert + Silver analysis | Physical ranges, units, criticality |
| System mappings | Equipment documentation | Which signals belong to which systems |
| Operational state definitions | Existing pipeline | State names and meanings |

---

## 📤 Outputs

### Code Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| Entity models | `src/models/entities.py` | Pydantic/dataclass definitions |
| Signal registry | `data/telemetry/config/signal_registry_v1.yaml` | Signal metadata |
| Technique config | `data/telemetry/config/technique_config.yaml` | Technique parameters |
| Profiling tool | `src/data/profiler.py` | Data quality assessment |
| Baseline generator | `src/baselines/baseline_generator.py` | Baseline calculation |
| Baseline manager | `src/baselines/baseline_manager.py` | Baseline retrieval with fallbacks |
| Orchestration flows | `src/orchestration/flows.py` | Prefect flow definitions |

### Data Artifacts

| Artifact | Location | Format | Purpose |
|----------|----------|--------|---------|
| Initial baselines | `data/telemetry/analytical_results/baselines/baseline_20260524.parquet` | Parquet | Reference statistics |
| Baseline metadata | `data/telemetry/analytical_results/baselines/baseline_metadata.json` | JSON | Version, training window info |
| Profiling reports | `outputs/profiling/` | HTML + JSON | Data quality assessment |
| Directory structure | `data/telemetry/analytical_results/` | Folders | Storage organization |

### Documentation Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| Entity diagram | `documentation/entity_diagram.md` | Visual data model |
| Signal registry guide | `documentation/signal_registry_guide.md` | How to add/modify signals |
| Baseline methodology | `documentation/baseline_methodology.md` | Calculation details |

---

## ✅ Task Checklist

### Week 1: Core Data Infrastructure

**Day 1: Analytical Data Model**
- [ ] Define 7 core entities (Signal, System, Unit, etc.)
- [ ] Create entity relationship diagram
- [ ] Implement Pydantic models with validation
- [ ] Write unit tests for entity validation
- [ ] Document schema versioning strategy

**Day 2: Storage Architecture**
- [ ] Design Parquet partitioning strategy
- [ ] Define directory structure
- [ ] Implement partition path generation utilities
- [ ] Create base writer classes for partitioned Parquet
- [ ] Add schema versioning to all outputs
- [ ] Test partition generation and writing
- [ ] Create sample output directories

**Day 3: Signal Registry**
- [ ] Review Silver layer signals (full inventory)
- [ ] Research signal metadata (15-20 key signals)
- [ ] Draft signal_registry_v1.yaml
- [ ] Implement SignalRegistry class
- [ ] Add registry query methods
- [ ] Write registry loading and validation tests
- [ ] Document signal addition process

**Day 4: System Mapping & Technique Config**
- [ ] Define 6 systems (Engine, Transmission, Brakes, etc.)
- [ ] Map signals to systems
- [ ] Create technique_config.yaml
- [ ] Define system criticality weights
- [ ] Implement TechniqueConfig class
- [ ] Define evaluation windows per technique
- [ ] Document technique validity periods
- [ ] Write configuration validation tests

**Day 5: Silver Data Profiling**
- [ ] Implement profiling metrics calculation
- [ ] Add flatline detection logic
- [ ] Add out-of-range detection logic
- [ ] Calculate operational state distributions
- [ ] Generate HTML profiling report
- [ ] Create JSON summary output
- [ ] Add signal availability heatmap
- [ ] Write profiling execution script
- [ ] Run profiling on full Silver dataset

### Week 2: Baselines & Orchestration

**Day 6: Data Quality Scoring**
- [ ] Implement coverage score calculation
- [ ] Add data gap detection (consecutive missing hours)
- [ ] Compute state consistency score
- [ ] Build confidence scoring function
- [ ] Define confidence penalties (coverage, baseline, state, size)
- [ ] Document InsufficientData threshold (confidence < 50)
- [ ] Write quality scoring unit tests

**Day 7: Baseline Generation - Part 1**
- [ ] Implement baseline calculation logic
- [ ] Add grouping by client + model + signal + state
- [ ] Calculate percentiles (P1, P5, P50, P95, P99)
- [ ] Calculate moments (mean, std, MAD)
- [ ] Add baseline quality assessment
- [ ] Implement minimum sample requirements (≥1000)
- [ ] Handle insufficient data cases
- [ ] Test on sample data

**Day 8: Baseline Generation - Part 2**
- [ ] Implement baseline versioning (YYYYMMDD)
- [ ] Create baseline metadata JSON generator
- [ ] Build baseline storage writer
- [ ] Add baseline staleness detection
- [ ] Implement fallback hierarchy (4 levels)
- [ ] Create BaselineManager class
- [ ] Write baseline lookup tests with fallbacks
- [ ] Generate initial baselines for all clients

**Day 9: Evaluation Window System**
- [ ] Implement EvaluationWindow dataclass
- [ ] Create rolling window generator (6h, 24h)
- [ ] Create tumbling window generator (weekly)
- [ ] Create multi-week window generator (4w, 8w, 12w)
- [ ] Add window metadata storage
- [ ] Implement window validity checking
- [ ] Handle partial window cases
- [ ] Write window generation tests

**Day 10: Execution Orchestration**
- [ ] Install Prefect
- [ ] Configure Prefect workspace
- [ ] Create base flow templates
- [ ] Define dummy tasks for each technique (6 tasks)
- [ ] Set up scheduling configuration
- [ ] Implement structured logging
- [ ] Add retry logic for failed tasks
- [ ] Create error notification system
- [ ] Test dummy flow execution end-to-end
- [ ] Document flow execution process

---

## 📦 Deliverables

### Critical Deliverables (Must-Have)

1. **Signal Registry** (`signal_registry_v1.yaml`)
   - At least 15 signals defined with complete metadata
   - Validation passes on startup
   - Documentation for adding new signals

2. **Baseline System** (`baseline_generator.py`, `baseline_manager.py`)
   - Generates baselines for all client + model + signal + state combinations
   - At least 1 baseline version created (`baseline_20260524.parquet`)
   - Fallback hierarchy working for edge cases

3. **Data Profiling Report**
   - HTML report showing data quality for all units
   - JSON summary with key metrics
   - Signal availability heatmap

4. **Orchestration Framework**
   - Prefect flows can execute dummy tasks
   - Scheduling configuration defined
   - Logging and error handling functional

### Important Deliverables (Should-Have)

5. **Entity Models** (`entities.py`)
   - All 7 core entities defined with validation
   - Unit tests passing

6. **Technique Configuration** (`technique_config.yaml`)
   - 6 techniques configured (threshold, event, trend, rules, peer, AE)
   - Evaluation windows defined

7. **Storage Infrastructure** (`storage.py`, `partition_utils.py`)
   - Partition path generation working
   - Base writer classes implemented
   - Output directory structure created

### Nice-to-Have Deliverables

8. **Documentation**
   - Entity relationship diagram
   - Signal registry guide
   - Baseline methodology document

---

## 🎯 Success Criteria

### Functional Success Criteria

| Criterion | Target | Validation Method |
|-----------|--------|-------------------|
| Signal registry completeness | ≥15 signals with full metadata | Manual review |
| Baseline coverage | 100% of client + model + signal + state combinations | Automated count |
| Baseline quality | ≥80% of baselines have quality_score > 0.7 | Query baseline file |
| Data profiling coverage | All units profiled | Check profiling report |
| Orchestration reliability | Dummy flows execute without errors | Manual test run |

### Technical Success Criteria

| Criterion | Target | Validation Method |
|-----------|--------|-------------------|
| Entity validation | All Pydantic models enforce constraints | Unit tests pass |
| Baseline fallback logic | Correctly selects fallback when primary unavailable | Unit tests pass |
| Partition generation | Generates correct paths for all output types | Unit tests pass |
| Configuration validation | Invalid configs rejected on startup | Integration test |

### Data Quality Success Criteria

| Criterion | Target | Validation Method |
|-----------|--------|-------------------|
| Silver data coverage | ≥70% of units have ≥90 days history | Profiling report |
| Signal availability | ≥80% of signals have ≥50% coverage | Profiling report |
| State distribution | Operational states identified for ≥90% of data | Profiling report |
| Missing data patterns | Identified and documented | Profiling report + analysis |

### Exit Gates (Must Pass to Proceed to Phase 2)

**Gate 1: Infrastructure Validation**
- [ ] Signal registry loads without errors
- [ ] Technique config loads without errors
- [ ] All entity models validate correctly
- [ ] Output directories exist and are writable

**Gate 2: Baseline Quality**
- [ ] At least 1 baseline version generated
- [ ] ≥80% of expected baselines created (some may be missing due to insufficient data)
- [ ] Baseline manager retrieves baselines correctly
- [ ] Fallback logic tested and working

**Gate 3: Data Understanding**
- [ ] Profiling report generated for all clients
- [ ] Data quality issues identified and documented
- [ ] Known gaps or limitations documented
- [ ] Minimum data requirements validated against Silver

**Gate 4: Orchestration Readiness**
- [ ] Prefect flows execute successfully
- [ ] Logging captures execution details
- [ ] Error handling prevents silent failures
- [ ] Can schedule and run dummy tasks

---

## 📝 Implementation Notes

### Week 1 Notes

**Day 1 (Analytical Data Model):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 
- 

Blockers/Issues:
- 
- 

Decisions Made:
- 
- 

Next Steps:
- 
- 
```

**Day 2 (Storage Architecture):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 
- 

Blockers/Issues:
- 
- 

Decisions Made:
- 
- 

Next Steps:
- 
- 
```

**Day 3 (Signal Registry):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 
- 

Blockers/Issues:
- 
- 

Decisions Made:
- 
- 

Next Steps:
- 
- 
```

**Day 4 (System Mapping & Config):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 
- 

Blockers/Issues:
- 
- 

Decisions Made:
- 
- 

Next Steps:
- 
- 
```

**Day 5 (Silver Data Profiling):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 
- 

Blockers/Issues:
- 
- 

Decisions Made:
- 
- 

Data Quality Findings:
- 
- 

Next Steps:
- 
- 
```

### Week 2 Notes

**Day 6 (Data Quality Scoring):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 
- 

Blockers/Issues:
- 
- 

Confidence Thresholds Chosen:
- Coverage penalty: _____
- Baseline penalty: _____
- State mismatch penalty: _____

Next Steps:
- 
- 
```

**Day 7 (Baseline Generation - Part 1):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 
- 

Blockers/Issues:
- 
- 

Baseline Statistics:
- Total combinations expected: _____
- Combinations with sufficient data: _____
- Combinations requiring fallback: _____

Next Steps:
- 
- 
```

**Day 8 (Baseline Generation - Part 2):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 
- 

Blockers/Issues:
- 
- 

Baseline Files Generated:
- Version: _____
- Size: _____
- Clients covered: _____

Fallback Statistics:
- Level 1 (unit): _____%
- Level 2 (model): _____%
- Level 3 (client): _____%
- Level 4 (global): _____%

Next Steps:
- 
- 
```

**Day 9 (Evaluation Window System):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 
- 

Blockers/Issues:
- 
- 

Window Types Implemented:
- Rolling 6h: Yes/No
- Rolling 24h: Yes/No
- Tumbling weekly: Yes/No
- Multi-week (4w, 8w, 12w): Yes/No

Edge Cases Handled:
- Partial windows: _____
- Missing data: _____
- State transitions: _____

Next Steps:
- 
- 
```

**Day 10 (Execution Orchestration):**
```
Date: ___________
Developer: ___________

Work Completed:
- 
- 
- 

Blockers/Issues:
- 
- 

Prefect Configuration:
- Flows created: _____
- Tasks defined: _____
- Scheduling tested: Yes/No
- Retry logic tested: Yes/No

Test Execution Results:
- Dummy flow success: Yes/No
- Error handling works: Yes/No
- Logs captured: Yes/No

Next Steps:
- 
- 
```

---

### Phase 1 Retrospective

**To be completed at end of Phase 1:**

```
Date Completed: ___________
Team: ___________

What Went Well:
- 
- 
- 

What Didn't Go Well:
- 
- 
- 

Key Learnings:
- 
- 
- 

Unexpected Challenges:
- 
- 
- 

Data Quality Surprises:
- 
- 
- 

Architecture Decisions to Revisit:
- 
- 
- 

Recommendations for Phase 2:
- 
- 
- 

Estimated vs. Actual Time:
- Estimated: 10 days
- Actual: _____ days
- Variance: _____

Readiness for Phase 2:
- Infrastructure: Ready / Needs Work
- Baselines: Ready / Needs Work
- Data Understanding: Ready / Needs Work
- Team: Ready / Needs Work
```

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-05-24 | Senior Data Scientist | Initial Phase 1 implementation guide |

---

**Related Documents**
- [Implementation Plan (Main)](implementation_plan.md)
- [Project Overview](project_overview.md)
- [Data Contracts](data_contracts.md)
- [Phase 2 Guide](implementation_phase_2.md)
