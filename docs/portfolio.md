# FlightInsight — portfolio and interview notes

## Project overview

FlightInsight is a self-hosted historical flight reliability dashboard based on official U.S. BTS on-time data for January–March 2025 (1,645,503 records). It demonstrates an end-to-end pipeline: Python ETL, PostgreSQL, SQL analytics, FastAPI, and Streamlit/Plotly, deployed with Docker Compose.

**Problem:** Business-travel planners need comparable historical statistics on airline/airport punctuality, cancellations and time patterns. The app does not predict or guarantee individual flight outcomes.

## What the implementation demonstrates

- Data ingestion: official source ZIP files downloaded on demand, CSV inspected and streamed to PostgreSQL; original archives stay out of Git.
- Data modeling: normalized `airlines`, `airports`, `flights`, `import_batches` tables with foreign keys and relevant indexes.
- Reliability: validation, transactional month imports, deduplication, and import counts checked against source CSVs.
- SQL analytics: grouped counts, medians, trend windows, typed parameters, `EXPLAIN ANALYZE`, minimum sample sizes for rankings.
- API: read-only, documented FastAPI endpoints with validation and tests.
- UI: Streamlit/Plotly filters, multiple dashboards and CSV export via HTTP API.
- Reproducibility: Docker Compose, local-only credentials, cross-platform startup scripts, health checks.

## Resume-ready description (English)

**FlightInsight — Flight Reliability Analytics Platform** — Built an end-to-end Python/PostgreSQL analytics service for 1.64M real U.S. domestic flights. Implemented validated streaming ETL with repeat-import protection, relational schema and indexed SQL queries, read-only FastAPI, Streamlit/Plotly dashboards and Docker Compose deployment. Added unit/integration checks and reproducible startup scripts.

Use this description only if you personally understand the implementation and have verified it end-to-end.

## Interview questions to rehearse

**Why PostgreSQL?** A relational model gives explicit referential integrity and supports analytical SQL (aggregates, percentiles, CTEs, window functions) for this dataset.

**Why stream data instead of loading the entire dataset into pandas?** CSV streams reduce peak Python memory during import; PostgreSQL COPY supports bulk ingest efficiently.

**How are duplicates prevented?** The ETL checks source-file identity and relies on a unique scheduled-flight key; repeat runs should leave flight totals unchanged.

**Why exclude cancellations and diversions from the on-time denominator?** These don't have a comparable normal arrival-delay measurement. They are reported separately.

**What does the 19.69% delay rate mean?** Among 1,611,046 normally completed Q1 2025 arrivals, 317,266 arrived 15+ minutes late. This is historical descriptive statistics, not a forecast.

**Why is a full-table sequential scan sometimes appropriate?** With an unfiltered summary covering nearly every row, reading the table sequentially can outperform index navigation; plans must be measured with EXPLAIN ANALYZE, not guessed.

**How does a user run the application?** A Windows `.cmd` or Unix shell wrapper uses a temporary Python Docker container to create local credentials and download source ZIPs; Compose then starts PostgreSQL, imports data and runs the API and dashboard.

**What would you improve next?** Add optional materialized rollups/caching if measured query latency justifies it; consider additional quarters or reporting-airline names only after validating source mapping.
