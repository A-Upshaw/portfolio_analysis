import os
import json
import requests
from dotenv import load_dotenv
from supabase import create_client
import anthropic
from datetime import date

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """You are a portfolio analyst with access to real-time data from the user's investment accounts.
Answer questions using only the data returned by your tools — never guess at numbers.
Be concise and specific. Lead with the key number, then explain.
Today's date is {date}. Price data may be from the most recent trading day, which may not be today. """

def add_user_messages(messages, text):
    user_message = {"role": "user" , "content" : text}
    messages.append(user_message)

def add_assistant_message(messages, content):
    assistant_message = {"role": "assistant", "content": content}
    messages.append(assistant_message)

tools = [
    {
        "name": "get_portfolio_summary",
        "description": "Returns portfolio totals: total value, cost basis, unrealized P&L, P&L %, number of positions, best and worst performers. Use this for high-level portfolio health questions.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_portfolio_positions",
        "description": "Returns all individual holdings with ticker, shares, cost basis, current value, and P&L for each lot. Use this when the question is about specific positions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sector": {
                    "type": "string",
                    "description": "Optional: filter to positions in a specific sector (e.g. 'Technology', 'Healthcare')"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_sector_exposure",
        "description": "Returns portfolio allocation broken down by sector: sector name, total value in that sector, and % of portfolio. Use this for sector concentration and diversification questions.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_daily_movers",
        "description": "Returns portfolio performance vs SPY for recent trading days, including daily return %, SPY return %, and alpha (outperformance). Use this for questions about recent performance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "How many recent trading days to return. Default 5."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_market_movers",
        "description": "Returns the day's top gainers and losers across the full 560-ticker universe (not just portfolio holdings) — ticker, company, sector, close, change $, change %, volume. Use this for 'what's moving in the market today' type questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["gainers", "losers", "both"],
                    "description": "Which side to return. Default 'both'."
                },
                "limit": {
                    "type": "integer",
                    "description": "How many tickers per side. Default 10."
                },
                "sector": {
                    "type": "string",
                    "description": "Optional: filter to a specific sector."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_market_news",
        "description": "Returns recent news headlines, optionally filtered to a ticker. Use this for 'what's the news on X' or 'why did X move' type questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Optional: ticker symbol to filter news to (e.g. 'AAPL')."
                },
                "limit": {
                    "type": "integer",
                    "description": "How many articles to return. Default 10."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_economic_indicators",
        "description": "Returns recent values for key macro indicators: Fed Funds Rate, CPI, GDP, Unemployment rate. Use this for macroeconomic / interest rate / inflation questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "indicator": {
                    "type": "string",
                    "enum": ["Fed Funds Rate", "CPI (Index)", "GDP ($B)", "Unemployment"],
                    "description": "Optional: a single indicator to return. Omit to return all four."
                }
            },
            "required": []
        }
    }
]


def run_tool(tool_name, tool_input, supabase):
    if tool_name == "get_portfolio_summary":
        result = supabase.table("portfolio_summary").select("*").execute()
        return result.data[0] if result.data else {}

    elif tool_name == "get_portfolio_positions":
        query = supabase.table("portfolio_positions").select("*")
        if tool_input.get("sector"):
            query = query.eq("sector", tool_input["sector"])
        result = query.execute()
        return result.data

    elif tool_name == "get_sector_exposure":
        result = supabase.table("portfolio_sector_exposure").select("*").execute()
        return result.data

    elif tool_name == "get_daily_movers":
        days = tool_input.get("days", 5)
        result = supabase.table("portfolio_vs_spy").select("*").order("date", desc=True).limit(days).execute()
        return result.data

    elif tool_name == "get_market_movers":
        direction = tool_input.get("direction", "both")
        limit = tool_input.get("limit", 10)
        sector = tool_input.get("sector")

        query = supabase.table("market_movers").select("*")
        if sector:
            query = query.eq("sector", sector)
        rows = query.execute().data

        gainers = sorted(rows, key=lambda r: r["change_pct"], reverse=True)[:limit]
        losers = sorted(rows, key=lambda r: r["change_pct"])[:limit]

        if direction == "gainers":
            return gainers
        elif direction == "losers":
            return losers
        return {"gainers": gainers, "losers": losers}

    elif tool_name == "get_market_news":
        params = {
            "apiKey": os.environ["POLYGON_API_KEY"],
            "limit": tool_input.get("limit", 10),
            "order": "desc",
            "sort": "published_utc",
        }
        if tool_input.get("ticker"):
            params["ticker.any_of"] = tool_input["ticker"]
        resp = requests.get("https://api.polygon.io/v2/reference/news", params=params, timeout=10)
        resp.raise_for_status()
        articles = resp.json().get("results", [])
        return [
            {
                "title": a.get("title"),
                "publisher": a.get("publisher", {}).get("name"),
                "tickers": a.get("tickers"),
                "published_utc": a.get("published_utc"),
                "url": a.get("article_url"),
            }
            for a in articles
        ]

    elif tool_name == "get_economic_indicators":
        fred_key = os.environ["FRED_API_KEY"]
        series_map = {
            "Fed Funds Rate": ("FEDFUNDS", "%"),
            "CPI (Index)": ("CPIAUCSL", ""),
            "GDP ($B)": ("GDP", "$B"),
            "Unemployment": ("UNRATE", "%"),
        }
        wanted = [tool_input["indicator"]] if tool_input.get("indicator") else list(series_map)

        result = {}
        for label in wanted:
            series_id, unit = series_map[label]
            resp = requests.get("https://api.stlouisfed.org/fred/series/observations", params={
                "series_id": series_id, "api_key": fred_key, "file_type": "json", "limit": 6, "sort_order": "desc",
            }, timeout=10)
            resp.raise_for_status()
            obs = [o for o in resp.json()["observations"] if o["value"] != "."]
            obs.sort(key=lambda o: o["date"])
            result[label] = {"unit": unit, "observations": obs}
        return result


def analyze(question: str, messages: list) -> str:
    system = SYSTEM_PROMPT.format(date=date.today().isoformat())
    add_user_messages(messages, question)

    while True:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            tools=tools,
            messages=messages,
        )

        # Claude is done — return the answer
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        # Claude wants to call tools — execute each one
        add_assistant_message(messages, response.content)

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                data = run_tool(block.name, block.input, supabase)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(data),
                })

        messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    print("Portfolio Analyzer — ask anything about your holdings. Type 'quit' to exit.\n")

    messages = []

    while True:
        question = input("You: ").strip()
        if question.lower() in ("quit", "exit", "q"):
            break
        if question:
            analyze(question, messages)
