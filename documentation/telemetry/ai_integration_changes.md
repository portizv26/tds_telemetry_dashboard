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
| `comment` | string | AI-generated diagnostic (2-3 sentences) |
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
| `comment` | string | AI-generated system diagnosis |
| `signals_referenced` | string (JSON) | Signals discussed in the comment |
| `recommended_action` | string | Suggested maintenance action |
| `evaluation_timestamp` | datetime | When generated |
| `model_used` | string | LLM model identifier |

### Unit Comments Schema

| Column | Type | Description |
|--------|------|-------------|
| `unit` | string | Equipment identifier |
| `overall_status` | string | Unit overall status |
| `priority_score` | float64 | Fleet priority score |
| `comment` | string | Executive-level assessment |
| `systems_referenced` | string (JSON) | Systems discussed |
| `urgency` | string | Action timeline classification |
| `recommended_action` | string | Top-priority recommendation |
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
| Unit header AI comment | `unit_comments.parquet` | Structured comment with urgency indicator |
| System Risk Table | `system_comments.parquet` | Expandable row showing system-level AI diagnosis and recommended action |
| Signal detail cards | `signal_comments.parquet` | AI diagnosis shown above each signal's time series plot |

### Key Benefits for Dashboard

1. **Granularity**: Signal-level comments were previously absent — now each non-Normal signal has its own AI explanation visible in the detail view.

2. **Independence**: Comments are stored separately from health records, enabling:
   - Independent caching/refresh of comments vs. scores
   - Dashboard can show comments even if health records haven't refreshed
   - Historical comment comparison without parsing embedded fields

3. **Structured metadata**: The `urgency`, `recommended_action`, and `techniques_referenced` fields enable the dashboard to style and filter comments programmatically rather than treating them as opaque text.

4. **Bottom-up consistency**: Signal comments feed into system comments, which feed into unit comments. This ensures the hierarchy is internally consistent — a unit comment won't contradict its constituent system comments.

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
