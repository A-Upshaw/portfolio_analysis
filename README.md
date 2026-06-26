# Finance Data Platform

A personal finance data platform built on a modern data stack.

Pulls daily stock prices, transforms the data with dbt, serves it through a FastAPI 
layer, and renders a live portfolio dashboard. Claude API analyzer answers questions 
against live data using tool use.

---

## What It Does

- Fetches daily prices for 560+ stocks from Polygon.io and loads them into Supabase
- dbt staging and mart models clean and transform the raw data into portfolio metrics
- FastAPI serves the transformed data including a SPY benchmark endpoint
- Streamlit dashboard calls the API to render live portfolio positions and KPIs
- Claude API portfolio analyzer uses tool use to answer questions against live data
- GitHub Actions runs the price fetch automatically every weekday at market close

---

## Stack

| Layer | Tool |
|-------|------|
| Data source | Polygon.io |
| Database | Supabase (PostgreSQL) |
| Transformation | dbt |
| API | FastAPI |
| Dashboard | Streamlit |
| AI layer | Claude API with tool use |
| Automation | GitHub Actions |
| Language | Python |

---

## Project Structure

```
finance-data-platform/
├── ingestion/        # Daily price fetcher and backfill script
├── dbt/              # Staging models and portfolio marts
├── api/              # FastAPI service
├── dashboard/        # Streamlit portfolio dashboard
├── analysis/         # Claude API portfolio analyzer
├── schema/           # Database schema
└── .github/
    └── workflows/    # Automated daily pipeline
```

---

## Status

Active build. Ingestion, dbt layer, FastAPI, and dashboard complete. 
Claude API analyzer in progress.



