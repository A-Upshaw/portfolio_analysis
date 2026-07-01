-- STOCK ANALYSIS DATABASE SETUP
--  Schema: stocks, price_history, fundamentals, portfolio
-- ============================================================

--  STEP 1: CREATE TABLES
--  Order matters — stocks has no foreign keys, so it goes first.
--  price_history, fundamentals, and portfolio all reference stocks.
-- ============================================================

-- Reference/lookup table — one row per ticker, relatively static
CREATE TABLE IF NOT EXISTS stocks (
    ticker       VARCHAR(20)  PRIMARY KEY,
    company      TEXT         NOT NULL,
    sector       TEXT,
    industry     TEXT,
    theme        TEXT,        -- e.g. "S&P 500", "AI Infrastructure - Power"
    asset_type   TEXT,        -- Equity, ETF, REIT, Crypto
    exchange     TEXT         -- NYQ, NMS, etc.
);

-- Daily price data — one row per ticker per day
-- UNIQUE(ticker, date) prevents duplicate rows on re-runs
CREATE TABLE IF NOT EXISTS price_history (
    id        BIGSERIAL     PRIMARY KEY,
    ticker    VARCHAR(20)   NOT NULL REFERENCES stocks(ticker),
    date      DATE          NOT NULL,
    open      NUMERIC(12,4),
    high      NUMERIC(12,4),
    low       NUMERIC(12,4),
    close     NUMERIC(12,4),
    volume    BIGINT,
    UNIQUE (ticker, date)
);

-- Quarterly financials — one row per ticker per quarter
-- period format: '2025-Q1', '2025-Q2', etc.
-- UNIQUE(ticker, period) ensures one snapshot per quarter
CREATE TABLE IF NOT EXISTS fundamentals (
    id                 BIGSERIAL     PRIMARY KEY,
    ticker             VARCHAR(20)   NOT NULL REFERENCES stocks(ticker),
    period             VARCHAR(10)   NOT NULL,   -- e.g. '2025-Q2'
    snapshot_date      DATE          NOT NULL,   -- date the data was pulled
    revenue            NUMERIC(20,2),            -- totalRevenue
    ebitda             NUMERIC(20,2),
    ebitda_margin      NUMERIC(8,6),             -- ebitdaMargins
    gross_margin       NUMERIC(8,6),             -- grossMargins
    operating_margin   NUMERIC(8,6),             -- operatingMargins
    profit_margin      NUMERIC(8,6),             -- profitMargins
    free_cashflow      NUMERIC(20,2),
    operating_cashflow NUMERIC(20,2),
    trailing_pe        NUMERIC(12,4),
    forward_pe         NUMERIC(12,4),
    peg_ratio          NUMERIC(8,4),
    price_to_book      NUMERIC(8,4),
    enterprise_value   NUMERIC(20,2),
    revenue_growth     NUMERIC(8,6),
    earnings_growth    NUMERIC(8,6),
    return_on_equity   NUMERIC(8,6),
    return_on_assets   NUMERIC(8,6),
    debt_to_equity     NUMERIC(10,4),
    trailing_eps       NUMERIC(10,4),
    forward_eps        NUMERIC(10,4),
    UNIQUE (ticker, period)
);

-- Your positions — one row per buy lot for accurate cost-basis P&L
CREATE TABLE IF NOT EXISTS portfolio (
    id             BIGSERIAL     PRIMARY KEY,
    ticker         VARCHAR(20)   NOT NULL REFERENCES stocks(ticker),
    account        TEXT          NOT NULL,   -- e.g. 'Robinhood', 'Webull'
    shares         NUMERIC(12,4) NOT NULL,
    purchase_price NUMERIC(12,4) NOT NULL,
    purchase_date  DATE          NOT NULL
);

-- One row per sell transaction
CREATE TABLE IF NOT EXISTS sales (
    id          BIGSERIAL     PRIMARY KEY,
    ticker      VARCHAR(20)   NOT NULL REFERENCES stocks(ticker),
    account     TEXT          NOT NULL,
    shares      NUMERIC(12,4) NOT NULL,
    sale_price  NUMERIC(12,4) NOT NULL,
    sale_date   DATE          NOT NULL
);


-- ============================================================
--  QUICK REFERENCE: TABLE RELATIONSHIPS
--
--  stocks (ticker) <── price_history.ticker
--  stocks (ticker) <── fundamentals.ticker
--  stocks (ticker) <── portfolio.ticker
--
--  stocks is the parent — always seed it first before loading
--  data into the other three tables.
-- ============================================================
