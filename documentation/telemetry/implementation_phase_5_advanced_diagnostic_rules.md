# Phase 5: Advanced Diagnostic Rules — Implementation Guide

**Duration**: Week 8 (2-3 working days)  
**Objective**: Implement sophisticated multi-signal mechanical failure patterns with domain knowledge  
**Status**: Not Started  
**Last Updated**: May 28, 2026  
**Prerequisites**: Phase 4 completed (validation report approved, thresholds calibrated)

---

## 📋 Table of Contents

1. [Phase Overview](#phase-overview)
2. [Timeline](#timeline)
3. [Inputs](#inputs)
4. [Outputs](#outputs)
5. [Task Checklist](#task-checklist)
6. [Deliverables](#deliverables)
7. [Success Criteria](#success-criteria)
8. [Local Execution Guide](#local-execution-guide)
9. [Implementation Notes](#implementation-notes)

---

## 🎯 Phase Overview

### Purpose

Expand the diagnostic rules framework (from Phase 3) to capture sophisticated mechanical failure patterns that require multi-signal temporal logic:

- **Complex Pattern Recognition**: Multi-signal conditions with temporal dependencies
- **Domain Knowledge Integration**: Encode expert mechanical knowledge into rules
- **Explainable Intelligence**: Every alert traces to specific rule logic
- **High-Value Detection**: Focus on patterns that Phase 2 techniques miss

### Why This Phase Matters

**Advanced diagnostic rules bridge the gap** between simple threshold violations and complex failure modes:
- Detect pre-failure signatures (e.g., coolant rising + oil pressure dropping = impending engine failure)
- Capture temporal patterns (e.g., persistent abnormality over 3+ days)
- Encode mechanical relationships (e.g., high brake temp + low hydraulic pressure = brake system compromise)
- Provide actionable explanations operators can understand

### Why This Is Phase 5 (Before Peer/ChangePoint/AutoEncoder)

**Rationale**:
1. ✅ **Highest Explainability**: Rules are 100% transparent and auditable
2. ✅ **Builds on Phase 3**: Extends existing diagnostic rules framework
3. ✅ **Domain-Driven**: Leverages expert knowledge, not just statistics
4. ✅ **Fast Implementation**: 2-3 days vs. 4-5 days for AutoEncoder
5. ✅ **Immediate Value**: Targets known failure patterns from Phase 4 validation

### Key Principle

**Explainability first.** Advanced rules must be understandable by maintenance teams and debuggable when they fire incorrectly.

---

## 📅 Timeline

### Day 37: Rule Design & Configuration

**Morning** (4 hours): **Advanced Rule Design**

**Tasks**:
1. Review Phase 3 diagnostic rules (5-8 basic rules implemented)
2. Review Phase 4 validation report: which failures were missed?
3. Consult with domain expert or review equipment manuals
4. Design 5-8 advanced rules targeting specific failure modes

**Advanced Rule Examples**:

| Rule ID | Rule Name | Logic | Systems | Severity | Expected Advance Warning |
|---------|-----------|-------|---------|----------|-------------------------|
| ADR-001 | Engine Pre-Failure Pattern | `EngCoolTemp` rising (trend slope >0.5°C/day) AND `EngOilPres` dropping (trend slope <-5 kPa/day) AND `EngSpd` stable (±50 RPM) | Engine | Critical | 5-7 days |
| ADR-002 | Transmission Overload Cascade | `TrnLubeTemp` >threshold P95 for 3+ consecutive days AND `TrnOilPres` >threshold P90 AND load state = "Heavy" | Transmission | High | 3-5 days |
| ADR-003 | Brake System Degradation | (`LtFBrkTemp` + `LtRBrkTemp`) mean rising trend AND (`RtFBrkTemp` + `RtRBrkTemp`) mean rising trend AND any single brake >120°C | Brakes | Critical | 2-4 days |
| ADR-004 | Differential Stress Pattern | `DiffTemp` >P95 for 2+ days AND `DiffLubePres` <P10 for 2+ days | Drive | High | 3-5 days |
| ADR-005 | Hydraulic Cavitation | `StrgOilPres` <P5 for 4+ hours AND `StrgOilTemp` <P20 (cold oil = high viscosity) | Hydraulics | Medium | 1-2 days |
| ADR-006 | Cooling System Compromise | (`TCOutTemp` + `RAftrclrTemp` + `LAftrclrTemp`) mean >P90 for 2+ days AND `EngCoolTemp` rising trend | Cooling | High | 3-4 days |
| ADR-007 | Multi-System Thermal Stress | 3+ systems with mean signal temps >P90 simultaneously for 1+ day | Multiple | Critical | 2-3 days |
| ADR-008 | Oscillating Failure Precursor | Signal variance >2x baseline variance for 3+ consecutive days (indicates unstable behavior) | Any | Medium | 1-3 days |

**Output**: Rule design document with logic, thresholds, expected outcomes

---

**Afternoon** (4 hours): **Rule Configuration**

**Tasks**:
1. Add advanced rules to `diagnostic_rules.yaml`
2. Define rule parameters (thresholds, time windows, severity)
3. Specify required signals per rule
4. Define rule evaluation cadence (daily vs. weekly)
5. Document rule metadata (description, rationale, tuning guidance)

**Configuration Structure**:
```yaml
advanced_rules:
  ADR-001:
    name: "Engine Pre-Failure Pattern"
    description: "Detects coolant heating + oil pressure drop signature"
    systems: ["Engine"]
    severity: "Critical"
    evaluation_cadence: "daily"
    conditions:
      - signal: "EngCoolTemp"
        operator: "trend_rising"
        threshold: 0.5  # °C/day
        window: "7d"
      - signal: "EngOilPres"
        operator: "trend_dropping"
        threshold: -5  # kPa/day
        window: "7d"
      - signal: "EngSpd"
        operator: "stable"
        threshold: 50  # ±50 RPM variance
    logic: "AND"
    minimum_confidence: 70
    expected_advance_warning_days: [5, 7]
    
  ADR-002:
    name: "Transmission Overload Cascade"
    # ... (similar structure)
```

**Validation**:
- Test YAML loads without errors
- Verify all referenced signals exist in signal registry
- Check threshold reasonableness

**Output**: `data/telemetry/config/diagnostic_rules.yaml` (updated)

---

### Day 38: Implementation & Testing

**Morning** (4 hours): **Rule Engine Enhancement**

**Tasks**:
1. Extend `DiagnosticRulesEngine` class from Phase 3
2. Implement temporal condition evaluators:
   - `evaluate_trend_condition()`: Check if slope exceeds threshold
   - `evaluate_persistence_condition()`: Check duration (consecutive days)
   - `evaluate_stability_condition()`: Check variance within bounds
   - `evaluate_multi_signal_condition()`: Combine multiple signals
3. Add rule state tracking (when did rule first trigger, how long has it persisted?)
4. Implement confidence scoring for advanced rules

**Code Structure**:
```python
class AdvancedDiagnosticRulesEngine(DiagnosticRulesEngine):
    def evaluate_trend_condition(self, signal, operator, threshold, window):
        """Evaluate if signal trend meets condition."""
        # Load trend analysis results
        # Check if slope exceeds threshold
        # Return (condition_met, confidence, evidence)
        pass
    
    def evaluate_persistence_condition(self, signal, operator, threshold, duration_days):
        """Evaluate if condition persisted for required duration."""
        # Load daily threshold deviation results
        # Check consecutive days above/below threshold
        # Return (condition_met, days_persisted, evidence)
        pass
    
    def evaluate_rule(self, rule_config, unit_data):
        """Evaluate single advanced rule."""
        # Evaluate each condition
        # Combine with logic (AND/OR)
        # Calculate overall confidence
        # Build evidence dictionary
        # Return TechniqueResult
        pass
```

**Output**: `src/techniques/advanced_diagnostic_rules.py`

---

**Afternoon** (4 hours): **Testing & Validation**

**Tasks**:
1. Create synthetic test data matching known failure patterns
2. Test each rule individually:
   - Does ADR-001 fire when coolant rises + oil drops?
   - Does ADR-003 fire when all brakes heat up?
3. Test rule confidence scoring (low confidence when data quality poor)
4. Test false positive scenarios (should NOT fire):
   - Normal operational variations
   - Single-signal anomalies (require multi-signal pattern)
5. Validate output schema (TechniqueResult format)

**Test Script**:
```python
# test_advanced_rules.py
def test_engine_pre_failure_rule():
    # Create synthetic data: coolant rising, oil dropping
    synthetic_data = create_engine_failure_pattern()
    engine = AdvancedDiagnosticRulesEngine(config)
    result = engine.evaluate_rule('ADR-001', synthetic_data)
    assert result.status == 'Anormal'
    assert result.risk_score > 70
    assert 'EngCoolTemp' in result.evidence['contributing_signals']
```

**Output**: `tests/test_advanced_rules.py`, test results documented

---

### Day 39: Backtesting & Integration

**Morning** (4 hours): **Historical Backtest**

**Tasks**:
1. Load Phase 4 known failure events
2. For each failure, check: did advanced rules detect it?
3. Measure for advanced rules only:
   - Detection rate (% of events detected)
   - Advance warning (days before failure)
   - Incremental detection (events NOT caught by Phase 2 techniques)
4. Compare against Phase 3 basic rules
5. Document which rules are most effective

**Backtest Script**:
```bash
# Run backtest
python scripts/backtest_advanced_rules.py \
  --known-events data/validation/known_events.csv \
  --output data/validation/advanced_rules_backtest.csv
```

**Expected Results**:
- Advanced rules catch ≥2 additional failures vs. Phase 2 techniques
- Mean advance warning ≥3 days
- No increase in false positive rate

**Output**: `data/validation/advanced_rules_backtest.csv`

---

**Afternoon** (4 hours): **Integration & Deployment**

**Tasks**:
1. Integrate advanced rules into analysis pipeline
2. Create runner script for local execution:
   ```python
   # run_advanced_diagnostic_rules.py
   python src/runners/run_advanced_diagnostic_rules.py \
     --date 2026-05-28 \
     --client CDA \
     --output data/telemetry/analytical_results/technique_results/advanced_diagnostic_rules/
   ```
3. Test on full fleet (all units, all clients)
4. Generate execution report:
   - How many rules fired per unit?
   - Which rules fired most frequently?
   - Any units with multiple rules firing? (high priority!)
5. Store results to `technique_results/advanced_diagnostic_rules/`
6. Verify results are accessible to Phase 3 aggregation layer

**Output**: 
- `src/runners/run_advanced_diagnostic_rules.py`
- Advanced rule results in `technique_results/advanced_diagnostic_rules/year=2026/month=05/day=28/`

---

## 📥 Inputs

### Data Inputs

| Input | Location | Format | Created By | Notes |
|-------|----------|--------|------------|-------|
| Technique results (Threshold) | `technique_results/threshold_deviation/` | Parquet | Phase 2 | For persistence conditions |
| Technique results (Trend) | `technique_results/trend_analysis/` | Parquet | Phase 2 | For trend conditions |
| Silver telemetry | `data/telemetry/silver/{client}/` | Parquet | Upstream | For variance/stability checks |
| Signal registry | `config/signal_registry_v1.yaml` | YAML | Phase 1 | Signal metadata |
| Basic diagnostic rules | `config/diagnostic_rules.yaml` | YAML | Phase 3 | Existing rules |
| Known failure events | `data/validation/known_events.csv` | CSV | Phase 4 | For backtest |

### Configuration Inputs

| Parameter | Source | Default | Notes |
|-----------|--------|---------|-------|
| Trend slope thresholds | Rule config | ±0.5 to ±5 (signal-dependent) | Adjustable per rule |
| Persistence duration | Rule config | 2-3 days | Minimum consecutive days |
| Multi-system threshold | Rule config | 3+ systems | For multi-system rules |
| Confidence minimum | Rule config | 70 | Minimum to trigger alert |

---

## 📤 Outputs

### Code Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| Advanced Rules Engine | `src/techniques/advanced_diagnostic_rules.py` | Rule evaluation logic |
| Rule evaluators | `src/techniques/rule_evaluators.py` | Condition evaluation functions |
| Runner script | `src/runners/run_advanced_diagnostic_rules.py` | Local execution script |
| Test suite | `tests/test_advanced_rules.py` | Validation tests |

### Data Artifacts

| Artifact | Location | Format | Cadence | Purpose |
|----------|----------|--------|---------|---------|
| Advanced rule results | `technique_results/advanced_diagnostic_rules/year=*/month=*/day=*/` | Parquet | Daily | Rule firing records |
| Backtest results | `data/validation/advanced_rules_backtest.csv` | CSV | One-time | Validation against known failures |
| Rule performance report | `data/validation/advanced_rules_performance.json` | JSON | One-time | Rule effectiveness metrics |

### Documentation Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| Rule design document | `documentation/telemetry/advanced_rules_design.md` | Rule logic and rationale |
| Tuning guide | `documentation/telemetry/advanced_rules_tuning.md` | How to adjust thresholds |
| Updated diagnostic_rules.yaml | `config/diagnostic_rules.yaml` | 10-15 total rules (5-8 basic + 5-8 advanced) |

---

## ✅ Task Checklist

### Day 37: Rule Design & Configuration

**Morning: Advanced Rule Design**
- [ ] Review Phase 3 diagnostic rules (count: how many exist?)
- [ ] Review Phase 4 validation report (identify missed failures)
- [ ] Research equipment manuals for mechanical failure signatures
- [ ] Design ADR-001: Engine Pre-Failure Pattern
- [ ] Design ADR-002: Transmission Overload Cascade
- [ ] Design ADR-003: Brake System Degradation
- [ ] Design ADR-004: Differential Stress Pattern
- [ ] Design ADR-005: Hydraulic Cavitation
- [ ] Design ADR-006: Cooling System Compromise
- [ ] Design ADR-007: Multi-System Thermal Stress
- [ ] Design ADR-008: Oscillating Failure Precursor (optional)
- [ ] Document rule design (logic, systems, severity, advance warning)

**Afternoon: Rule Configuration**
- [ ] Add ADR-001 to diagnostic_rules.yaml
- [ ] Add ADR-002 to diagnostic_rules.yaml
- [ ] Add ADR-003 to diagnostic_rules.yaml
- [ ] Add ADR-004 to diagnostic_rules.yaml
- [ ] Add ADR-005 to diagnostic_rules.yaml
- [ ] Add ADR-006 to diagnostic_rules.yaml
- [ ] Add ADR-007 to diagnostic_rules.yaml
- [ ] Add ADR-008 to diagnostic_rules.yaml (optional)
- [ ] Define rule parameters (thresholds, time windows)
- [ ] Specify required signals per rule
- [ ] Define evaluation cadence (daily/weekly)
- [ ] Document rule metadata (description, rationale)
- [ ] Validate YAML syntax (load without errors)
- [ ] Verify all signals exist in signal registry

### Day 38: Implementation & Testing

**Morning: Rule Engine Enhancement**
- [ ] Create AdvancedDiagnosticRulesEngine class
- [ ] Implement evaluate_trend_condition() method
- [ ] Implement evaluate_persistence_condition() method
- [ ] Implement evaluate_stability_condition() method
- [ ] Implement evaluate_multi_signal_condition() method
- [ ] Add rule state tracking (first trigger date, persistence)
- [ ] Implement confidence scoring for advanced rules
- [ ] Add evidence dictionary builder
- [ ] Write unit tests for condition evaluators

**Afternoon: Testing & Validation**
- [ ] Create synthetic test data (engine failure pattern)
- [ ] Test ADR-001 (Engine Pre-Failure)
- [ ] Test ADR-002 (Transmission Overload)
- [ ] Test ADR-003 (Brake Degradation)
- [ ] Test ADR-004 (Differential Stress)
- [ ] Test ADR-005 (Hydraulic Cavitation)
- [ ] Test false positive scenarios (should NOT fire)
- [ ] Validate TechniqueResult output schema
- [ ] Test confidence scoring (low when data poor)
- [ ] Document test results

### Day 39: Backtesting & Integration

**Morning: Historical Backtest**
- [ ] Load Phase 4 known_events.csv
- [ ] Run backtest for each known failure
- [ ] Calculate detection rate for advanced rules
- [ ] Calculate mean advance warning (days)
- [ ] Identify incremental detections (not caught by Phase 2)
- [ ] Compare against Phase 3 basic rules
- [ ] Generate backtest report (advanced_rules_backtest.csv)
- [ ] Document which rules are most effective

**Afternoon: Integration & Deployment**
- [ ] Create run_advanced_diagnostic_rules.py runner script
- [ ] Add command-line arguments (date, client, output)
- [ ] Test execution on single unit
- [ ] Run on full fleet (all units, all clients)
- [ ] Generate execution report (rules fired per unit)
- [ ] Store results to technique_results/ partition
- [ ] Verify results accessible to aggregation layer
- [ ] Update Phase 3 aggregation to include advanced rules
- [ ] Test end-to-end (advanced rules → system health)
- [ ] Document execution commands

---

## 📦 Deliverables

### Critical Deliverables (Must-Have)

1. **Advanced Diagnostic Rules Configuration**
   - 5-8 advanced rules defined in `diagnostic_rules.yaml`
   - Each rule with clear logic, thresholds, metadata
   - Total 10-15 rules (5-8 basic + 5-8 advanced)

2. **Advanced Rules Engine Implementation**
   - `AdvancedDiagnosticRulesEngine` class complete
   - All condition evaluators implemented and tested
   - Confidence scoring and evidence generation working

3. **Backtest Validation**
   - Advanced rules tested against known failures
   - Detection rate calculated (target: ≥2 additional detections)
   - Advance warning measured (target: ≥3 days mean)
   - Incremental value documented

4. **Local Execution Script**
   - `run_advanced_diagnostic_rules.py` working
   - Can be run manually on command line
   - Outputs saved to correct partitions

### Important Deliverables (Should-Have)

5. **Rule Performance Report**
   - Which rules fire most frequently?
   - Which rules have highest precision?
   - Recommendations for tuning

6. **Integration with Aggregation**
   - Phase 3 aggregation consumes advanced rule results
   - System/Unit health scores reflect advanced rule alerts

### Nice-to-Have Deliverables

7. **Rule Tuning Guide**
   - How to adjust thresholds
   - How to add new rules
   - Common pitfalls to avoid

8. **Visual Analysis**
   - Plots showing rule firing patterns
   - Comparison of basic vs. advanced rules

---

## 🏆 Success Criteria

### Functional Success

- [ ] All 5-8 advanced rules implemented and tested
- [ ] Rules execute without errors on full fleet
- [ ] Output schema matches TechniqueResult format
- [ ] Results stored in correct Parquet partitions

### Detection Performance

- [ ] Advanced rules detect ≥2 failures missed by Phase 2 techniques (or N/A if Phase 2 already caught all)
- [ ] Mean advance warning ≥3 days
- [ ] False positive rate ≤20% (sampled validation)
- [ ] Confidence scores correlate with data quality

### Explainability

- [ ] Every rule has clear natural language description
- [ ] Evidence dictionary traces to specific signals and conditions
- [ ] Maintenance teams can understand why rule fired

### Integration

- [ ] Advanced rule results feed into Phase 3 aggregation
- [ ] System/Unit health scores updated correctly
- [ ] Can run manually via command line

---

## 💻 Local Execution Guide

### Setup Requirements

**Python Environment**:
```bash
# Ensure dependencies installed
pip install pandas numpy pyyaml scipy
```

**Data Prerequisites**:
- Phase 2 technique results available (threshold, trend)
- Silver telemetry data for past 30 days
- Signal registry and technique config loaded

### Running Advanced Diagnostic Rules

**Daily Execution** (run after Phase 2 completes):

```bash
# Navigate to project root
cd c:\Users\patri\Coddi\Proyectos\telemetry_dashboard

# Run for specific date and client
python src/runners/run_advanced_diagnostic_rules.py \
  --date 2026-05-28 \
  --client CDA \
  --output data/telemetry/analytical_results/technique_results/advanced_diagnostic_rules/

# Run for all clients
python src/runners/run_advanced_diagnostic_rules.py \
  --date 2026-05-28 \
  --all-clients \
  --output data/telemetry/analytical_results/technique_results/advanced_diagnostic_rules/
```

**Backtest Execution** (validate against known failures):

```bash
python scripts/backtest_advanced_rules.py \
  --known-events data/validation/known_events.csv \
  --start-date 2025-11-01 \
  --end-date 2026-05-01 \
  --output data/validation/advanced_rules_backtest.csv
```

**Check Results**:

```bash
# View rule firing summary
python scripts/summarize_rule_results.py \
  --input data/telemetry/analytical_results/technique_results/advanced_diagnostic_rules/year=2026/month=05/ \
  --output-format markdown

# Check which units have multiple rules firing
python scripts/identify_high_priority_units.py \
  --date 2026-05-28 \
  --min-rules 2
```

### Expected Output Files

After execution:
```
data/telemetry/analytical_results/technique_results/advanced_diagnostic_rules/
  year=2026/
    month=05/
      day=28/
        client=CDA/
          part-0.parquet  (contains TechniqueResults for all units)
```

Each Parquet file contains:
- `unit_id`
- `timestamp`
- `technique_name`: "advanced_diagnostic_rules"
- `risk_score`: 0-100
- `confidence_score`: 0-100
- `status`: "Normal" / "Alerta" / "Anormal"
- `evidence`: JSON with rule_id, contributing_signals, conditions_met

### Troubleshooting

**Issue**: Rule doesn't fire when expected
- Check signal data availability (coverage >80%?)
- Verify thresholds (too strict?)
- Check temporal conditions (requires N consecutive days?)

**Issue**: Too many false positives
- Increase confidence minimum (default: 70)
- Tighten thresholds (e.g., P95 → P97)
- Add additional conditions (AND logic)

**Issue**: Results not appearing in aggregation
- Verify Parquet partitioning is correct
- Check schema version matches expected
- Ensure Phase 3 aggregation reads advanced_diagnostic_rules/ directory

---

## 📝 Implementation Notes

### Day 37 Notes

**Date**: ___________  
**Developer**: ___________

**Work Completed**:
- 
- 
- 

**Decisions Made**:
- 
- 

**Blockers/Issues**:
- 
- 

**Next Steps**:
- 
- 

---

### Day 38 Notes

**Date**: ___________  
**Developer**: ___________

**Work Completed**:
- 
- 
- 

**Decisions Made**:
- 
- 

**Blockers/Issues**:
- 
- 

**Next Steps**:
- 
- 

---

### Day 39 Notes

**Date**: ___________  
**Developer**: ___________

**Work Completed**:
- 
- 
- 

**Decisions Made**:
- 
- 

**Blockers/Issues**:
- 
- 

**Next Steps**:
- 
- 

---

## 🔄 Phase Retrospective

**Completion Date**: ___________

### What Went Well
- 
- 
- 

### What Didn't Go Well
- 
- 

### Lessons Learned
- 
- 

### Recommendations for Next Phase (Phase 6: Peer Deviation)
- 
- 

---

## 📊 Validation Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Rules implemented | 5-8 | ___ | ⏳ |
| Incremental detections | ≥2 | ___ | ⏳ |
| Mean advance warning | ≥3 days | ___ | ⏳ |
| False positive rate | ≤20% | ___ | ⏳ |
| Execution time (full fleet) | <30 min | ___ | ⏳ |

**Overall Phase 5 Status**: ⏳ Not Started

---

**Next Phase**: [Phase 6: Peer Deviation Analysis](implementation_phase_6_peer_deviation.md)
