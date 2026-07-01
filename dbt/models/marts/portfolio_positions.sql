with latest_price as(
    select 
        ticker,
        close as current_price,
        date as price_date,
        row_number() over (PARTITION BY ticker ORDER BY date desc) as rn
    FROM {{ ref('stg_price_history') }}
),

current_prices as(
    select
        ticker,
        current_price,
        price_date
    from latest_price
    where rn = 1

)

select
    p.account,
    s.company,
    s.sector,
    p.ticker,
    cp.current_price,
    cp.price_date,
    p.shares,
    p.purchase_price,
    round(p.shares * p.purchase_price,2) as cost_basis,
    round(p.shares * cp.current_price,2) as current_value,
    round((p.shares * cp.current_price) - (p.shares * p.purchase_price), 2) as unrealized_gain_loss,
    round((cp.current_price - p.purchase_price)/ p.purchase_price * 100,2) as unrealized_gain_loss_pct,
    round(sum(shares * purchase_price) OVER (PARTITION BY p.ticker, p.account) / sum(shares) OVER (PARTITION BY p.ticker, p.account),4) as weighted_avg_cost
from {{ ref('stg_portfolio') }} p
left join current_prices cp on p.ticker = cp.ticker
left join stocks s on p.ticker = s.ticker


