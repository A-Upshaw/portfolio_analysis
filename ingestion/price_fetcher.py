import os
import sys
import requests
from datetime import date, timedelta
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
POLYGON_API_KEY = os.environ['POLYGON_API_KEY']


def get_last_trading_day():
    """Return yesterday, or Friday if today is Monday (skips weekend)."""
    today = date.today()
    if today.weekday() == 0:   # Monday → use Friday
        return today - timedelta(days=3)
    return today - timedelta(days=1)


def fetch_tickers(supabase):
    """Pull all tickers from the stocks table. Returns a set for O(1) lookup."""
    result = supabase.table('stocks').select('ticker').execute()
    return {row['ticker'] for row in result.data}


def fetch_polygon_prices(target_date: date):
    """
    Call Polygon grouped daily bars for all US stocks on target_date.
    Returns the raw results list, or raises on HTTP error.
    One API call covers every ticker — free tier safe.
    """
    url = (
        f'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks'
        f'/{target_date.isoformat()}'
        f'?adjusted=true&apiKey={POLYGON_API_KEY}'
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # resultsCount=0 means the market was closed (holiday) — not an error
    return data.get('results', [])


def build_rows(polygon_results, our_tickers, target_date: date):
    """Filter Polygon's 8k+ results down to our universe and shape the rows."""
    rows = []
    for item in polygon_results:
        ticker = item.get('T')
        if ticker not in our_tickers:
            continue
        rows.append({
            'ticker': ticker,
            'date':   target_date.isoformat(),
            'open':   item.get('o'),
            'high':   item.get('h'),
            'low':    item.get('l'),
            'close':  item.get('c'),
            'volume': int(item['v']) if item.get('v') is not None else None,
        })
    return rows


def upsert_prices(supabase, rows):
    """
    Upsert rows into price_history.
    UNIQUE(ticker, date) constraint means re-runs update instead of duplicating.
    """
    if not rows: # skip empty results market holidays return no data from Polygon
        return
    supabase.table('price_history').upsert(rows, on_conflict='ticker,date').execute()


def main():
    target_date = get_last_trading_day()
    print(f'Date: {target_date}')

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    our_tickers = fetch_tickers(supabase)
    print(f'Our universe: {len(our_tickers)} tickers')

    polygon_results = fetch_polygon_prices(target_date)
    print(f'Polygon returned: {len(polygon_results)} tickers')

    if not polygon_results:
        print('No results from Polygon — market may have been closed. Exiting.')
        sys.exit(0)

    rows = build_rows(polygon_results, our_tickers, target_date)
    matched_tickers = {r['ticker'] for r in rows}
    print(f'Matched our universe: {len(rows)} tickers')

    upsert_prices(supabase, rows)
    print(f'Upserted: {len(rows)} rows into price_history')

    missing = our_tickers - matched_tickers
    if missing:
        print(f'No data for ({len(missing)} tickers): {sorted(missing)}')


if __name__ == '__main__':
    main()
