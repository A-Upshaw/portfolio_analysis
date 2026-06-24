from fastapi import FastAPI
from dotenv import load_dotenv
from supabase import create_client
import os

load_dotenv()

app = FastAPI(title="AI Portfolio Analyst API")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

@app.get("/portfolio/summary")
def get_summary():
    result = supabase.table("portfolio_summary").select("*").execute()
    return result.data[0] if result.data else {}

@app.get("/portfolio/positions")
def get_positions():
    result = supabase.table("portfolio_positions").select("*").execute()
    return result.data

@app.get("/portfolio/sector")
def get_sector():
    result = supabase.table("portfolio_sector_exposure").select("*").execute()
    return result.data

@app.get("/portfolio/spy")
def get_spy():
    result = supabase.table("portfolio_vs_spy").select("*").execute()
    return result.data
    