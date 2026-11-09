"""FlightInsight: interactive dashboard over the public read-only FastAPI API.

Run via Docker Compose. No direct PostgreSQL connection or credentials.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from client import FlightInsightAPIError, fetch_json
from helpers import (
    chart_pairs,
    count_text,
    export_csv,
    minutes_text,
    percent_text,
    safe_number,
)


START_DATE = date(2025, 1, 1)
END_DATE = date(2025, 3, 31)
API_BASE_URL = os.environ.get("API_BASE_URL", "http://api:8000").rstrip("/")
PRIMARY = "#087E8B"
SECONDARY = "#EF8B45"
MIDNIGHT = "#14253E"
WEEKDAYS = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}
CANCELLATION_CODES = {
    "A": "Carrier",
    "B": "Weather",
    "C": "National Airspace System",
    "D": "Security",
    "UNKNOWN": "Unknown",
}
CAUSE_LABELS = {
    "carrier": "Carrier",
    "weather": "Weather",
    "nas": "Air traffic system",
    "security": "Security",
    "late_aircraft": "Late inbound aircraft",
}


st.set_page_config(
    page_title="FlightInsight | Flight reliability analytics",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .stApp {background: #F5F8FC;}
      [data-testid="stSidebar"] {background: #EAF1F7; border-right: 1px solid #DBE6EE;}
      .block-container {padding-top: 1.6rem; max-width: 1400px; padding-bottom: 3.5rem;}
      .hero {border-radius: 20px; padding: 27px 32px; margin-bottom: 24px;
        background: linear-gradient(112deg, #122540 0%, #163F52 61%, #087E8B 100%);
        color: #FFFFFF; box-shadow: 0 12px 30px rgba(14, 39, 66, 0.1);}
      .hero .eyebrow {font-size: 11px; letter-spacing: 2px; font-weight: 700;
        text-transform: uppercase; color: #9CE9DF; margin-bottom: 6px;}
      .hero h1 {font-size: 34px; margin: 0 0 8px; color: #FFFFFF; font-weight: 730;}
      .hero p {color: #D8E7EC; margin: 0; font-size: 14px; line-height: 1.65;}
      .section-kicker {text-transform: uppercase; letter-spacing: 1.5px;
        font-size: 12px; font-weight: 760; color: #087E8B; margin: 12px 0 4px;}
      div[data-testid="stMetric"] {background: #FFFFFF; border: 1px solid #E0E8F0;
        border-radius: 15px; padding: 17px 18px 13px; min-height: 135px;}
      div[data-testid="stMetricLabel"] {font-weight: 700; color: #51647A;}
      div[data-testid="stMetricValue"] {font-weight: 740; color: #14253E;}
      div[data-testid="stPlotlyChart"] {background: #FFFFFF; border: 1px solid #E0E8F0;
        border-radius: 15px; padding: 10px 12px;}
      [data-testid="stDataFrame"] {background: #FFFFFF; border-radius: 13px;}
      h2,h3 {color: #14253E; letter-spacing: -0.02em;}
      .muted {font-size: 12px; color: #60758D;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300, show_spinner=False)
def cached_get(base_url: str, path: str, params: tuple[tuple[str, str], ...]) -> Any:
    """A small cache avoids recomputing multi-million-row SQL on every UI rerun."""
    return fetch_json(base_url, path, dict(params))


def api(path: str, parameters: dict[str, Any] | None = None) -> Any:
    items = tuple(sorted((key, str(value)) for key, value in (parameters or {}).items() if value is not None and value != ""))
    return cached_get(API_BASE_URL, path, items)


def common_plot(fig: go.Figure, height: int = 370) -> go.Figure:
    fig.update_layout(
        template="plotly_white", height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFFFF",
        margin=dict(l=18, r=22, t=18, b=28),
        font=dict(family="Arial, sans-serif", color=MIDNIGHT, size=12),
        hovermode="x unified", legend=dict(orientation="h", y=1.12, x=0),
    )
    fig.update_xaxes(showgrid=False, linecolor="#D6E3ED", zeroline=False)
    fig.update_yaxes(gridcolor="#ECF1F6", zeroline=False)
    return fig


def csv_button(records: list[dict], filename: str, label: str = "Download CSV") -> None:
    if records:
        st.download_button(
            label=label, data=export_csv(records), file_name=filename,
            mime="text/csv", use_container_width=False,
        )


def as_table(rows: list[dict], columns: dict[str, str], key: str | None = None) -> None:
    if not rows:
        st.info("No records match the selected filters. Try a wider date range or different airport.")
        return
    frame = pd.DataFrame(rows)
    selected = [col for col in columns if col in frame.columns]
    st.dataframe(frame[selected].rename(columns=columns), hide_index=True, use_container_width=True, height=min(445, 45 + 35 * len(frame)), key=key)


def plot_rankings(rows: list[dict], key: str, label_field: str, caption: str, limit: int = 15) -> None:
    chosen = [row for row in rows if safe_number(row.get(key)) is not None][:limit]
    if not chosen:
        st.info("No eligible records for a ranking with the current minimum sample.")
        return
    names = [str(row.get(label_field, "")) for row in chosen][::-1]
    rates = [safe_number(row.get(key)) for row in chosen][::-1]
    labels = [count_text(row.get("arrival_sample", row.get("departure_sample"))) for row in chosen][::-1]
    fig = go.Figure(go.Bar(
        x=rates, y=names, orientation="h", marker_color=PRIMARY,
        text=[f"{value:.2f}%" for value in rates], textposition="outside",
        customdata=labels,
        hovertemplate="%{y}: %{x:.2f}% delayed<br>Valid sample: %{customdata}<extra></extra>",
    ))
    fig.update_layout(xaxis=dict(title="Delayed flights (%)", range=[0, max(5, max(rates) * 1.25)]),
                      yaxis=dict(title=""), showlegend=False)
    st.plotly_chart(common_plot(fig, max(330, 37 * len(chosen) + 90)), use_container_width=True)
    st.caption(caption)


def plot_trend(rows: list[dict]) -> None:
    dates, daily = chart_pairs(rows, "flight_date", "delayed_15_pct")
    _, weekly = chart_pairs(rows, "flight_date", "delayed_7d_pct")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=daily, name="Daily delayed rate", mode="lines",
                             line=dict(color="#9EB4C7", width=1.3), opacity=0.85,
                             hovertemplate="%{x}: %{y:.2f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=dates, y=weekly, name="7-day weighted rate", mode="lines",
                             line=dict(color=PRIMARY, width=3),
                             hovertemplate="%{x}: %{y:.2f}%<extra></extra>"))
    fig.update_layout(yaxis_title="Flights delayed 15+ min (%)", xaxis_title="Date")
    st.plotly_chart(common_plot(fig, 390), use_container_width=True)


def plot_volumes(rows: list[dict]) -> None:
    dates, total = chart_pairs(rows, "flight_date", "total_flights")
    _, late = chart_pairs(rows, "flight_date", "delayed_15_flights")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=dates, y=total, name="Scheduled flights", marker_color="#BCD7E2"))
    fig.add_trace(go.Bar(x=dates, y=late, name="Delayed arrivals", marker_color=SECONDARY))
    fig.update_layout(barmode="overlay", xaxis_title="Date", yaxis_title="Flight count")
    st.plotly_chart(common_plot(fig, 340), use_container_width=True)


def render_overview(filters: dict[str, Any], summary: dict[str, Any]) -> None:
    st.markdown('<div class="section-kicker">Flight performance</div>', unsafe_allow_html=True)
    st.subheader("At a glance")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total flights", count_text(summary.get("total_flights")))
    k2.metric("On-time arrivals", percent_text(summary.get("on_time_pct")), help="Arrivals less than 15 minutes late among normally completed flights")
    k3.metric("Delayed arrivals", percent_text(summary.get("delayed_15_pct")))
    k4.metric("Cancelled flights", percent_text(summary.get("cancelled_pct")))
    st.caption(
        f"Punctuality is based on {count_text(summary.get('arrival_sample'))} normal completed arrivals. "
        "Cancelled and diverted flights are excluded from the arrival punctuality denominator."
    )
    k5, k6, k7 = st.columns(3)
    k5.metric("Avg. schedule deviation", minutes_text(summary.get("avg_schedule_deviation_min")))
    k6.metric("Median schedule deviation", minutes_text(summary.get("median_schedule_deviation_min")))
    k7.metric("Avg. lateness of delayed flights", minutes_text(summary.get("avg_lateness_delayed_min")))
    st.caption("Negative deviation means an early arrival. Average lateness is calculated only for arrivals at least 15 minutes late.")
    st.markdown('<div class="section-kicker">Time series</div>', unsafe_allow_html=True)
    st.subheader("Delay trends")
    with st.spinner("Loading daily trends from API..."):
        rows = api("/api/v1/analytics/trends", filters)
    if not rows:
        st.info("No daily trend data for this selection.")
        return
    plot_trend(rows)
    st.subheader("Flight volumes")
    plot_volumes(rows)
    csv_button(rows, "flightinsight_daily_trends.csv", "Download daily trend CSV")


def render_airlines(filters: dict[str, Any]) -> None:
    st.markdown('<div class="section-kicker">Carriers</div>', unsafe_allow_html=True)
    st.subheader("Airline reliability")
    st.caption("Airlines are ordered by arrival delays of 15+ minutes (lower is better). Minimum sample is applied to normal completed arrivals.")
    with st.spinner("Ranking airlines..."):
        rows = api("/api/v1/analytics/airlines", {**filters, "limit": 500})
    if not rows:
        st.info("No airlines meet your filters and minimum sample. Lower the minimum sample to see smaller carriers.")
        return
    plot_rankings(rows, "delayed_15_pct", "airline_code", "Bars show arrival delay rates. Sample counts appear on hover.", limit=15)
    as_table(rows, {
        "airline_code": "Code", "airline_name": "Airline", "total_flights": "Flights",
        "arrival_sample": "Valid arrivals", "delayed_15_flights": "Delayed arrivals",
        "delayed_15_pct": "Delayed (%)", "cancelled_pct": "Cancelled (%)",
        "avg_schedule_deviation_min": "Avg deviation (min)",
    })
    csv_button(rows, "flightinsight_airlines.csv")


def render_airports(filters: dict[str, Any]) -> None:
    st.markdown('<div class="section-kicker">Airports</div>', unsafe_allow_html=True)
    st.subheader("Airport reliability")
    direction = st.radio("Compare airports by", ["Arrival", "Departure"], horizontal=True, key="airport_direction")
    with st.spinner("Ranking airports..."):
        rows = api("/api/v1/analytics/airports", {
            **filters, "direction": direction.lower(), "limit": 500,
        })
    if not rows:
        st.info("No airports meet the selected filters and minimum sample.")
        return
    msg = ("Arrival delays exclude cancelled/diverted flights."
           if direction == "Arrival" else
           "Departure delay rates use flights with recorded departure delay, excluding cancelled flights; diverted flights may contribute.")
    plot_rankings(rows, "delayed_15_pct", "airport_code", msg, limit=15)
    if direction == "Arrival":
        columns = {"airport_code": "Airport", "city": "City", "state": "State",
                   "scheduled_arrivals": "Scheduled arrivals", "arrival_sample": "Valid arrivals",
                   "delayed_15_arrivals": "Delayed arrivals", "delayed_15_pct": "Delayed (%)",
                   "avg_arrival_deviation_min": "Avg deviation (min)"}
    else:
        columns = {"airport_code": "Airport", "city": "City", "state": "State",
                   "scheduled_departures": "Scheduled departures", "departure_sample": "Valid departures",
                   "delayed_15_departures": "Delayed departures", "delayed_15_pct": "Delayed (%)",
                   "cancelled_pct": "Cancelled (%)", "avg_departure_deviation_min": "Avg deviation (min)"}
    as_table(rows, columns)
    csv_button(rows, f"flightinsight_airports_{direction.lower()}.csv")


def render_patterns(filters: dict[str, Any]) -> None:
    st.markdown('<div class="section-kicker">Calendar patterns</div>', unsafe_allow_html=True)
    st.subheader("When are flights delayed?")
    st.caption("Scheduled departure hours are local to the origin airport. Weekdays follow the flight date; times are not converted into one common timezone.")
    with st.spinner("Loading time-of-day and weekday reports..."):
        weekdays = api("/api/v1/analytics/delays", {**filters, "group_by": "weekday"})
        hours = api("/api/v1/analytics/delays", {**filters, "group_by": "hour"})
    left, right = st.columns([1, 1])
    with left:
        st.markdown("**By day of week**")
        if weekdays:
            x = [WEEKDAYS.get(row.get("weekday_iso"), "Unknown") for row in weekdays]
            y = [safe_number(row.get("delayed_15_pct")) for row in weekdays]
            fig = go.Figure(go.Bar(x=x, y=y, marker_color=PRIMARY,
                                    hovertemplate="%{x}: %{y:.2f}%<extra></extra>"))
            fig.update_layout(yaxis_title="Delayed arrivals (%)", xaxis_title="Weekday")
            st.plotly_chart(common_plot(fig, 365), use_container_width=True)
        else:
            st.info("No weekday data")
    with right:
        st.markdown("**By scheduled departure hour**")
        if hours:
            x = [row.get("origin_local_departure_hour") for row in hours]
            y = [safe_number(row.get("delayed_15_pct")) for row in hours]
            fig = go.Figure(go.Scatter(x=x, y=y, mode="lines+markers",
                                       line=dict(color=SECONDARY, width=3),
                                       hovertemplate="%{x}:00 — %{y:.2f}%<extra></extra>"))
            fig.update_layout(yaxis_title="Delayed arrivals (%)", xaxis_title="Local scheduled departure hour")
            fig.update_xaxes(dtick=2, range=[-0.4, 23.4])
            st.plotly_chart(common_plot(fig, 365), use_container_width=True)
        else:
            st.info("No hourly data")
    c1, c2 = st.columns(2)
    with c1:
        as_table(weekdays, {"weekday_iso": "ISO weekday", "total_flights": "Flights",
                            "arrival_sample": "Valid arrivals", "delayed_15_pct": "Delayed (%)"})
        csv_button(weekdays, "flightinsight_weekdays.csv", "Download weekday CSV")
    with c2:
        as_table(hours, {"origin_local_departure_hour": "Hour", "total_flights": "Flights",
                         "arrival_sample": "Valid arrivals", "delayed_15_pct": "Delayed (%)"})
        csv_button(hours, "flightinsight_hours.csv", "Download hourly CSV")


def render_disruptions(filters: dict[str, Any]) -> None:
    st.markdown('<div class="section-kicker">Disruptions</div>', unsafe_allow_html=True)
    st.subheader("Why flights are disrupted")
    with st.spinner("Loading cancellation and delay causes..."):
        cancellations = api("/api/v1/analytics/cancellations", filters)
        causes = api("/api/v1/analytics/delay-causes", filters)
    left, right = st.columns(2)
    with left:
        st.markdown("**Cancellation reasons**")
        if cancellations:
            labels = [CANCELLATION_CODES.get(row["cancellation_code"], row["cancellation_code"]) for row in cancellations]
            fig = go.Figure(go.Bar(x=labels, y=[row["cancelled_flights"] for row in cancellations],
                                    marker_color=SECONDARY, hovertemplate="%{x}: %{y:,} cancellations<extra></extra>"))
            fig.update_layout(yaxis_title="Cancelled flights", xaxis_title="Reason")
            st.plotly_chart(common_plot(fig, 360), use_container_width=True)
        else:
            st.info("No cancellations in the selected period.")
    with right:
        st.markdown("**Reported delay-cause minutes**")
        if causes:
            labels = [CAUSE_LABELS.get(row["reason"], row["reason"]) for row in causes]
            values = [safe_number(row.get("total_minutes")) or 0 for row in causes]
            fig = go.Figure(go.Bar(x=values[::-1], y=labels[::-1], orientation="h",
                                    marker_color=PRIMARY,
                                    hovertemplate="%{y}: %{x:,.0f} min<extra></extra>"))
            fig.update_layout(xaxis_title="Minutes reported", yaxis_title="")
            st.plotly_chart(common_plot(fig, 360), use_container_width=True)
        else:
            st.info("No reported delay causes for the current selection.")
    st.caption("Cause minutes describe BTS-reported contributing factors for flights arriving at least 15 minutes late, not every delayed minute on every flight.")
    c1, c2 = st.columns(2)
    with c1:
        as_table(cancellations, {"cancellation_code": "Reason code", "cancelled_flights": "Cancelled",
                                 "share_of_cancellations_pct": "Share of cancellations (%)"})
        csv_button(cancellations, "flightinsight_cancellations.csv", "Download cancellations CSV")
    with c2:
        as_table(causes, {"reason": "Cause", "total_minutes": "Reported minutes",
                          "reported_flights": "Records with cause", "share_of_reported_cause_minutes_pct": "Share of cause minutes (%)"})
        csv_button(causes, "flightinsight_delay_causes.csv", "Download causes CSV")


def main() -> None:
    st.markdown(
        """<div class="hero"><div class="eyebrow">United States · BTS · Q1 2025</div>
          <h1>✈ FlightInsight</h1><p>Explore real flight reliability data. Compare airlines and airports,
          discover delay patterns, and make better-informed travel decisions.</p></div>""",
        unsafe_allow_html=True,
    )
    try:
        with st.spinner("Connecting to FlightInsight API..."):
            health = api("/health")
            if health.get("status") != "ok" or health.get("database") != "ok":
                raise FlightInsightAPIError("API or PostgreSQL is not ready")
            airlines = api("/api/v1/airlines")
            airports = api("/api/v1/airports")
    except FlightInsightAPIError as exc:
        st.error(f"FlightInsight API unavailable: {exc}")
        st.info("Run `docker compose up -d --build api dashboard` and verify `http://localhost:8000/health`.")
        st.stop()

    airline_labels = {row["airline_code"]: (row.get("airline_name") or row["airline_code"]) for row in airlines}
    airport_labels = {
        row["airport_code"]: ", ".join(part for part in (row.get("city"), row.get("state")) if part)
        for row in airports
    }

    with st.sidebar:
        st.markdown("### Explore data")
        st.caption("Real US domestic flights · Jan–Mar 2025")
        page = st.radio(
            "View", ["Overview", "Airlines", "Airports", "Time patterns", "Disruptions"],
            label_visibility="collapsed",
        )
        st.divider()
        st.markdown("**Filters**")
        with st.form("filter_form"):
            dates = st.date_input("Flight dates", (START_DATE, END_DATE), min_value=START_DATE, max_value=END_DATE)
            airline = st.selectbox("Airline", [""] + sorted(airline_labels),
                                   format_func=lambda code: "All airlines" if not code else
                                   (code if airline_labels.get(code, code) == code else f"{code} · {airline_labels[code]}") )
            origin = st.selectbox("Origin airport", [""] + sorted(airport_labels),
                                  format_func=lambda code: "All origins" if not code else
                                  (f"{code} · {airport_labels[code]}" if airport_labels.get(code) else code))
            destination = st.selectbox("Destination airport", [""] + sorted(airport_labels),
                                       format_func=lambda code: "All destinations" if not code else
                                       (f"{code} · {airport_labels[code]}" if airport_labels.get(code) else code))
            sample = st.number_input("Minimum ranking sample", min_value=0, max_value=1_000_000, value=100, step=100,
                                     help="Smaller samples may produce unstable rankings")
            st.form_submit_button("Apply filters", use_container_width=True, type="primary")
        st.divider()
        st.caption("Source: Bureau of Transportation Statistics (BTS). Historic results are not future predictions.")
        st.markdown("[Open API documentation](http://localhost:8000/docs)")

    if not isinstance(dates, (list, tuple)) or len(dates) != 2:
        st.info("Select both the start and end dates in the sidebar.")
        st.stop()
    date_from, date_to = dates
    if date_from > date_to:
        st.warning("The start date must not be after the end date.")
        st.stop()
    filters = {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
               "airline": airline or None, "origin": origin or None,
               "destination": destination or None, "min_sample_size": int(sample)}

    st.caption(f"**Selected period:** {date_from:%d %b %Y} – {date_to:%d %b %Y}"
               + (f" · Airline {airline}" if airline else ""))
    try:
        summary = api("/api/v1/summary", filters)
        if summary.get("total_flights", 0) == 0:
            st.info("No flights match the selected filters. Adjust the date range or airport selections.")
            st.stop()
        if page == "Overview":
            render_overview(filters, summary)
        elif page == "Airlines":
            render_airlines(filters)
        elif page == "Airports":
            render_airports(filters)
        elif page == "Time patterns":
            render_patterns(filters)
        else:
            render_disruptions(filters)
    except FlightInsightAPIError as exc:
        st.error(f"Could not load analytics: {exc}")
        st.info("The API may be busy processing the query. Try the filters again or inspect `docker compose logs api`.")

    st.divider()
    st.caption("FlightInsight · Public BTS on-time performance data · January–March 2025 · Flight arrivals ≥15 min late are delayed")


if __name__ == "__main__":
    main()
