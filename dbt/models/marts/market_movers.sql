with price_with_lag as (
    select
        ticker,
        date,
        open,
        close,
        volume,
        -- Previous trading day's close for this ticker (handles weekends correctly)
        lag(close) over (partition by ticker order by date) as prev_close
    from {{ ref('stg_price_history') }}
),

latest_day as (
    select
        ticker,
        date,
        open,
        close,
        volume,
        prev_close,
        rank() over (partition by ticker order by date desc) as rn
    from price_with_lag
    where prev_close is not null   -- skip tickers with only one day of data
)

select
    m.ticker,
    s.company,
    s.sector,
    m.date,
    m.open,
    m.close,
    round(m.close - m.prev_close, 2)                             as change_dollars,
    round(((m.close - m.prev_close) / m.prev_close) * 100, 2)   as change_pct,
    m.volume
from latest_day m
join {{ source('public', 'stocks') }} s on m.ticker = s.ticker
where m.rn = 1
    -- Exclude split/adjustment artifacts: Polygon back-adjusts prices for splits,
    -- but a ticker's older price_history row can predate that adjustment, producing
    -- a fake ~2x/0.5x "move" overnight. Real single-day moves don't exceed this.
    and abs((m.close - m.prev_close) / m.prev_close) < 0.5
order by change_pct desc