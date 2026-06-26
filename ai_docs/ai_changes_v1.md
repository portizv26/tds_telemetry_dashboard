# AI Integration Changes — Summary

**Date**: June 2026  
**Scope**: New pipeline step, data contract additions, dashboard integration

---

## Overview

The **AI Diagnosis** step has been introduced as a separate, first-class pipeline phase between Aggregation (Phase 9) and the legacy LLM Explanations (Phase 11). It produces structured diagnostic comments at three hierarchical levels — Signal, System, and Unit — stored independently for dashboard consumption.

This replaces the previous approach where AI-generated text was embedded directly into `system_health.explanation` and `unit_health.executive_summary` fields.

---

## Data Contract Changes

### New Output Tables (Golden Layer)

Three new parquet files are produced per execution cycle:

| File | Location | Records |
|------|----------|---------|
| `signal_comments.parquet` | `golden/{client}/ai_comments/year=YYYY/week=WW/` | One per non-Normal (unit, signal) pair |
| `system_comments.parquet` | `golden/{client}/ai_comments/year=YYYY/week=WW/` | One per non-Normal (unit, system) pair |
| `unit_comments.parquet` | `golden/{client}/ai_comments/year=YYYY/week=WW/` | One per non-Normal unit |

### Signal Comments Schema

| Column | Type | Description |
|--------|------|-------------|
| `unit` | string | Equipment identifier |
| `signal` | string | Signal name |
| `system` | string | System grouping |
| `status` | string | Worst status across techniques for this signal |
| `risk_score` | float64 | Max risk score across techniques |
| `description` | string | Brief summary of what was detected (~20 words, Spanish) |
| `explaining` | string | Detailed explanation of findings and relevance (2-4 sentences, Spanish) |
| `techniques_referenced` | string (JSON) | Which techniques informed the diagnosis |
| `evaluation_timestamp` | datetime | When generated |
| `model_used` | string | LLM model identifier |

### System Comments Schema

| Column | Type | Description |
|--------|------|-------------|
| `unit` | string | Equipment identifier |
| `system` | string | System name |
| `system_status` | string | System health status |
| `system_score` | float64 | Aggregated system score |
| `description` | string | Brief summary of system condition (~20 words, Spanish) |
| `explaining` | string | Detailed system diagnosis with signal references (2-4 sentences, Spanish) |
| `signals_referenced` | string (JSON) | Signals discussed in the comment |
| `recommended_action` | string | Suggested maintenance action (Spanish) |
| `evaluation_timestamp` | datetime | When generated |
| `model_used` | string | LLM model identifier |

### Unit Comments Schema

| Column | Type | Description |
|--------|------|-------------|
| `unit` | string | Equipment identifier |
| `overall_status` | string | Unit overall status |
| `priority_score` | float64 | Fleet priority score |
| `description` | string | Brief summary of unit condition (~20 words, Spanish) |
| `explaining` | string | Detailed executive assessment (2-4 sentences, Spanish) |
| `systems_referenced` | string (JSON) | Systems discussed |
| `urgency` | string | Action timeline classification |
| `recommended_action` | string | Top-priority recommendation (Spanish) |
| `evaluation_timestamp` | datetime | When generated |
| `model_used` | string | LLM model identifier |

### Urgency Classification

The `urgency` field maps priority scores to action timelines:

| Priority Score | Urgency | Meaning |
|----------------|---------|---------|
| < 20 | `routine` | No immediate action needed |
| 20–49 | `monitor` | Watch closely, schedule if worsening |
| 50–99 | `schedule_inspection` | Plan inspection within days |
| >= 100 | `immediate` | Requires immediate attention |

### Retention

AI Comments follow the same 2-year retention as system/unit health records.

---

## Dashboard Impact

### Page 1: Fleet Overview

| Widget | Before | After |
|--------|--------|-------|
| AI Assessment Table (F4) | Read from `unit_health.executive_summary` (embedded field) | Read from `ai_comments/unit_comments.parquet` (independent table) |

The dashboard now loads `unit_comments.parquet` directly, giving access to structured fields like `urgency` and `recommended_action` that enable color-coded severity borders and actionable callouts.

### Page 2: Unit Detail

| Section | Data Source | What's New |
|---------|-------------|------------|
| Unit header AI comment | `unit_comments.parquet` | `description` + `explaining` with urgency indicator |
| System Risk Table | `system_comments.parquet` | Expandable row showing `description`, `explaining`, and `recommended_action` |
| Signal detail cards | `signal_comments.parquet` | `description` + `explaining` shown above each signal's time series plot |

### Key Benefits for Dashboard

1. **Granularity**: Signal-level comments were previously absent — now each non-Normal signal has its own AI explanation visible in the detail view.

2. **Two-level text structure**: `description` gives a quick glance; `explaining` provides full context on demand — supporting progressive disclosure in the UI.

3. **Actions at the right level**: `recommended_action` is only generated at system and unit levels, where enough context exists to recommend meaningful actions.

4. **Spanish language**: All AI-generated text is in Spanish, matching the target audience (maintenance teams in Spanish-speaking operations).

5. **Independence**: Comments are stored separately from health records, enabling:
   - Independent caching/refresh of comments vs. scores
   - Dashboard can show comments even if health records haven't refreshed
   - Historical comment comparison without parsing embedded fields

6. **Bottom-up consistency**: Signal comments feed into system comments, which feed into unit comments. This ensures the hierarchy is internally consistent — a unit comment won't contradict its constituent system comments.

---

## Pipeline Changes

### New Phase

```
Phase 9:  Aggregation (unchanged)
Phase 10: AI Diagnosis (NEW) ← Signal → System → Unit comments
Phase 11: LLM Explanations (legacy, optional)
Phase 12: Persist outputs (now includes ai_comments/)
```

### Configuration

New `AICommentsConfig` in `settings.py`:
- `model`: gpt-4o-mini (default)
- `temperature`: 0.2 (lower than legacy LLM for more factual output)
- `max_tokens_signal/system/unit`: Token budgets per level
- `skip_normal`: Only diagnose non-Normal entities (cost control)
- `batch_size`: For future batching optimization

### Skip Flag

```python
pipeline.run(skip_ai_comments=True)  # Skip to save API costs during testing
```

---

## File Changes Summary

| File | Change |
|------|--------|
| `documentation/telemetry/telemetry_processing_documentation.md` | Added AI Diagnosis section, updated pipeline phases and diagrams |
| `documentation/telemetry/data_contracts.md` | Added 3 new output schemas (sections 6-8), validation classes, retention policy |
| `documentation/telemetry/dashboard_proposal.md` | Updated data sources, added AI Comments Integration section |
| `src/config/settings.py` | Added `AICommentsConfig` dataclass, wired into `PipelineConfig` |
| `src/techniques/ai_comments.py` | New module — `run_ai_diagnosis()` with 3-level generation |
| `src/pipeline.py` | Added Phase 10, `skip_ai_comments` flag, persistence logic |
