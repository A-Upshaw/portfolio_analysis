import os
import sys
import re
import requests
import streamlit as st
import plotly.express as px
import pandas as pd
from datetime import date, timedelta, datetime
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

@st.cache_data(ttl=300)
def load_movers():
    return supabase.table("market_movers").select("*").execute().data

@st.cache_data(ttl=3600)
def load_enterprise_values():
    rows = supabase.table("fundamentals").select("ticker,enterprise_value").execute().data
    return {r["ticker"]: r["enterprise_value"] for r in rows if r["enterprise_value"]}

@st.cache_data(ttl=300)
def load_news(ticker=None, limit=20):
    params = {
        "apiKey": os.environ["POLYGON_API_KEY"],
        "limit":  limit,
        "order":  "desc",
        "sort":   "published_utc",
    }
    if ticker:
        params["ticker.any_of"] = ticker
    resp = requests.get("https://api.polygon.io/v2/reference/news", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("results", [])

@st.cache_data(ttl=3600)
def load_indicators():
    fred_key = os.environ["FRED_API_KEY"]
    series_map = {
        "Fed Funds Rate": ("FEDFUNDS", "%"),
        "CPI (Index)":    ("CPIAUCSL", ""),
        "GDP ($B)":       ("GDP", "$B"),
        "Unemployment":   ("UNRATE", "%"),
    }
    result = {}
    for label, (series_id, unit) in series_map.items():
        resp = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id":  series_id,
                "api_key":    fred_key,
                "file_type":  "json",
                "limit":      24,
                "sort_order": "desc",
            },
            timeout=10,
        )
        resp.raise_for_status()
        obs = [o for o in resp.json()["observations"] if o["value"] != "."]
        obs.sort(key=lambda o: o["date"])
        result[label] = {"unit": unit, "observations": obs}
    return result

def fetch_ticker_metadata(ticker):
    resp = requests.get(
        f"https://api.polygon.io/v3/reference/tickers/{ticker}",
        params={"apiKey": os.environ["POLYGON_API_KEY"]},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    r = resp.json().get("results", {})
    return {
        "ticker":     ticker,
        "company":    r.get("name", ticker),
        "sector":     None,
        "exchange":   r.get("primary_exchange"),
        "asset_type": r.get("type"),
    }

def backfill_ticker_prices(ticker, lookback_days=365):
    end   = date.today() - timedelta(days=1)
    start = end - timedelta(days=lookback_days)
    resp = requests.get(
        f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}",
        params={"adjusted": "true", "sort": "asc", "limit": 500, "apiKey": os.environ["POLYGON_API_KEY"]},
        timeout=30,
    )
    resp.raise_for_status()
    rows = []
    for r in resp.json().get("results", []):
        rows.append({
            "ticker": ticker,
            "date":   datetime.utcfromtimestamp(r["t"] / 1000).strftime("%Y-%m-%d"),
            "open":   r.get("o"),
            "high":   r.get("h"),
            "low":    r.get("l"),
            "close":  r.get("c"),
            "volume": int(r["v"]) if r.get("v") else None,
        })
    if rows:
        supabase.table("price_history").upsert(rows, on_conflict="ticker,date").execute()
    return len(rows)


