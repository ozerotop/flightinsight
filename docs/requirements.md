# FlightInsight — MVP requirements

## Purpose
Analyze historical flight punctuality and cancellations for travel planning.
Historical statistics do not guarantee the reliability of an individual flight.

## Source and scope
Official BTS Reporting Carrier On-Time Performance CSV for January–March 2025.
The three archives have been inspected: 1,645,503 flight rows, with consistent
columns and no rejected data rows in the tested source release.

## Functional requirements
- Download and validate the official CSV source data.
- Import idempotently into a normalized PostgreSQL relational database.
- Analyze delay rates (arrival 15+ minutes late), medians, average schedule
  deviations, cancellation/diversion rates, airlines, airports and trends.
- Filter by dates, airline and origin/destination, and allow CSV export.
- Serve analytics through validated FastAPI routes and Streamlit dashboard.
- Expose Swagger/OpenAPI documentation and reproducible Docker startup.

## Metric and data rules
- Arrival delay >= 15 minutes counts as delayed.
- Cancelled and diverted flights are excluded from the punctuality denominator.
- Cancellation percentages are computed from all scheduled flights.
- Average schedule deviation includes early arrivals as negative values.
- Mean/median lateness among delayed flights use the late-flight cohort only.
- Ranking results must display sample size, and delay causes may be NULL.
- All metrics must reconcile with the verified BTS import counts.

## Nonfunctional requirements
- No credentials or large BTS source ZIPs committed to Git.
- API accesses PostgreSQL through a restricted read-only role.
- Parameterized SQL and strict filter validation; no data mutation endpoints.
- Docker builds use non-root runtime users for application containers.
- Local-only ports by default; production hosting is out of scope.
- Repeatable startup and tests, without deleting existing PostgreSQL volumes.

## Release acceptance
- New clone starts with Docker Compose and internet access only.
- Health and API integration checks pass with 1,645,503 BTS flights.
- All tests pass after any dependency upgrade.
- Clean-clone execution must still be verified on an independent host.
