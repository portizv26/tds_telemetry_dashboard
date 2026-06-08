# Implementation Guidelines — Documentation Navigator

**Version**: 1.0.0  
**Last Updated**: May 24, 2026  
**Purpose**: Guide for understanding and using the telemetry health evaluation POC documentation

---

## 📚 Documentation Structure Overview

This project uses a **hierarchical documentation structure** with two levels:

1. **Strategic Level** — High-level planning and architecture
2. **Tactical Level** — Day-by-day execution guides with task checklists

---

## 🗂️ File Inventory

### Strategic Planning Documents

#### 1. `implementation_plan.md` — Master Strategic Plan
**Purpose**: High-level overview of the entire POC project

**Contains**:
- Executive summary with success metrics
- Project objectives and design principles
- Architectural overview (system layers diagram)
- Phase summary table with timeline
- Brief phase descriptions with links to detailed guides
- Technical component specifications (signal registry, baselines, technique results)
- Success criteria definitions
- Risk management
- Glossary of key terms
- Appendices (file structure, design decisions)

**When to use**:
- 📖 Project kickoff — Understand overall vision
- 🎯 Stakeholder presentations — Explain approach
- 🤔 Architectural questions — Reference design decisions
- 🔍 Technical specs — Look up schema definitions

**Target audience**: Project managers, architects, stakeholders, new team members

---

#### 2. `project_overview.md` — Architectural Deep Dive
**Purpose**: Explain the multi-technique framework design philosophy

**Contains**:
- Mission statement and scope boundaries
- Architectural philosophy (technique independence, risk/confidence separation)
- Multi-technique framework comparison table
- Evaluation hierarchy (Signal → System → Unit)
- Detailed technique methodologies (6 techniques)
- Scoring methodology with normalization functions
- Baseline strategy (state-specific, versioning, fallback hierarchy)
- Output architecture with storage strategy
- Key differentiators vs. traditional approaches

**When to use**:
- 🧠 Understanding "why" decisions were made
- 🔬 Learning technique methodologies
- 📐 Understanding aggregation formulas
- 💡 Grasping design philosophy

**Target audience**: Data scientists, ML engineers, technical architects

---

#### 3. `data_contracts.md` — Data Schemas
**Purpose**: Define all input and output data structures

**Contains**:
- Silver layer input schema (minute-level telemetry)
- Baseline table schema (percentiles, state-specific)
- TechniqueResult common schema + technique-specific evidence
- SystemHealth schema (14 columns)
- UnitHealth schema (18 columns)
- Event schema (17 columns)
- Weekly aggregates schema

**When to use**:
- 📊 Writing data loading code
- ✍️ Creating output writers
- ✅ Validating data structures
- 🔗 Understanding data relationships

**Target audience**: Data engineers, developers implementing techniques

---

### Tactical Execution Guides

#### 4. `implementation_phase_1.md` — Foundation (Weeks 1-2)
**Purpose**: Day-by-day guide for building analytical infrastructure

**Contains**:
- 10-day detailed timeline (morning/afternoon tasks)
- 50+ task checkboxes
- Inputs/outputs documentation
- Code artifact specifications
- Success criteria with exit gates
- **Blank implementation notes** for daily tracking
- Phase retrospective template

**Key deliverables**:
- Signal registry (signal_registry_v1.yaml)
- Baseline generation system
- Data profiling tools
- Orchestration framework (Prefect)

**When to use**:
- 🚀 Starting Phase 1 execution
- ✅ Daily task tracking
- 📝 Logging daily progress and decisions
- 🎯 Checking exit criteria before Phase 2

**Target audience**: Implementation team executing Phase 1

---

#### 5. `implementation_phase_2.md` — Core Analytics (Weeks 3-4)
**Purpose**: Day-by-day guide for implementing first analytical techniques

**Contains**:
- 10-day detailed timeline
- 40+ task checkboxes
- Threshold deviation implementation steps
- Event detection implementation steps
- Trend analysis implementation steps
- Weekly aggregation implementation steps
- Score normalization guidelines
- **Blank implementation notes** for daily tracking

**Key deliverables**:
- Threshold deviation technique (daily + weekly)
- Event detection technique
- Trend analysis technique (4w, 8w, 12w)
- Score normalization framework

**When to use**:
- 🛠️ Implementing analytical techniques
- 📊 Building TechniqueResult outputs
- 🧪 Testing technique execution
- 📈 Reviewing score distributions

**Target audience**: Data scientists implementing techniques

---

#### 6. `implementation_phase_3.md` — Aggregation & Intelligence (Weeks 5-6)
**Purpose**: Day-by-day guide for building health aggregation and diagnostic rules

**Contains**:
- 10-day detailed timeline
- 40+ task checkboxes
- System aggregation implementation (6 systems)
- Unit aggregation implementation
- Diagnostic rules engine (5-8 rules)
- Explanation generation
- **Blank implementation notes** for daily tracking

