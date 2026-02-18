# Telemetry Dashboard - Visualization Proposal

**Version**: 1.0  
**Created**: February 18, 2026  
**Owner**: Patricio Ortiz - Data Team
**Purpose**: Define dashboard layout and visualizations for telemetry monitoring

---

## 📋 Table of Contents

1. [Dashboard Context](#dashboard-context)
2. [User Needs & Use Cases](#user-needs--use-cases)
3. [Data Update Frequency](#data-update-frequency)
4. [Dashboard Structure](#dashboard-structure)
5. [Visualization Catalog](#visualization-catalog)
6. [Layout Specifications](#layout-specifications)
7. [Interactive Features](#interactive-features)
8. [Evidence-Based Design](#evidence-based-design)

---

## 🎯 Dashboard Context

### Integration into Multi-Technical Platform

The Telemetry section fits into the broader **Monitoring Section** of the Multi-Technical Alerts Dashboard:

```
Dashboard
├── Overview Section
│   └── General (Fleet summary across all techniques)
├── Monitoring Section
│   ├── Alerts (Consolidated alerts) ← Already planned
│   ├── Telemetry ← THIS DASHBOARD
│   ├── Mantentions (Maintenance records)
│   └── Oil (Tribology analysis)
└── Limits Section
    ├── Oil Limits
    └── Telemetry Limits
```

### Telemetry-Specific Objectives

1. **Show current machine health** based on latest sensor analysis
2. **Provide evidence** when equipment is flagged as problematic
3. **Enable temporal analysis** to understand degradation patterns
4. **Support drill-down** from machine → component → signal level
5. **Contextualize with operational states** (Operational, Idle, Loaded, etc.)

---

## 👥 User Needs & Use Cases

### Primary Users

1. **Maintenance Supervisors**
   - Need: Quick overview of which units require attention
   - Goal: Prioritize maintenance activities

2. **Fleet Managers**
   - Need: Understand fleet-wide health trends
   - Goal: Optimize equipment utilization

3. **Field Technicians**
   - Need: Detailed diagnostic evidence for specific units
   - Goal: Identify root cause before intervention

### Key Use Cases

#### **Use Case 1: Daily Health Check**
> "Every morning, I need to see which trucks have telemetry alerts so I can schedule inspections."

**Solution**: Machine Status Table with severity sorting

---

#### **Use Case 2: Diagnostic Investigation**
> "Unit 247 is flagged as 'Anormal'. What sensors are causing this? Show me the evidence."

**Solution**: Component drill-down with signal trend visualization

---

#### **Use Case 3: Pattern Recognition**
> "Has Unit 247's engine coolant temperature been increasing over time, or is this a sudden spike?"

**Solution**: Multi-week trend comparison with baseline overlays

---

#### **Use Case 4: State-Based Validation**
> "The brakes are flagged as hot, but maybe that's normal when the truck is loaded going uphill?"

**Solution**: State-conditioned analysis with GPS context

---

## ⏱️ Data Update Frequency

### Execution Schedule
- **Analysis runs**: Every 8-12 hours (twice daily)
- **Data granularity**: Weekly parquet files (Week{WW}Year{YYYY}.parquet)
- **Output freshness**: `latest_sample_date` in machine_status.parquet shows last evaluation

### Dashboard Refresh Strategy
- **Real-time view**: Show results from most recent analysis run
- **Historical view**: Allow week-by-week comparisons
- **Status indicator**: Display "Last Updated: {timestamp}" prominently

---

## 🏗️ Dashboard Structure

### Proposed Layout: Three-Tab Design

The Telemetry subsection should have **three tabs** to support different analysis depths:

```
Monitoring > Telemetry
├── Tab 1: Machine Status (Overview)
├── Tab 2: Component Analysis (Drill-down)
└── Tab 3: Signal Trends (Evidence)
```

---

## 📊 Visualization Catalog

Below are **8 key visualizations** designed to address user needs effectively.

---

### **Visualization 1: Machine Status Table**

**Purpose**: Overview of all monitored units with current health grades

**Visualization Type**: Interactive DataTable (Dash AG Grid or DataTable)

**Columns**:
| Column | Type | Description |
|--------|------|-------------|
| Unit | String | Equipment identifier |
| Overall Status | Badge | Normal (🟢), Alerta (🟡), Anormal (🔴) |
| Machine Score | Number | Total criticality score |
| Priority Score | Number | Maintenance priority (higher = worse) |
| Last Sample | Datetime | When last evaluated |
| Critical Components | String | List of components in Alerta/Anormal |
| Action | Button | "View Details" link to Tab 2 |

**Features**:
- ✅ Sortable by any column (default: Priority Score descending)
- ✅ Filterable by status
- ✅ Color-coded badges (green/yellow/red)
- ✅ Clickable rows navigate to drill-down

**Placement**: Tab 1 - Top section

**Why this works**: Immediate actionable overview, prioritizes worst units

---

### **Visualization 2: Fleet Health Sunburst Chart**

**Purpose**: Hierarchical view of fleet health: Fleet → Machines → Components

**Visualization Type**: Plotly Sunburst (or Treemap as alternative)

**Hierarchy**:
```
Fleet (Root)
├── Normal Units
│   ├── Unit 101
│   │   ├── Motor (Normal)
│   │   ├── Brakes (Normal)
│   │   └── ...
├── Alerta Units
│   ├── Unit 247
│   │   ├── Motor (Anormal) ← Large slice
│   │   ├── Brakes (Alerta)
│   │   └── ...
└── Anormal Units
    └── Unit 312
        ├── Powertrain (Anormal)
        └── ...
```

**Color Scheme**:
- Green: Normal
- Yellow: Alerta
- Red: Anormal
- Size: Proportional to priority score

**Interactions**:
- Click to filter dashboard to selected unit/component

**Placement**: Tab 1 - Middle section

**Why this works**: Intuitive visual hierarchy, shows fleet composition at-a-glance

---

### **Visualization 3: Component Heatmap (Per Unit)**

**Purpose**: Show which components are problematic across the fleet

**Visualization Type**: Plotly Heatmap

**Axes**:
- **Y-axis**: Units (one row per unit)
- **X-axis**: Components (Motor, Brakes, Powertrain, Steering)
- **Color**: Component status (Green/Yellow/Red)
- **Hover**: Show component score + grade

**Example**:
```
         Motor  Brakes  Powertrain  Steering
Unit 101  🟢     🟢      🟢          🟢
Unit 247  🔴     🟡      🟢          🟢
Unit 312  🟢     🟢      🔴          🟡
```

**Interactions**:
- Click cell to navigate to Tab 2 filtered for that unit/component

**Placement**: Tab 1 - Bottom section

**Why this works**: Easy to spot patterns (e.g., "All units have brake issues lately")

---

### **Visualization 4: Week-over-Week Boxplot Comparison** ⭐

**Purpose**: Compare current week sensor distributions against historical baseline

**Visualization Type**: Plotly Box Plot (grouped)

**Design**:
- **X-axis**: Sensor signals (grouped by component)
- **Y-axis**: Sensor value
- **Boxes**: 
  - **Baseline box** (gray): Historical baseline (P25, median, P75 from past 4-8 weeks)
  - **Current week box** (blue): Current week distribution
  - **Outliers**: Red dots for Anormal readings, yellow for Alerta

**Example for Motor Component**:
```
EngCoolTemp    EngOilPres    EngSpd       LtExhTemp
  📦📦          📦📦          📦📦         📦📦
  gray blue     gray blue     gray blue    gray blue
   ↑             ↑             ↑            ↑
  Baseline    Current       Baseline     Current
```

**Interactions**:
- Click signal to load Time Series Trend (Viz 5)

**Placement**: Tab 2 - Top section (filter by unit + component)

**Why this works**: 
- ✅ **This is your original idea enhanced!**
- ✅ Immediately shows "is current behavior normal?"
- ✅ Statistical rigor with visual clarity
- ✅ Validates grading logic visually

---

### **Visualization 5: Signal Time Series with Baseline Bands**

**Purpose**: Show detailed sensor behavior over time with grading thresholds

**Visualization Type**: Plotly Line Chart with filled areas

**Design**:
- **X-axis**: Time (datetime)
- **Y-axis**: Sensor value
- **Visual layers**:
  1. **Background bands**:
     - Green zone: P5 - P95 (Normal range)
     - Yellow zones: P1-P5 and P95-P99 (Alerta range)
     - Red zones: <P1 and >P99 (Anormal range)
  2. **Line plot**: Actual sensor readings (colored by grade)
  3. **Median line**: Baseline P50 (dashed gray)
  4. **Annotations**: Mark points where grade changes

**Time Ranges**:
- Default: Current week
- Options: Last 2 weeks, Last 4 weeks, Last 8 weeks

**Interactions**:
- Zoom/pan
- Hover for exact values + grade
- Toggle baseline visibility

**Placement**: Tab 3 - Main section (filter by unit + signal)

**Why this works**: 
- ✅ **Gold standard for evidence**
- ✅ Shows why a signal was flagged
- ✅ Temporal context reveals trends
- ✅ Baseline bands justify grading decisions

---

### **Visualization 6: Operational State Timeline**

**Purpose**: Show equipment operational states alongside sensor trends

**Visualization Type**: Plotly Gantt Chart or Timeline

**Design**:
- **X-axis**: Time
- **Y-axis**: State categories
- **Bars**: 
  - Estado (Operational state)
  - EstadoMaquina (Machine state)
  - EstadoCarga (Load state)
- **Color-coded states**:
  - Operacional: Blue
  - Ralenti: Gray
  - Cargado: Orange
  - Descargado: Light blue

**Alignment**: Place directly above/below Visualization 5 (Time Series)

**Placement**: Tab 3 - Above time series chart

**Why this works**:
- ✅ **Critical context**: "Sensor is high because truck was loaded uphill"
- ✅ Validates state-conditioned analysis
- ✅ Explains false positives

---

### **Visualization 7: GPS Route Map with Alert Overlays**

**Purpose**: Spatial context for alerts (where did issues occur?)

**Visualization Type**: Plotly Scattermapbox

**Design**:
- **Base layer**: Satellite or terrain map
- **Route line**: GPS trajectory (GPSLat, GPSLon) colored by time
- **Alert markers**: 
  - 🟡 Yellow pins: Alerta readings
  - 🔴 Red pins: Anormal readings
- **Hover info**: 
  - Time
  - GPS elevation
  - Sensor values at that location
  - State (Operacional, Cargado, etc.)

**Interactions**:
- Click marker to jump to that timestamp in Time Series (Viz 5)
- Filter by date range

**Placement**: Tab 3 - Bottom section (optional, show if GPS data available)

**Why this works**:
- ✅ "Brakes always overheat on the steep descent road"
- ✅ Identifies location-specific issues
- ✅ Correlates terrain (GPSElevation) with sensor behavior

---

### **Visualization 8: Component Status Radar Chart**

**Purpose**: Multi-dimensional view of component health

**Visualization Type**: Plotly Radar Chart

**Design**:
- **Axes**: One per component (Motor, Brakes, Powertrain, Steering)
- **Values**: Normalized component scores (0-10 scale)
- **Plots**:
  - Current week (solid line)
  - Previous week (dashed line)
  - Baseline (faded line)

**Color**: 
- Green area: All normal
- Yellow/Red shading: Problem zones

**Placement**: Tab 2 - Middle section (filter by unit)

**Why this works**:
- ✅ Holistic unit health snapshot
- ✅ Easy to see which component is worst
- ✅ Week-over-week comparison

---

## 🎨 Layout Specifications

### **TAB 1: Machine Status (Fleet Overview)**

**Purpose**: High-level fleet health monitoring

```
┌────────────────────────────────────────────────────────────┐
│ 🔧 Telemetry Monitoring - Machine Status                  │
│ Last Updated: Feb 18, 2026 14:30 | Refresh Data ↻        │
├────────────────────────────────────────────────────────────┤
│ FILTERS:                                                   │
│ [All Units ▼] [All Status ▼] [Week Selector ▼]           │
├────────────────────────────────────────────────────────────┤
│ KPI CARDS:                                                 │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │
│ │ Total   │ │ Normal  │ │ Alerta  │ │ Anormal │         │
│ │ Units   │ │ Units   │ │ Units   │ │ Units   │         │
│ │   45    │ │   38    │ │    5    │ │    2    │         │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘         │
├────────────────────────────────────────────────────────────┤
│ VISUALIZATION 1: Machine Status Table                     │
│ [Sortable, filterable, clickable DataTable]              │
│ Shows all units with status, scores, critical comps      │
├────────────────────────────────────────────────────────────┤
│ LEFT (60%):              │ RIGHT (40%):                   │
│ VISUALIZATION 2:         │ VISUALIZATION 3:              │
│ Fleet Health Sunburst    │ Component Heatmap             │
│ [Interactive sunburst]   │ [Unit x Component heatmap]    │
└────────────────────────────────────────────────────────────┘
```

**User Flow**:
1. View KPIs → Understand fleet health at-a-glance
2. Scan table → Identify priority units
3. Click "View Details" → Navigate to Tab 2

---

### **TAB 2: Component Analysis (Drill-Down)**

**Purpose**: Detailed component-level analysis for selected unit

```
┌────────────────────────────────────────────────────────────┐
│ 🔍 Component Analysis - Unit 247                          │
│ Last Sample: Feb 18, 2026 12:00 | Status: 🔴 Anormal     │
├────────────────────────────────────────────────────────────┤
│ FILTERS:                                                   │
│ [Unit Selector ▼] [Component Selector ▼] [Week Range ▼]  │
├────────────────────────────────────────────────────────────┤
│ COMPONENT SUMMARY CARDS:                                   │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │
│ │ Motor   │ │ Brakes  │ │Powertrain││Steering│         │
│ │🔴Anormal│ │🟡Alerta  │ │🟢Normal  │ │🟢Normal │         │
│ │Score: 25│ │Score: 10│ │Score: 0  │ │Score: 0│         │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘         │
├────────────────────────────────────────────────────────────┤
│ VISUALIZATION 8: Component Radar Chart                    │
│ [Shows all 4 components on radar, current vs baseline]   │
├────────────────────────────────────────────────────────────┤
│ VISUALIZATION 4: Week-over-Week Boxplot Comparison ⭐     │
│ [Boxplots for all signals in selected component]         │
│ Showing: Motor Component (10 signals)                    │
│ Gray boxes = Baseline, Blue boxes = Current week         │
│ Red/Yellow outliers marked                                │
├────────────────────────────────────────────────────────────┤
│ SIGNAL DETAILS TABLE:                                      │
│ [List signals with grade, score, baseline stats]         │
│ Click signal to view time series in Tab 3 →              │
└────────────────────────────────────────────────────────────┘
```

**User Flow**:
1. Select unit + component
2. View radar chart → Understand component health distribution
3. Inspect boxplot → See which signals are abnormal
4. Click signal → Navigate to Tab 3 for evidence

---

### **TAB 3: Signal Trends (Evidence)**

**Purpose**: Detailed time series evidence for diagnostic validation

```
┌────────────────────────────────────────────────────────────┐
│ 📈 Signal Trends - Unit 247 - EngCoolTemp                │
│ Grade: 🔴 Anormal | Score: 10 | Component: Motor         │
├────────────────────────────────────────────────────────────┤
│ FILTERS:                                                   │
│ [Unit ▼] [Signal ▼] [Time Range: Last 4 weeks ▼]        │
├────────────────────────────────────────────────────────────┤
│ VISUALIZATION 6: Operational State Timeline               │
│ [Gantt chart showing Estado, EstadoMaquina, EstadoCarga] │
├────────────────────────────────────────────────────────────┤
│ VISUALIZATION 5: Signal Time Series with Baseline Bands ⭐│
│ [Line chart with green/yellow/red background zones]      │
│ - Green zone: Normal range (P5-P95)                      │
│ - Yellow zones: Alerta range (P1-P5, P95-P99)           │
│ - Red zones: Anormal (<P1, >P99)                         │
│ - Median baseline: Dashed gray line                      │
│ - Actual values: Colored line (green/yellow/red)        │
├────────────────────────────────────────────────────────────┤
│ CONTEXT KPIs (when signal flagged):                       │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │
│ │ Max Value    │ │ Baseline P95 │ │ Exceedances  │      │
│ │   103.5°C    │ │    95.2°C    │ │    47 times  │      │
│ └──────────────┘ └──────────────┘ └──────────────┘      │
├────────────────────────────────────────────────────────────┤
│ VISUALIZATION 7: GPS Route Map (Optional)                 │
│ [Map showing route with alert markers]                   │
│ Red pins where EngCoolTemp exceeded Anormal threshold    │
└────────────────────────────────────────────────────────────┘
```

**User Flow**:
1. Select signal to investigate
2. View state timeline → Understand operational context
3. Inspect time series → See when/how signal exceeded thresholds
4. Check GPS map → Identify if location-specific
5. Export evidence for maintenance report

---

## 🔄 Interactive Features

### Cross-Tab Navigation

**Enable seamless drill-down flow**:
1. **Tab 1 → Tab 2**: Click unit in table/chart → Navigate to Tab 2 filtered for that unit
2. **Tab 2 → Tab 3**: Click signal in boxplot/table → Navigate to Tab 3 filtered for that signal
3. **Tab 3 → Tab 1**: "Back to Overview" button

### Filtering System

**Global Filters** (persist across tabs):
- **Unit Selector**: Dropdown or multi-select
- **Date Range**: Week selector or date range picker
- **Status Filter**: All, Normal, Alerta, Anormal

**Tab-Specific Filters**:
- Tab 2: Component selector
- Tab 3: Signal selector, State filter

### Data Export

**Enable report generation**:
- Export Machine Status Table → Excel/CSV
- Export Signal Time Series → CSV (with grades)
- Export Evidence Plot → PNG/PDF for maintenance reports

---

## 📐 Evidence-Based Design Principles

### Why This Layout Works

#### **1. Progressive Disclosure**
- Tab 1: Overview (what's wrong?)
- Tab 2: Diagnosis (which component?)
- Tab 3: Evidence (why is it wrong?)

**Benefit**: Users don't get overwhelmed, can drill down as needed

---

#### **2. Multiple Views of Same Data**

The same grading logic is visualized in complementary ways:
- **Table**: Precise numbers for sorting/filtering
- **Sunburst**: Hierarchical relationships
- **Heatmap**: Pattern recognition across fleet
- **Boxplot**: Statistical validity
- **Time series**: Temporal evidence

**Benefit**: Different users prefer different views; all needs covered

---

#### **3. Baseline Comparisons are Everywhere**

Every visualization shows current vs. historical:
- Boxplot: Current week vs. baseline weeks
- Time series: Actual vs. median + bands
- Radar: Current vs. previous week

**Benefit**: **Always answering "Is this normal?"** ← Core user question

---

#### **4. Context is King**

Evidence is never shown in isolation:
- Time series + State timeline
- Time series + GPS map
- Boxplot + Component grouping

**Benefit**: Prevents false conclusions (e.g., "High temp, but truck was fully loaded")

---

#### **5. Actionable Design**

Every visualization enables action:
- Status table → Prioritized maintenance list
- Heatmap → Identify fleet-wide component issues
- Time series → Confirm diagnosis before repair

**Benefit**: Dashboard drives decisions, not just displays data

---

## 🎨 Visual Design Consistency

### Color Palette

**Status Colors** (use everywhere):
- 🟢 Normal: `#28a745` (green)
- 🟡 Alerta: `#ffc107` (amber)
- 🔴 Anormal: `#dc3545` (red)
- ⚪ Unknown/No Data: `#6c757d` (gray)

**Chart Colors**:
- Baseline histograms: `#adb5bd` (light gray)
- Current data: `#007bff` (blue)
- Thresholds: Dashed `#343a40` (dark gray)

### Typography

- **KPI Numbers**: 36px, bold
- **Section Headers**: 20px, semi-bold
- **Table Text**: 14px, regular
- **Hover Labels**: 12px, regular

### Layout Consistency

- Filters always at top
- KPIs below filters (horizontal cards)
- Main visualizations below KPIs
- Supporting visualizations below main charts

---

## 🚀 Implementation Priorities

### Phase 1: MVP (Essential Visualizations)

**Must-Have for Launch**:
1. ✅ Visualization 1: Machine Status Table
2. ✅ Visualization 3: Component Heatmap
3. ✅ Visualization 4: Week-over-Week Boxplot ⭐
4. ✅ Visualization 5: Signal Time Series with Bands ⭐

**Rationale**: Covers overview → drill-down → evidence flow

---

### Phase 2: Enhancements

**Nice-to-Have**:
5. ✅ Visualization 2: Fleet Sunburst
6. ✅ Visualization 6: State Timeline
7. ✅ Visualization 8: Radar Chart

**Rationale**: Improves UX and pattern recognition

---

### Phase 3: Advanced

**Optional**:
8. ✅ Visualization 7: GPS Map

**Rationale**: High value but requires additional GPS data processing

---

## 📊 Data Requirements Summary

### Tab 1 (Machine Status)
**Data Source**: `machine_status.parquet`
- Columns needed: All (unit_id, overall_status, machine_score, priority_score, component_details, etc.)

### Tab 2 (Component Analysis)
**Data Source**: `classified.parquet`
- Columns needed: unit, date, component, component_status, signals_evaluation

### Tab 3 (Signal Trends)
**Data Sources**: 
1. `Telemetry_Wide_With_States/Week{WW}Year{YYYY}.parquet` (raw sensor data)
2. `classified.parquet` (grades)
3. Baseline statistics (computed from historical weeks)

**Baseline Calculation**:
- Pre-compute percentiles (P1, P5, P25, P50, P75, P95, P99) per signal + state
- Store in `signal_baselines.parquet` for fast loading

---

## 📚 Success Metrics

### User Engagement
- ✅ 80%+ of users access Tab 3 (evidence) when investigating Anormal units
- ✅ Average time to diagnosis < 5 minutes

### Technical Performance
- ✅ Tab load time < 2 seconds
- ✅ Chart rendering < 1 second
- ✅ Smooth interactions (no lag)

### Business Impact
- ✅ 90% of flagged Anormal cases confirmed by field inspection
- ✅ False positive rate < 15%

---

## 🔗 Related Documentation

- **Project Overview**: `project_overview.md` - Analysis method details
- **Implementation Plan**: `implementation_plan.md` - Build steps
- **Data Contracts**: Define exact schema for machine_status.parquet and classified.parquet

---

**Document Status**: ✅ Ready for Review  
**Recommended Visualizations**: Start with Viz 1, 3, 4, 5 (MVP)  
**Key Innovation**: Boxplot + Time Series with baseline bands = statistical rigor + visual evidence
