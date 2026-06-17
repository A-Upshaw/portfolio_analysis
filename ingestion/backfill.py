import os
import sys
import requests
from datetime import date, timedelta
from dotenv import load_dotenv
from supabase import create_client
from ingestion.price_fetcher import fetch_polygon_prices, build_rows, upsert_prices, fetch_tickers
import time

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

start_date = date(2026,5,25) #backfilling price_history table 
end_date = date(2026,6,15) #backfilling price_history table 

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
POLYGON_API_KEY = os.environ['POLYGON_API_KEY']

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

our_tickers = fetch_tickers(supabase)

current = start_date
while current <= end_date:
    if current.weekday() >= 5:
        current += timedelta(days=1)
        continue
    print(f"Fetching {current}")
    
    results = fetch_polygon_prices(current)
    rows = build_rows(results,our_tickers,current)
    upsert_prices(supabase,rows)
    time.sleep(12)

    current += timedelta(days=1)
   
