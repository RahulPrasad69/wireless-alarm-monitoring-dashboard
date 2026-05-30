import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(
    page_title="Wireless Alarm Monitoring Dashboard",
    page_icon="📡",
    layout="wide",
)

CHANNEL_ID = st.secrets.get("CHANNEL_ID", "")
READ_API_KEY = st.secrets.get("READ_API_KEY", "")

STATUS_MAP = {
    0: "NORMAL",
    1: "FAULT",
    2: "COMMUNICATION LOST",
}

ALARM_MAP = {
    0: "SYSTEM NORMAL",
    1: "ALARM ACTIVE",
    2: "COMMUNICATION WARNING",
}

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            max-width: 1500px;
        }
        .header {
            background: linear-gradient(135deg, #0f172a, #1e293b, #334155);
            color: white;
            padding: 1.4rem 1.6rem;
            border-radius: 24px;
            box-shadow: 0 18px 45px rgba(15, 23, 42, 0.22);
            margin-bottom: 1rem;
        }
        .header h1 {
            margin: 0;
            font-size: 2.1rem;
            line-height: 1.2;
            letter-spacing: -0.03em;
        }
        .header p {
            margin: 0.4rem 0 0 0;
            color: #cbd5e1;
            font-size: 1rem;
        }
        .card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 22px;
            padding: 1.1rem 1.2rem;
            box-shadow: 0 14px 32px rgba(15, 23, 42, 0.08);
            margin-bottom: 0.8rem;
        }
        .node-normal { border-top: 8px solid #16a34a; }
        .node-fault { border-top: 8px solid #dc2626; }
        .node-lost { border-top: 8px solid #f97316; }
        .node-title {
            font-size: 1.25rem;
            font-weight: 850;
            color: #0f172a;
            margin-bottom: 0.15rem;
        }
        .node-subtitle {
            color: #64748b;
            font-size: 0.9rem;
            margin-bottom: 0.8rem;
        }
        .badge {
            display: inline-block;
            padding: 0.45rem 0.8rem;
            border-radius: 999px;
            font-weight: 850;
            font-size: 0.82rem;
            letter-spacing: 0.03em;
        }
        .badge-normal {
            background: #dcfce7;
            color: #166534;
        }
        .badge-fault {
            background: #fee2e2;
            color: #991b1b;
        }
        .badge-lost {
            background: #ffedd5;
            color: #9a3412;
        }
        .section-title {
            font-size: 1.05rem;
            font-weight: 850;
            color: #0f172a;
            margin: 0.4rem 0 0.8rem 0;
        }
        .summary-normal { border-left: 8px solid #16a34a; }
        .summary-fault { border-left: 8px solid #dc2626; }
        .summary-warning { border-left: 8px solid #f97316; }
        .summary-text {
            font-size: 1rem;
            color: #334155;
        }
        .summary-state {
            font-weight: 900;
            color: #0f172a;
        }
        .footer {
            color: #64748b;
            font-size: 0.85rem;
            margin-top: 0.8rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def safe_int(value, default=None):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def safe_float(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def status_text(code):
    return STATUS_MAP.get(safe_int(code, 2), "UNKNOWN")


def alarm_text(code):
    return ALARM_MAP.get(safe_int(code, 2), "UNKNOWN")


def status_class(status):
    if status == "FAULT":
        return "fault"
    if status == "COMMUNICATION LOST":
        return "lost"
    return "normal"


def badge_class(status):
    if status == "FAULT":
        return "badge-fault"
    if status == "COMMUNICATION LOST":
        return "badge-lost"
    return "badge-normal"


def signal_quality(rssi):
    if rssi is None:
        return "Unknown"
    if rssi >= -85:
        return "Strong"
    if rssi >= -100:
        return "Weak"
    return "Critical"


def summary_class(alarm_state):
    if alarm_state == "ALARM ACTIVE":
        return "summary-fault"
    if alarm_state == "COMMUNICATION WARNING":
        return "summary-warning"
    return "summary-normal"


@st.cache_data(ttl=15)
def fetch_thingspeak_data(channel_id, read_api_key, results):
    if not channel_id:
        return pd.DataFrame()

    url = f"https://api.thingspeak.com/channels/{channel_id}/feeds.json?results={results}"

    if read_api_key:
        url += f"&api_key={read_api_key}"

    response = requests.get(url, timeout=15)
    response.raise_for_status()

    data = response.json()
    feeds = data.get("feeds", [])

    rows = []

    for feed in feeds:
        rows.append(
            {
                "Time": pd.to_datetime(feed.get("created_at"), errors="coerce"),
                "D1 Status Code": safe_int(feed.get("field1")),
                "D2 Status Code": safe_int(feed.get("field2")),
                "D1 RSSI": safe_float(feed.get("field3")),
                "D2 RSSI": safe_float(feed.get("field4")),
                "D1 Response": safe_float(feed.get("field5")),
                "D2 Response": safe_float(feed.get("field6")),
                "Alarm Code": safe_int(feed.get("field7")),
                "Packet Seq": safe_int(feed.get("field8")),
                "Entry ID": safe_int(feed.get("entry_id")),
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df = df.dropna(subset=["Time"])
    df = df.sort_values("Time")

    df["D1 Status"] = df["D1 Status Code"].apply(status_text)
    df["D2 Status"] = df["D2 Status Code"].apply(status_text)
    df["Alarm State"] = df["Alarm Code"].apply(alarm_text)

    return df


def render_node_card(title, subtitle, status, rssi, response):
    css = status_class(status)
    badge = badge_class(status)

    st.markdown(
        f"""
        <div class="card node-{css}">
            <div class="node-title">{title}</div>
            <div class="node-subtitle">{subtitle}</div>
            <span class="badge {badge}">{status}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("RSSI", "—" if rssi is None else f"{rssi:.0f} dBm")

    with c2:
        st.metric("Signal Quality", signal_quality(rssi))

    with c3:
        st.metric("Response", "—" if response is None else f"{response:.0f} ms")


def render_rssi_chart(df):
    fig = go.Figure()

    fig.add_trace(go.Scatter(x=df["Time"], y=df["D1 RSSI"], mode="lines+markers", name="Department 1 RSSI"))
    fig.add_trace(go.Scatter(x=df["Time"], y=df["D2 RSSI"], mode="lines+markers", name="Department 2 RSSI"))

    fig.add_hline(y=-85, line_dash="dash", annotation_text="Strong / Weak")
    fig.add_hline(y=-100, line_dash="dash", annotation_text="Weak / Critical")

    fig.update_layout(
        height=350,
        margin=dict(l=10, r=10, t=15, b=10),
        xaxis_title="Time",
        yaxis_title="RSSI (dBm)",
        legend_title="Signal",
    )

    st.plotly_chart(fig, use_container_width=True)


def render_response_chart(df):
    fig = go.Figure()

    fig.add_trace(go.Scatter(x=df["Time"], y=df["D1 Response"], mode="lines+markers", name="Department 1 Response"))
    fig.add_trace(go.Scatter(x=df["Time"], y=df["D2 Response"], mode="lines+markers", name="Department 2 Response"))

    fig.update_layout(
        height=350,
        margin=dict(l=10, r=10, t=15, b=10),
        xaxis_title="Time",
        yaxis_title="Response time (ms)",
        legend_title="Response",
    )

    st.plotly_chart(fig, use_container_width=True)


with st.sidebar:
    st.title("Dashboard Controls")

    results = st.slider("Number of cloud records", min_value=10, max_value=800, value=100, step=10)
    auto_refresh = st.toggle("Auto refresh", value=True)
    refresh_interval = st.slider("Refresh interval", min_value=10, max_value=60, value=20, step=5)

    if st.button("Refresh now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.caption(
        "Simulation dashboard reading cloud data from ThingSpeak. "
        "Later, the Python simulator can be replaced by the real control-room ESP32 uploader."
    )


st.markdown(
    """
    <div class="header">
        <h1>Wireless Alarm Monitoring Dashboard</h1>
        <p>Remote simulation interface for centralized field alarm monitoring</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if not CHANNEL_ID:
    st.error("CHANNEL_ID is missing. Add CHANNEL_ID and READ_API_KEY in .streamlit/secrets.toml.")
    st.stop()

try:
    df = fetch_thingspeak_data(CHANNEL_ID, READ_API_KEY, results)
except Exception as error:
    st.error(f"Could not read cloud data: {error}")
    st.stop()

if df.empty:
    st.warning("No cloud data found yet. Start cloud_alarm_simulator.py first.")
    st.stop()

latest = df.iloc[-1]

d1_status = latest["D1 Status"]
d2_status = latest["D2 Status"]
alarm_state = latest["Alarm State"]

d1_rssi = latest["D1 RSSI"]
d2_rssi = latest["D2 RSSI"]

d1_response = latest["D1 Response"]
d2_response = latest["D2 Response"]

last_update = latest["Time"]

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric("System State", alarm_state)

with m2:
    packet_value = "—" if pd.isna(latest["Packet Seq"]) else int(latest["Packet Seq"])
    st.metric("Last Packet", packet_value)

with m3:
    st.metric("Last Update", last_update.strftime("%Y-%m-%d %H:%M:%S"))

with m4:
    active_faults = int(d1_status == "FAULT") + int(d2_status == "FAULT")
    st.metric("Active Faults", active_faults)

st.markdown(
    f"""
    <div class="card {summary_class(alarm_state)}">
        <div class="summary-text">
            Current cloud simulation state:
            <span class="summary-state">{alarm_state}</span>.
            The dashboard is reading simulated alarm values from the cloud channel.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

c1, c2 = st.columns(2)

with c1:
    render_node_card("Department 1", "Fixed field node simulation", d1_status, d1_rssi, d1_response)

with c2:
    render_node_card("Department 2", "Mobile field node simulation for robustness testing", d2_status, d2_rssi, d2_response)

st.write("")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown('<div class="section-title">Wireless Signal Strength Simulation</div>', unsafe_allow_html=True)
    render_rssi_chart(df)

with chart_col2:
    st.markdown('<div class="section-title">Response Time Simulation</div>', unsafe_allow_html=True)
    render_response_chart(df)

st.write("")

st.markdown('<div class="section-title">Cloud Simulation Records</div>', unsafe_allow_html=True)

display_df = df.copy()
display_df["Time"] = display_df["Time"].dt.strftime("%Y-%m-%d %H:%M:%S")

display_df = display_df[
    [
        "Time",
        "D1 Status",
        "D2 Status",
        "D1 RSSI",
        "D2 RSSI",
        "D1 Response",
        "D2 Response",
        "Alarm State",
        "Packet Seq",
        "Entry ID",
    ]
].sort_values("Time", ascending=False)

st.dataframe(display_df, use_container_width=True, hide_index=True)

csv = display_df.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download simulation log as CSV",
    data=csv,
    file_name=f"wireless_alarm_simulation_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    mime="text/csv",
    use_container_width=True,
)

st.markdown(
    """
    <div class="footer">
        Cloud-based simulation dashboard. In the final prototype, this cloud data source can be replaced by the control-room ESP32 receiver.
    </div>
    """,
    unsafe_allow_html=True,
)

if auto_refresh:
    time.sleep(refresh_interval)
    st.cache_data.clear()
    st.rerun()
