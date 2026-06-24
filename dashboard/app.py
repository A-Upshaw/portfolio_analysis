import os
import sys
import streamlit as st
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client
import requests

# allows importing from analysis/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis.portfolio_analyzer import analyze

load_dotenv()

# supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

st.set_page_config(page_title="AI Portfolio Analyst", layout="wide")

st.markdown("""
<style>
.kpi-card {
    background-color: rgba(255, 255, 255, 0.05);
    border-left: 4px solid #4c9be8;
    border-right: 4px solid #4c9be8;
    border-top: 1px solid rgba(255, 255, 255, 0.15);
    border-bottom: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 8px;
}
.kpi-label { font-size: 0.85rem; color: #aaa; margin-bottom: 4px; }
.kpi-value { font-size: 1.4rem; font-weight: 700; }
.kpi-delta { font-size: 0.9rem; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

st.title("AI Portfolio Analyst")
st.markdown("#### Claude-powered portfolio analysis.")
st.markdown("---")

@st.cache_data(ttl=300)
def load_summary():
    return requests.get("http://localhost:8000/portfolio/summary").json()

@st.cache_data(ttl=300)
def load_positions():
    return requests.get("http://localhost:8000/portfolio/positions").json()

@st.cache_data(ttl=300)
def load_sector_exposure():
    return requests.get("http://localhost:8000/portfolio/sector").json()

@st.cache_data(ttl=300)
def load_vs_spy():
    return requests.get("http://localhost:8000/portfolio/spy").json()

summary = load_summary()
positions = pd.DataFrame(load_positions())
sectors = pd.DataFrame(load_sector_exposure())
vs_spy = pd.DataFrame(load_vs_spy())

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Portfolio Summary", "Positions", "Market Movers", "News", "Economic Indicators"])

# ── Tab 1: My Portfolio ───────────────────────────────────────────────────────
with tab1:
    st.subheader("Portfolio Summary")

    pnl = summary['total_gain_loss_dollars']
    pnl_pct = summary['portfolio_gain_loss_pct']
    pnl_color = "#2ecc71" if pnl >= 0 else "#e74c3c"
    pnl_arrow = "▲" if pnl >= 0 else "▼"

    best_row = positions.loc[positions['unrealized_gain_loss_pct'].idxmax()]
    worst_row = positions.loc[positions['unrealized_gain_loss_pct'].idxmin()]

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Total Value</div>
            <div class="kpi-value">${summary['total_market_value']:,.2f}</div>
        </div>""", unsafe_allow_html=True)

    with col2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Total Cost</div>
            <div class="kpi-value">${summary['total_cost_basis']:,.2f}</div>
        </div>""", unsafe_allow_html=True)

    with col3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Unrealized P&L</div>
            <div class="kpi-value">${pnl:,.2f}</div>
            <div class="kpi-delta" style="color:{pnl_color}">{pnl_arrow} {pnl_pct}%</div>
        </div>""", unsafe_allow_html=True)

    with col4:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Best Performer</div>
            <div class="kpi-value">{best_row['ticker']}</div>
            <div class="kpi-delta" style="color:#2ecc71">▲ {best_row['unrealized_gain_loss_pct']}%</div>
        </div>""", unsafe_allow_html=True)

    with col5:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Worst Performer</div>
            <div class="kpi-value">{worst_row['ticker']}</div>
            <div class="kpi-delta" style="color:#e74c3c">▼ {abs(worst_row['unrealized_gain_loss_pct'])}%</div>
        </div>""", unsafe_allow_html=True)

    st.caption(f"As of {summary['as_of_date']}")

    st.subheader("Portfolio Breakdown")
    col1, col2 = st.columns(2)

    with col1:
        fig_sector = px.pie(sectors, values="sector_market_value", names="sector",
                            title="Sector Allocation")
        st.plotly_chart(fig_sector, use_container_width=True)

    with col2:
        pnl_view = st.radio("Unrealized P&L View", ["By Position", "By Sector"],
                            horizontal=True, label_visibility="collapsed")

        if pnl_view == "By Position":
            fig_pnl = px.bar(positions.sort_values("unrealized_gain_loss"),
                             x="ticker", y="unrealized_gain_loss",
                             color="unrealized_gain_loss",
                             color_continuous_scale=["red", "green"],
                             color_continuous_midpoint=0,
                             title="Unrealized P&L by Position",
                             labels={"unrealized_gain_loss": "Gain/Loss ($)", "ticker": "Ticker"})
            fig_pnl.update_coloraxes(showscale=False)
        else:
            fig_pnl = px.bar(sectors.sort_values("sector_gain_loss_dollars"),
                             x="sector", y="sector_gain_loss_dollars",
                             color="sector_gain_loss_dollars",
                             color_continuous_scale=["red", "green"],
                             color_continuous_midpoint=0,
                             title="Unrealized P&L by Sector",
                             labels={"sector_gain_loss_dollars": "Gain/Loss ($)", "sector": "Sector"})
            fig_pnl.update_coloraxes(showscale=False)

        st.plotly_chart(fig_pnl, use_container_width=True)

    st.subheader("Portfolio vs SPY")
    fig_spy = px.line(vs_spy, x="date", y=["portfolio_idx", "spy_idx"],
                      title="Portfolio vs SPY (Indexed to 100)",
                      labels={"value": "Indexed Return", "date": "Date", "variable": ""},
                      color_discrete_map={"portfolio_idx": "#1f77b4", "spy_idx": "#ff7f0e"})
    fig_spy.for_each_trace(lambda t: t.update(
        name="My Portfolio" if t.name == "portfolio_idx" else "SPY"
    ))
    st.plotly_chart(fig_spy, use_container_width=True)

    st.divider()
    st.subheader("Ask Your Portfolio Anything")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask anything about your portfolio..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                response = analyze(prompt)
            st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})

