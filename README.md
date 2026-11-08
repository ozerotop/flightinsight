# FlightInsight

FlightInsight is a portfolio analytics project for exploring
flight delays, cancellations, and airline punctuality.

## Business problem

Companies need historical flight reliability statistics
to make more informed business travel decisions.

The application will compare airlines, airports,
routes, and time intervals using real flight data.

## Data source

Bureau of Transportation Statistics (BTS), USA.

https://www.transtats.bts.gov/

Target period: January-March 2025.
Data availability and structure will be verified in Stage 2.

## Technology stack

- Python 3.11+
- PostgreSQL
- pandas and NumPy
- FastAPI
- Streamlit and Plotly
- Docker and Docker Compose
- pytest

## Architecture

BTS CSV -> Python ETL -> PostgreSQL -> FastAPI -> Streamlit

## Planned features

- Reliable CSV import and data validation
- Normalized relational database
- SQL analytics and KPI calculation
- REST API
- Interactive analytics dashboard
- Data filters and CSV export
- Automated tests

## Project status

Stage 1: Repository initialization.

The data pipeline, database, API, and dashboard
have not been implemented yet.

## Documentation

See docs/requirements.md for MVP requirements.

## Running the project

Startup instructions will be added after
the Docker configuration is implemented.