summary  = load_summary()
positions = pd.DataFrame(load_positions())
sectors   = pd.DataFrame(load_sector_exposure())
vs_spy    = pd.DataFrame(load_vs_spy())
movers    = pd.DataFrame(load_movers())

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

    if "analyzer_messages" not in st.session_state:
        st.session_state.analyzer_messages = []
    
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
                response = analyze(prompt, st.session_state.analyzer_messages)
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

    if movers.empty:
        st.info("No mover data yet — run `dbt run` after the next price fetch.")
    else:
        st.caption(f"As of {movers['date'].max()} · {len(movers)} tickers")

        ev_map = load_enterprise_values()
        movers["size_metric"] = movers["ticker"].map(ev_map)
        movers.loc[movers["size_metric"] <= 0, "size_metric"] = None
        movers["size_metric"] = movers["size_metric"].fillna(movers["size_metric"].median())
        movers["sector"] = movers["sector"].fillna("Other")
        # Pre-format as a plain string — passing the raw float through customdata into a
        # d3-format texttemplate produced garbled output (e.g. "5.7099999999999999%") for
        # some values due to a float round-trip precision quirk.
        movers["change_label"] = movers["change_pct"].apply(lambda x: f"{x:+.2f}%")

        HEATMAP_SCALE = [
            [0.00, "#8b0000"], [0.25, "#d73027"], [0.45, "#fdae61"],
            [0.50, "#fffabf"],
            [0.55, "#a6d96a"], [0.75, "#1a9850"], [1.00, "#00441b"],
        ]
        fig_heat = px.treemap(
            movers,
            path=[px.Constant("S&P Universe"), "sector", "ticker"],
            values="size_metric",
            color="change_pct",
            color_continuous_scale=HEATMAP_SCALE,
            color_continuous_midpoint=0,
            range_color=[-4, 4],
            custom_data=["company", "close", "change_label"],
        )

        # Plotly auto-colors sector/root headers by averaging their children's color —
        # a mixed sector averages back to ~0, landing on the same pale yellow as a flat
        # stock. Override headers (depth 0-1 ids) to a fixed dark band; leave leaf
        # tickers (depth 2) on the data-driven scale.
        from plotly.colors import sample_colorscale
        change_by_ticker = movers.set_index("ticker")["change_pct"].to_dict()
        node_colors = []
        for node_id, label in zip(fig_heat.data[0].ids, fig_heat.data[0].labels):
            if node_id.count("/") == 2:
                t = (max(-4, min(4, change_by_ticker.get(label, 0))) + 4) / 8
                node_colors.append(sample_colorscale(HEATMAP_SCALE, [t])[0])
            else:
                node_colors.append("#2c2f38")

        fig_heat.update_traces(
            texttemplate="<b>%{label}</b><br>%{customdata[2]}",
            textfont=dict(family="Inter, sans-serif", size=13, color="white"),
            hovertemplate="<b>%{customdata[0]}</b><br>Close: $%{customdata[1]:,.2f}<br>Change: %{customdata[2]}<extra></extra>",
            marker=dict(colors=node_colors, line=dict(width=1, color="white")),
        )
        fig_heat.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            height=550,
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_heat, use_container_width=True)

        st.markdown("---")

        sector_options = ["All"] + sorted(movers["sector"].unique().tolist())
        selected_sector = st.selectbox("Sector", sector_options)
        movers_view = movers if selected_sector == "All" else movers[movers["sector"] == selected_sector]

        def style_movers(df):
            disp = df[["ticker", "company", "sector", "close", "change_dollars", "change_pct", "volume"]].copy()
            disp.columns = ["Ticker", "Company", "Sector", "Close", "Change ($)", "Change (%)", "Volume"]
            return disp.style.map(color_pnl_cell, subset=["Change ($)", "Change (%)"]).format({
                "Close":      "${:,.2f}",
                "Change ($)": "${:,.2f}",
                "Change (%)": "{:.2f}%",
                "Volume":     "{:,.0f}",
            })

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Top Gainers**")
            gainers = movers_view.sort_values("change_pct", ascending=False).head(10)
            st.dataframe(style_movers(gainers), use_container_width=True, hide_index=True)
        with col2:
            st.markdown("**Top Losers**")
            losers = movers_view.sort_values("change_pct", ascending=True).head(10)
            st.dataframe(style_movers(losers), use_container_width=True, hide_index=True)

# Tab 4: News
with tab4:
    st.subheader("News")

    news_ticker = st.text_input("Filter by ticker (optional)", placeholder="e.g. AAPL").strip().upper()
    articles = load_news(ticker=news_ticker or None)

    if not articles:
        st.info("No news articles found.")
    else:
        for article in articles:
            published = article.get("published_utc", "")[:10]
            publisher = article.get("publisher", {}).get("name", "Unknown")
            tickers   = ", ".join(article.get("tickers", [])[:5])
            st.markdown(f"""
            <div class="kpi-card" style="border-left-color:#4c9be8;">
                <div style="font-weight:700; font-size:1rem; margin-bottom:4px;">
                    <a href="{article.get('article_url', '#')}" target="_blank" style="text-decoration:none; color:#1a1f2e;">{article.get('title', 'Untitled')}</a>
                </div>
                <div style="font-size:0.8rem; color:#7a8599;">{publisher} · {published} · {tickers}</div>
            </div>
            """, unsafe_allow_html=True)

# Tab 5: Economic Indicators
with tab5:
    st.subheader("Economic Indicators")

    indicators = load_indicators()
    col1, col2 = st.columns(2)
    cols = [col1, col2, col1, col2]

    for (label, data), col in zip(indicators.items(), cols):
        obs = data["observations"]
        if not obs:
            continue
        df_obs = pd.DataFrame(obs)
        df_obs["date"] = pd.to_datetime(df_obs["date"])
        df_obs["value"] = df_obs["value"].astype(float)

        latest = df_obs.iloc[-1]
        with col:
            fig = px.line(
                df_obs, x="date", y="value",
                title=f"{label} — latest {latest['value']:,.2f}{data['unit']}",
                template=CHART_TEMPLATE,
                labels={"value": label, "date": ""},
                color_discrete_sequence=["#4c9be8"],
            )
            fig.update_traces(line=dict(width=2.5))
            fig.update_layout(font=CHART_FONT, height=300, margin=dict(t=40, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)