**Key deliverables**:
- SystemHealth outputs (per system, per unit)
- UnitHealth outputs with priority rankings
- Diagnostic rules engine
- Natural language explanations

**When to use**:
- 🔄 Implementing aggregation logic
- 📋 Creating diagnostic rules
- 💬 Building explanation templates
- 🏆 Generating priority rankings

**Target audience**: Data scientists implementing aggregation layer

---

#### 7. `implementation_phase_4.md` — Validation (Week 7)
**Purpose**: Day-by-day guide for validating framework performance

**Contains**:
- 5-day detailed timeline
- 30+ task checkboxes
- Known event collection guidelines (≥10 failures)
- Backtest execution steps
- False positive analysis methodology
- Threshold calibration process
- Validation report structure
- **Blank implementation notes** for daily tracking

**Key deliverables**:
- Known events dataset (known_events.csv)
- Backtest results (detection rate, advance warning)
- False positive analysis
- Calibrated thresholds
- Comprehensive validation report

**When to use**:
- 🔍 Collecting historical failure data
- 🧪 Running backtest validation
- ⚖️ Calibrating thresholds
- 📊 Generating validation report

**Target audience**: Data scientists, validation analysts

---

#### 8. `implementation_phase_5_advanced_diagnostic_rules.md` — Advanced Diagnostic Rules (Week 8)
**Purpose**: Day-by-day guide for implementing sophisticated multi-signal failure patterns

**Contains**:
- 3-day detailed timeline (Days 37-39)
- 30+ task checkboxes
- Advanced rule design (5-8 additional rules)
- Rule engine enhancements (temporal logic, multi-signal patterns)
- Historical backtest validation
- Integration with Phase 3 aggregation
- **Local execution guide** (no orchestration)
- **Blank implementation notes** for daily tracking

**Key deliverables**:
- 5-8 advanced diagnostic rules (10-15 total with Phase 3)
- Enhanced DiagnosticRulesEngine
- Backtest validation against known failures
- Local runner script

**When to use**:
- 🧠 Encoding domain expert knowledge into rules
- 🔍 Detecting complex mechanical failure patterns
- 📋 Adding explainable intelligence layer
- 🎯 Targeting failures missed by Phase 2 techniques

**Target audience**: Data scientists, domain experts

---

#### 9. `implementation_phase_6_peer_deviation.md` — Peer Deviation Analysis (Week 9)
**Purpose**: Day-by-day guide for implementing fleet-based peer comparison

**Contains**:
- 3-day detailed timeline (Days 40-42)
- 25+ task checkboxes
- Fleet baseline generation (percentiles, z-scores)
- Peer comparison logic implementation
- Risk score normalization (relative performance)
- Bottom performer identification
- **Local execution guide** (simple Python runners)
- **Blank implementation notes** for daily tracking

**Key deliverables**:
- Fleet baseline generation system
- PeerDeviation technique class
- Peer comparison results (percentile ranks, z-scores)
- Bottom 10% performers report

**When to use**:
- 📊 Comparing units against fleet context
- 🔍 Detecting relative underperformance
- 📈 Identifying units drifting from fleet average
- 🎯 Catching "slow drift" failures

**Target audience**: Data scientists implementing statistical techniques

---

#### 10. `implementation_phase_7_change_point.md` — Change-Point Detection (Weeks 9-10)
**Purpose**: Day-by-day guide for detecting sudden regime shifts using PELT algorithm

**Contains**:
- 4-day detailed timeline (Days 43-46)
- 35+ task checkboxes
- PELT algorithm implementation (ruptures library)
- Change-point detection and analysis
- Maintenance event correlation
- Parameter tuning (penalty, segment length)
- **Local execution guide** (weekly execution)
- **Blank implementation notes** for daily tracking

**Key deliverables**:
- ChangePointDetection technique class
- Regime shift detection (before/after analysis)
- Maintenance event labeling
- High-risk change-point reports

**When to use**:
- 🔄 Detecting sudden behavioral changes
- 📅 Distinguishing maintenance from degradation
- 🚨 Identifying failure precursor events
- 🎯 Catching abrupt deterioration

**Target audience**: Data scientists implementing time series analysis

---

#### 11. `implementation_phase_8_autoencoder.md` — AutoEncoder Anomaly Detection (Weeks 10-11)
**Purpose**: Day-by-day guide for implementing ML-based multivariate anomaly detection

**Contains**:
- 5-day detailed timeline (Days 47-51)
- 40+ task checkboxes
- AutoEncoder architecture design (6→4→2→4→6)
- Model training on healthy data
- Threshold calibration (P95 reconstruction error)
- SHAP explainability integration (optional)
- **Local execution guide** (TensorFlow/Keras setup)
- **Blank implementation notes** for daily tracking

