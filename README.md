# Finance Data Platform

A personal finance data platform built on a modern data stack.

Pulls daily stock prices, transforms the data with dbt, and uses the Claude API 
to answer questions about the portfolio against live data.

---

## What It Does

- Fetches daily prices for 560+ stocks from Polygon.io and loads them into Supabase
- dbt models clean and transform the raw data into portfolio-level metrics
- Claude API portfolio analyzer uses tool use to answer real questions: 
  "Why is my portfolio down today?" "What's my biggest risk?"
- GitHub Actions runs the price fetch automatically every weekday at market close

---

## Stack

| Layer | Tool |
|-------|------|
| Data source | Polygon.io |
| Database | Supabase (PostgreSQL) |
| Transformation | dbt |
| AI layer | Claude API with tool use |
| Automation | GitHub Actions |
| Language | Python |

---

## Status

Active build. Ingestion and dbt layer complete. Claude API analyzer in progress.


