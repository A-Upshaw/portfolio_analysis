SELECT
    sum(current_value) as total_market_value,
    sum(cost_basis) as total_cost_basis,
    sum(unrealized_gain_loss) as total_gain_loss_dollars,
    round((sum(unrealized_gain_loss) / sum(cost_basis)) * 100, 2) as portfolio_gain_loss_pct,
    count(distinct ticker)           as num_positions,
    count(*)                         as num_lots,
    max(unrealized_gain_loss_pct)                     as best_position_pct,
    min(unrealized_gain_loss_pct)                     as worst_position_pct,
    max(price_date)                  as as_of_date

from {{ ref('portfolio_positions') }}