**Key deliverables**:
- Trained AutoEncoder model (Engine system)
- AutoEncoderAnomaly technique class
- Validation against known failures
- Model registry and serving infrastructure

**When to use**:
- 🤖 Detecting complex multivariate patterns
- 🔬 Analyzing signal interactions and correlations
- 🎯 Catching failures explainable techniques miss
- ⚠️ Last resort for complex failure modes

**Target audience**: Data scientists, ML engineers

**⚠️ Important**: Phases 5-8 are now **MANDATORY** (no longer optional). Each phase builds a distinct analytical capability and should be completed sequentially.

---

## 🎯 Implementation Workflow

### Step 1: Project Kickoff (Day 0)
1. Read `implementation_plan.md` (Executive Summary + Phase Overview)
2. Read `project_overview.md` (Understand architectural philosophy)
3. Review `data_contracts.md` (Understand data structures)

**Goal**: Understand what you're building and why

---

### Step 2: Phase Execution (Weeks 1-11)

**Complete 8-Phase Implementation Timeline**:
- **Phase 1** (Weeks 1-2): Foundation — Data infrastructure and baselines
- **Phase 2** (Weeks 3-4): Core Analytics — Threshold, event, trend techniques
- **Phase 3** (Weeks 5-6): Aggregation & Intelligence — System/unit health, diagnostic rules
- **Phase 4** (Week 7): Validation — Historical backtest and threshold calibration
- **Phase 5** (Week 8, 2-3 days): Advanced Diagnostic Rules — Complex failure patterns
- **Phase 6** (Week 9, 2-3 days): Peer Deviation — Fleet-based comparison
- **Phase 7** (Weeks 9-10, 3-4 days): Change-Point Detection — Regime shift analysis
- **Phase 8** (Weeks 10-11, 4-5 days): AutoEncoder — ML-based multivariate anomaly detection

**Total Duration**: ~11 weeks (55 working days)

**For each phase**:

1. **Open phase guide** (`implementation_phase_X.md`)
2. **Review phase overview** (purpose, key principles, deliverables)
3. **Check inputs section** (do you have everything you need?)
4. **Follow day-by-day timeline**:
   - Each day: morning tasks (4h) + afternoon tasks (4h)
   - Check off tasks as completed
   - Fill in implementation notes daily
