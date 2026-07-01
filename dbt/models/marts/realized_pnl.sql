with cost_basis as(
    SELECT ticker, account, sum(shares * purchase_price) / sum(shares) as avg_cost_per_share
    FROM {{ source('public', 'portfolio') }}
    Group by ticker, account
),
sales_enriched as(
    Select s.ticker, 
            s.account, 
            s.shares, 
            s.sale_price, 
            s.sale_date, 
            cb.avg_cost_per_share, 
            ss.company, 
            ss.sector
    from {{ source('public', 'sales') }} s
    left join cost_basis cb on s.ticker = cb.ticker and s.account = cb.account
    left join {{ ref('stg_stocks') }} ss on cb.ticker = ss.ticker
)

Select ticker,
        company,
        sector,
        account,
        shares,
        sale_price,
        sale_date,
        avg_cost_per_share,
        (sale_price - avg_cost_per_share) * shares as realized_gain_loss,
        (sale_price - avg_cost_per_share) / avg_cost_per_share * 100 as realized_gain_loss_pct 
from sales_enriched 