# ── Tab 2: Positions ─────────────────────────────────────────────────────────
with tab2:
    st.subheader("All Positions")
    display = positions[[
        "ticker", "company", "account", "shares", "purchase_price",
        "current_price", "cost_basis", "current_value",
        "unrealized_gain_loss", "unrealized_gain_loss_pct"
    ]].copy()
    display.columns = [
        "Ticker", "Company", "Account", "Shares", "Purchase Price",
        "Current Price", "Cost Basis", "Current Value",
        "Gain/Loss ($)", "Gain/Loss (%)"
    ]
    display = display.sort_values("Gain/Loss (%)", ascending=False)
    display = display.round(2)

    def color_pnl(val):
        color = "#2ecc71" if val >= 0 else "#e74c3c"
        return f"color: {color}"

    st.dataframe(
        display.style.map(color_pnl, subset=["Gain/Loss ($)", "Gain/Loss (%)"]).format({
            "Shares": "{:.0f}",

            "Purchase Price": "${:.2f}",
            "Current Price": "${:.2f}",
            "Cost Basis": "${:.2f}",
            "Current Value": "${:.2f}",
            "Gain/Loss ($)": "${:.2f}",
            "Gain/Loss (%)": "{:.2f}%",
        }),
        use_container_width=True,
        hide_index=True
    )

# ── Tab 3: Market Movers ──────────────────────────────────────────────────────
with tab3:
    st.subheader("Market Movers")
    st.info("Coming soon — top gainers and losers from your 560-ticker universe.")

# ── Tab 4: News ───────────────────────────────────────────────────────────────
with tab4:
    st.subheader("News")
    st.info("Coming soon — latest news for your portfolio tickers via Polygon.io.")

# ── Tab 5: Economic Indicators ────────────────────────────────────────────────
with tab5:
    st.subheader("Economic Indicators")
    st.info("Coming soon — GDP, inflation, Fed funds rate, and unemployment via FRED API.")
