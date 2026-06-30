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
        result = supabase.table("portfolio_vs_spy").select("*").limit(days).execute()
        return result.data


def analyze(question: str) -> str:
    system = SYSTEM_PROMPT.format(date=date.today().isoformat())
    messages = [{"role": "user", "content": question}]

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
        messages.append({"role": "assistant", "content": response.content})

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
    while True:
        question = input("You: ").strip()
        if question.lower() in ("quit", "exit", "q"):
            break
        if question:
            analyze(question)
