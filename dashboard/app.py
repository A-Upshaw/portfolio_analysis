import os
import sys
import re
import streamlit as st
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis.portfolio_analyzer import analyze

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

st.set_page_config(page_title="Portfolio OS", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stMarkdown, .stDataFrame, button, input {
    font-family: 'Inter', sans-serif !important;
}

.kpi-card {
    background-color: #f8f9fb;
    border: 1px solid #e4e8ee;
    border-left: 4px solid #4c9be8;
    border-radius: 10px;
    padding: 18px 22px;
    margin-bottom: 8px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.kpi-label {
    font-size: 0.72rem;
    color: #7a8599;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
}
.kpi-value {
    font-size: 1.45rem;
    font-weight: 700;
    color: #1a1f2e;
}
.kpi-delta {
    font-size: 0.85rem;
    margin-top: 5px;
    font-weight: 500;
}

.ticker-strip {
    background-color: #f8f9fb;
    border: 1px solid #e4e8ee;
    border-radius: 8px;
    padding: 10px 0;
    margin-bottom: 16px;
    overflow: hidden;
    white-space: nowrap;
}
.ticker-track {
    display: inline-block;
    animation: ticker-scroll 40s linear infinite;
}
.ticker-track:hover { animation-play-state: paused; }
@keyframes ticker-scroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
.ticker-item {
    display: inline-block;
    margin-right: 36px;
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem;
}
.ticker-symbol { font-weight: 700; color: #1a1f2e; }
.ticker-price { color: #555; margin: 0 5px; }
</style>
""", unsafe_allow_html=True)

CHART_FONT = dict(family="Inter, sans-serif", size=13, color="#1a1f2e")
CHART_TEMPLATE = "plotly_white"
@st.cache_data(ttl=300)
def load_summary():
    return supabase.table("portfolio_summary").select("*").execute().data[0]

@st.cache_data(ttl=300)
def load_positions():
    return supabase.table("portfolio_positions").select("*").execute().data

@st.cache_data(ttl=300)
def load_sector_exposure():
    return supabase.table("portfolio_sector_exposure").select("*").execute().data

@st.cache_data(ttl=300)
def load_vs_spy():
    return supabase.table("portfolio_vs_spy").select("*").execute().data

summary  = load_summary()
positions = pd.DataFrame(load_positions())
sectors   = pd.DataFrame(load_sector_exposure())
vs_spy    = pd.DataFrame(load_vs_spy())

# Header
st.markdown("""
<div style="padding: 8px 0 4px 0;">
    <span style="font-family:'Inter',sans-serif; font-size:2rem; font-weight:800; color:#1a1f2e; letter-spacing:-0.03em;">Portfolio</span>
    <span style="font-family:'Inter',sans-serif; font-size:2rem; font-weight:300; color:#4c9be8; letter-spacing:-0.03em;"> OS</span>
</div>
""", unsafe_allow_html=True)

# Ticker strip — items duplicated so scroll loops seamlessly
def build_ticker_items(df):
    html = ""
    for _, row in df.sort_values("ticker").iterrows():
        color = "#27ae60" if row["unrealized_gain_loss_pct"] >= 0 else "#e74c3c"
        arrow = "▲" if row["unrealized_gain_loss_pct"] >= 0 else "▼"
        html += (
            f'<span class="ticker-item">'
            f'<span class="ticker-symbol">{row["ticker"]}</span>'
            f'<span class="ticker-price">${row["current_price"]:,.2f}</span>'
            f'<span style="color:{color};font-weight:600;">{arrow}{abs(row["unrealized_gain_loss_pct"]):.2f}%</span>'
            f'</span>'
        )
    return html

items = build_ticker_items(positions)
ticker_html = f'<div class="ticker-strip"><div class="ticker-track">{items}{items}</div></div>'
st.markdown(ticker_html, unsafe_allow_html=True)

st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Portfolio Summary", "Positions", "Market Movers", "News", "Economic Indicators"])

# Tab 1: Portfolio Summary
with tab1:
    pnl       = summary["total_gain_loss_dollars"]
    pnl_pct   = summary["portfolio_gain_loss_pct"]
    pnl_color = "#27ae60" if pnl >= 0 else "#e74c3c"
    pnl_arrow = "▲" if pnl >= 0 else "▼"

    best_row  = positions.loc[positions["unrealized_gain_loss_pct"].idxmax()]
    worst_row = positions.loc[positions["unrealized_gain_loss_pct"].idxmin()]

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
            <div class="kpi-delta" style="color:#27ae60">▲ {best_row['unrealized_gain_loss_pct']}%</div>
        </div>""", unsafe_allow_html=True)
    with col5:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Worst Performer</div>
            <div class="kpi-value">{worst_row['ticker']}</div>
            <div class="kpi-delta" style="color:#e74c3c">▼ {abs(worst_row['unrealized_gain_loss_pct'])}%</div>
        </div>""", unsafe_allow_html=True)

    st.caption(f"As of {summary['as_of_date']}")
    st.markdown("---")

    # SPY chart full width
    spy_range = st.radio("Range", ["1W", "1M", "All"], index=2, horizontal=True, label_visibility="collapsed")

    vs_spy["date"] = pd.to_datetime(vs_spy["date"])
    if spy_range == "1W":
        df_spy = vs_spy[vs_spy["date"] >= pd.Timestamp.today() - pd.Timedelta(days=7)]
    elif spy_range == "1M":
        df_spy = vs_spy[vs_spy["date"] >= pd.Timestamp.today() - pd.Timedelta(days=30)]
    else:
        df_spy = vs_spy

    fig_spy = px.line(
        df_spy, x="date", y=["portfolio_idx", "spy_idx"],
        title="Portfolio vs SPY (Indexed to 100)",
        template=CHART_TEMPLATE,
        labels={"value": "Indexed Return", "date": "Date", "variable": ""},
        color_discrete_map={"portfolio_idx": "#4c9be8", "spy_idx": "#f39c12"},
    )
    fig_spy.for_each_trace(lambda t: t.update(
        name="My Portfolio" if t.name == "portfolio_idx" else "SPY",
        line=dict(width=2.5),
        hovertemplate="<b>%{fullData.name}</b><br>Date: %{x|%b %d, %Y}<br>Index: %{y:.2f}<extra></extra>"
    ))
    fig_spy.update_layout(
        font=CHART_FONT,
        margin=dict(t=40, b=10, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    st.plotly_chart(fig_spy, use_container_width=True)

    st.markdown("---")

    # Sector pie + P&L bar side by side
    col1, col2 = st.columns(2)

    with col1:
        fig_sector = px.pie(
            sectors, values="sector_market_value", names="sector",
            title="Sector Allocation",
            template=CHART_TEMPLATE,
            color_discrete_sequence=px.colors.qualitative.Set2,
            hole=0.35,
        )
        fig_sector.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Value: $%{value:,.2f}<br>%{percent}<extra></extra>"
        )
        fig_sector.update_layout(
            font=CHART_FONT,
            showlegend=False,
            height=360,
            margin=dict(t=40, b=10, l=10, r=10),
        )
        st.plotly_chart(fig_sector, use_container_width=True)

    with col2:
        pnl_view = st.radio("View P&L by:", ["By Position", "By Sector"], horizontal=True)

        if pnl_view == "By Position":
            df_bar = positions.sort_values("unrealized_gain_loss").copy()
            df_bar["_color"] = df_bar["unrealized_gain_loss"].apply(lambda x: "#27ae60" if x >= 0 else "#e74c3c")
            fig_pnl = px.bar(
                df_bar, x="ticker", y="unrealized_gain_loss",
                color="_color", color_discrete_map="identity",
                title="Unrealized P&L by Position",
                template=CHART_TEMPLATE,
                labels={"unrealized_gain_loss": "Gain/Loss ($)", "ticker": "Ticker", "_color": ""},
            )
        else:
            df_bar = sectors.sort_values("sector_gain_loss_dollars").copy()
            df_bar["_color"] = df_bar["sector_gain_loss_dollars"].apply(lambda x: "#27ae60" if x >= 0 else "#e74c3c")
            fig_pnl = px.bar(
                df_bar, x="sector", y="sector_gain_loss_dollars",
                color="_color", color_discrete_map="identity",
                title="Unrealized P&L by Sector",
                template=CHART_TEMPLATE,
                labels={"sector_gain_loss_dollars": "Gain/Loss ($)", "sector": "Sector", "_color": ""},
            )

        fig_pnl.update_traces(hovertemplate="<b>%{x}</b><br>Gain/Loss: $%{y:,.2f}<extra></extra>")
        fig_pnl.update_layout(
            font=CHART_FONT,
            showlegend=False,
            height=360,
            margin=dict(t=40, b=10, l=10, r=10),
            xaxis=dict(tickfont=dict(size=11)),
        )
        st.plotly_chart(fig_pnl, use_container_width=True)

    st.markdown("---")
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
            safe = re.sub(r'\$(\d)', r'\\$\1', response)
            st.markdown(safe)
        st.session_state.messages.append({"role": "assistant", "content": response})

# Tab 2: Positions
with tab2:
    display = positions[[
        "ticker", "company", "sector", "account", "shares", "purchase_price",
        "current_price", "cost_basis", "current_value",
        "unrealized_gain_loss", "unrealized_gain_loss_pct"
    ]].copy()
    display.columns = [
        "Ticker", "Company", "Sector", "Account", "Shares", "Purchase Price",
        "Current Price", "Cost Basis", "Market Value",
        "Gain/Loss ($)", "Gain/Loss (%)"
    ]
    display = display.sort_values("Gain/Loss (%)", ascending=False).round(2)

    def color_pnl_cell(val):
        if val > 0:
            return "background-color: rgba(39,174,96,0.12); color: #1e8449; font-weight: 600"
        elif val < 0:
            return "background-color: rgba(231,76,60,0.12); color: #c0392b; font-weight: 600"
        return ""

    st.dataframe(
        display.style
            .map(color_pnl_cell, subset=["Gain/Loss ($)", "Gain/Loss (%)"])
            .format({
                "Shares": "{:,.0f}",
                "Purchase Price": "${:,.2f}",
                "Current Price":  "${:,.2f}",
                "Cost Basis":     "${:,.2f}",
                "Market Value":   "${:,.2f}",
                "Gain/Loss ($)":  "${:,.2f}",
                "Gain/Loss (%)":  "{:.2f}%",
            }),
        use_container_width=True,
        hide_index=True,
        height=500,
    )

# Tab 3: Market Movers
with tab3:
    st.subheader("Market Movers")
    st.info("Coming soon — top gainers and losers from your 560-ticker universe.")

# Tab 4: News
with tab4:
    st.subheader("News")
    st.info("Coming soon — latest news for your portfolio tickers via Polygon.io.")

# Tab 5: Economic Indicators
with tab5:
    st.subheader("Economic Indicators")
    st.info("Coming soon — GDP, inflation, Fed funds rate, and unemployment via FRED API.")