5. **Track deliverables** (critical, important, nice-to-have)
6. **Validate exit criteria** before moving to next phase
7. **Complete phase retrospective** (what went well, what didn't)

**Daily routine**:
```
Morning:
- Review today's tasks from phase guide
- Execute morning task block (4h)
- Log progress in implementation notes

Afternoon:
- Execute afternoon task block (4h)
- Update task checklist
- Log blockers, decisions, next steps
- Prepare for next day
```

**Local Execution Note**: Phases 5-8 include detailed local execution guides with command-line scripts. No orchestration framework (Prefect) is required — run scripts manually as needed.

---

### Step 3: Cross-Phase References

**While implementing techniques** (Phases 2, 5-8):
- Reference `data_contracts.md` for schema definitions
- Reference `project_overview.md` for methodology details
- Reference `implementation_plan.md` for technical component specs

**While validating** (Phase 4):
- Reference Phase 2-3 retrospectives for known issues
- Reference `implementation_plan.md` for success criteria thresholds

**While implementing advanced techniques** (Phases 5-8):
- Reference Phase 4 validation report for gaps to address
- Reference Phase 2-3 outputs for input data
- Each phase builds incrementally on previous work

---

## 📋 Documentation Usage Patterns

### Pattern 1: "I'm starting a new phase"
1. Open `implementation_phase_X.md`
2. Read phase overview (first 2 pages)
3. Review inputs section (do I have everything?)
4. Scan timeline to understand flow
5. Start Day 1, Morning block

---

### Pattern 2: "I need to understand a design decision"
1. Check `implementation_plan.md` → Section 3 (Core Design Principles)
2. If still unclear, check `project_overview.md` → Architectural Philosophy
3. If technical detail needed, check relevant technical component section

---

### Pattern 3: "I need to implement a data schema"
1. Open `data_contracts.md`
2. Find relevant schema (e.g., TechniqueResult)
3. Copy schema definition
4. Implement in code (Pydantic/dataclass)
5. Reference schema in implementation notes

---

### Pattern 4: "I'm blocked on a task"
1. Log blocker in daily implementation notes
2. Check phase retrospectives from previous phases (similar issues?)
3. Check `implementation_plan.md` → Risk Management section
4. Escalate to team lead if unresolved

---

### Pattern 5: "I need to track progress"
1. Use task checklists in phase guide (check off completed)
2. Fill in daily implementation notes
3. Review deliverables section (which are complete?)
4. Check exit criteria (am I ready for next phase?)

---

## ✅ Daily Implementation Notes Structure

Each phase guide has **blank implementation notes** sections. Fill these out daily:

```markdown
Date: 2026-05-24
Developer: John Doe

Work Completed:
- Implemented SignalRegistry class
- Added validation for signal_registry_v1.yaml
- Wrote unit tests for registry loading

Blockers/Issues:
- Silver data missing for 3 units (escalated to data team)

Decisions Made:
- Using P1/P99 instead of P2/P98 for stricter anomaly detection
- Rationale: Domain expert recommendation

Next Steps:
- Complete system mapping (Day 4 morning)
- Begin technique configuration (Day 4 afternoon)
```

**Why this matters**:
- Creates audit trail of decisions
- Documents blockers for retrospectives
- Helps next developer understand context
- Provides material for status reports

---

## 🚦 Exit Criteria and Gates

Each phase has **Exit Gates** that must pass before proceeding:

**Example from Phase 1**:
- [ ] Signal registry loads without errors
- [ ] Baselines generated for ≥80% of expected combinations
- [ ] Orchestration framework can run dummy tasks
- [ ] Data quality issues documented

**How to use**:
1. At end of phase, review exit gates
2. Check each box honestly
3. If any fail, document why and address before Phase 2
4. Document decision to proceed (or not) in phase retrospective

---

## 📊 Phase Retrospective Template

Each phase guide ends with a **retrospective template**. Complete this before moving to next phase:

```markdown
Date Completed: _____
Team: _____

What Went Well:
- [List 3-5 things]

What Didn't Go Well:
- [List 3-5 things]

Key Learnings:
- [Document insights]

Recommendations for Next Phase:
- [Action items]

Readiness Assessment:
- Infrastructure: Ready / Needs Work
- Data Quality: Ready / Needs Work
- Team: Ready / Needs Work
```

**Why this matters**:
- Continuous improvement
- Prevents repeating mistakes
- Documents lessons learned
- Informs later phases

---

## 🎓 For Implementation Agents/AI Assistants

If you're an AI agent helping with implementation:

### Context Loading Strategy

**For general questions**:
1. Load `implementation_plan.md` (strategic context)
2. Load `project_overview.md` (architectural context)

**For specific phase questions**:
1. Load `implementation_phase_X.md` for current phase
2. Reference `implementation_plan.md` for technical specs
3. Reference `data_contracts.md` for schemas

**For code implementation**:
1. Load relevant phase guide (specific day/task)
2. Load `data_contracts.md` (schema definitions)
3. Load `project_overview.md` (methodology details)

### Key Principles for Agents

1. **Always check phase guide first** — Most detailed instructions are there
2. **Follow day-by-day sequence** — Tasks build on each other
3. **Reference implementation notes** — Past decisions inform current work
4. **Validate exit criteria** — Don't skip ahead if gates fail
5. **Document decisions** — Fill in implementation notes as you work

### Common Agent Tasks

| Task | Primary Document | Supporting Documents |
|------|------------------|---------------------|
| Generate entity models | phase_1.md (Day 1) | data_contracts.md, project_overview.md |
| Implement technique | phase_2.md (specific day) | project_overview.md (methodology), data_contracts.md |
| Create aggregation logic | phase_3.md (Days 21-29) | project_overview.md (formulas), implementation_plan.md |
| Write validation report | phase_4.md (Day 36) | implementation_plan.md (success criteria) |
| Select enhancement | phase_5.md (selection guidance) | phase_4.md (validation results) |

---

## 🔗 Quick Reference Links

### Strategic Documents
- [Implementation Plan](implementation_plan.md) — High-level overview
- [Project Overview](project_overview.md) — Architecture deep dive
- [Data Contracts](data_contracts.md) — Schemas

### Phase Guides
- [Phase 1: Foundation](implementation_phase_1.md) — Weeks 1-2
- [Phase 2: Core Analytics](implementation_phase_2.md) — Weeks 3-4
- [Phase 3: Aggregation & Intelligence](implementation_phase_3.md) — Weeks 5-6
- [Phase 4: Validation](implementation_phase_4.md) — Week 7
- [Phase 5: Optional Enhancements](implementation_phase_5.md) — Week 8+

---

## 📞 Support and Questions

**General questions**:
- Review this guidelines file first
- Check relevant phase guide
- Check implementation_plan.md technical components

**Technical questions**:
- Check project_overview.md for methodology
- Check data_contracts.md for schemas
- Reference implementation notes for past decisions

**Process questions**:
- Check phase guide timeline
- Review exit criteria
- Consult phase retrospectives

---

**Version Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-05-24 | Senior Data Scientist | Initial implementation guidelines |

---

**Remember**: These documents are living artifacts. Update implementation notes daily, complete retrospectives, and iterate on the process as you learn.
