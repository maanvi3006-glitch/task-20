# PlaceMux Workflow

This document describes the end-to-end workflow the College-Value
Dashboard implements, from raw synthetic data to the Streamlit UI.

## 1. Schema creation (`create_database.py`)

Creates 10 normalized tables in `placemux.db` with primary keys, foreign
keys, CHECK constraints, and indexes. Idempotent — safe to re-run.

## 2. Data generation (`generate_data.py`)

Generates realistic, internally-consistent CSVs in `data/` using Faker,
NumPy, and Pandas. Generation follows the natural placement funnel so
that every downstream table only references valid rows upstream of it:

```
colleges → students → companies → jobs → applications
    → interviews → offers → placements → payments → revenue_events
```

Funnel shrinkage is deliberate and tuned to be realistic: not every
application gets interviewed, not every interview passes, not every offer
is accepted, and not every accepted offer results in a confirmed join.
Denormalized convenience fields (`students.placement_status`,
`colleges.total_students`, `applications.status`) are back-filled at the
end of generation so they stay consistent with the funnel tables.

## 3. Loading (`load_data.py`)

Loads all 10 CSVs into `placemux.db` in dependency order (parents before
children), clearing existing rows first so re-runs are idempotent.

## 4. Validation (`validation.py`)

Runs a suite of data-quality checks — missing data, duplicate records,
invalid salary values, broken foreign keys, and business-rule sanity
checks (e.g. a placement can't precede its own offer) — and writes a
Markdown report to `docs/validation_report.md`.

## 5. Metrics (`metrics_engine.py`)

A `MetricsEngine` class wraps all KPI SQL so the dashboard layer never
writes SQL directly. Metrics are grouped into College, Company, Student,
and Revenue families, plus marketplace-wide executive/health metrics.

## 6. Dashboard (`dashboard.py`)

A six-page Streamlit app (Executive Summary, College, Company, Student,
Revenue, Marketplace Health) that calls `MetricsEngine` and renders
results with Plotly — KPI cards, line/bar/pie charts, funnels, heatmaps,
box plots, and scatter plots. Sidebar filters (college, department, batch
year, placement status, salary range) narrow the data shown across pages.

## 7. Integration (`integration.py`)

Orchestrates steps 1–5 as a single dry-run command, useful for CI or a
live demo: `python integration.py`. Pass `--skip-generation` to reuse
existing CSVs instead of regenerating them.
