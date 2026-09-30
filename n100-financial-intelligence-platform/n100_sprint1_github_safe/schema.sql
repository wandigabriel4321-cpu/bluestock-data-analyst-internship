-- N100 Financial Intelligence Platform — Sprint 1 SQLite schema
-- The application must also enable foreign keys for every new connection.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY
        CHECK (length(id) BETWEEN 2 AND 12 AND id = upper(trim(id))),
    company_logo TEXT,
    company_name TEXT NOT NULL,
    chart_link TEXT,
    about_company TEXT,
    website TEXT,
    nse_profile TEXT,
    bse_profile TEXT,
    face_value REAL,
    book_value REAL,
    roce_percentage REAL,
    roe_percentage REAL
);

CREATE TABLE IF NOT EXISTS profitandloss (
    id INTEGER NOT NULL UNIQUE,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL CHECK (year GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    sales REAL,
    expenses REAL,
    operating_profit REAL,
    opm_percentage REAL,
    other_income REAL,
    interest REAL,
    depreciation REAL,
    profit_before_tax REAL,
    tax_percentage REAL,
    net_profit REAL,
    eps REAL,
    dividend_payout REAL,
    PRIMARY KEY (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS balancesheet (
    id INTEGER NOT NULL UNIQUE,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL CHECK (year GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    equity_capital REAL,
    reserves REAL,
    borrowings REAL,
    other_liabilities REAL,
    total_liabilities REAL,
    fixed_assets REAL,
    cwip REAL,
    investments REAL,
    other_asset REAL,
    total_assets REAL,
    PRIMARY KEY (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS cashflow (
    id INTEGER NOT NULL UNIQUE,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL CHECK (year GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    operating_activity REAL,
    investing_activity REAL,
    financing_activity REAL,
    net_cash_flow REAL,
    PRIMARY KEY (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS analysis (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    compounded_sales_growth TEXT,
    compounded_profit_growth TEXT,
    stock_price_cagr TEXT,
    roe TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL CHECK (year GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    annual_report TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS prosandcons (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    pros TEXT,
    cons TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS sectors (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL UNIQUE,
    broad_sector TEXT NOT NULL,
    sub_sector TEXT,
    index_weight_pct REAL,
    market_cap_category TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS market_cap (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL CHECK (year GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    market_cap_crore REAL,
    enterprise_value_crore REAL,
    pe_ratio REAL,
    pb_ratio REAL,
    ev_ebitda REAL,
    dividend_yield_pct REAL,
    UNIQUE (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS stock_prices (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    date TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    open_price REAL,
    high_price REAL,
    low_price REAL,
    close_price REAL,
    volume INTEGER,
    adjusted_close REAL,
    UNIQUE (company_id, date),
    FOREIGN KEY (company_id) REFERENCES companies(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Sprint 2 analytical output, finalised on Day 12.  The authoritative grain is
-- one row per key in the UNION of P&L, Balance Sheet and Cash Flow company-year
-- combinations.  Nullable KPI values represent documented source/denominator
-- edge cases, never fabricated zeroes.
CREATE TABLE IF NOT EXISTS financial_ratios (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL CHECK (year GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    broad_sector TEXT,
    is_financials INTEGER NOT NULL DEFAULT 0 CHECK (is_financials IN (0, 1)),
    net_profit_margin_pct REAL,
    operating_profit_margin_pct REAL,
    opm_source_pct REAL,
    opm_difference_pct_points REAL,
    opm_mismatch_flag INTEGER NOT NULL DEFAULT 0
        CHECK (opm_mismatch_flag IN (0, 1)),
    return_on_equity_pct REAL,
    return_on_capital_employed_pct REAL,
    return_on_assets_pct REAL,
    debt_to_equity REAL,
    high_leverage_flag INTEGER CHECK (high_leverage_flag IN (0, 1)),
    interest_coverage REAL,
    icr_label TEXT,
    icr_warning_flag INTEGER CHECK (icr_warning_flag IN (0, 1)),
    net_debt_cr REAL,
    asset_turnover REAL,
    free_cash_flow_cr REAL,
    capex_cr REAL,
    capex_intensity_pct REAL,
    capex_intensity_label TEXT,
    earnings_per_share REAL,
    book_value_per_share REAL,
    dividend_payout_ratio_pct REAL,
    total_debt_cr REAL,
    cash_from_operations_cr REAL,
    -- CAGR flags are stored separately from values. Supported states are:
    -- OK, DECLINE_TO_LOSS, TURNAROUND, BOTH_NEGATIVE, ZERO_BASE, INSUFFICIENT.
    revenue_cagr_3yr REAL,
    revenue_cagr_3yr_flag TEXT,
    revenue_cagr_5yr REAL,
    revenue_cagr_5yr_flag TEXT,
    revenue_cagr_10yr REAL,
    revenue_cagr_10yr_flag TEXT,
    pat_cagr_3yr REAL,
    pat_cagr_3yr_flag TEXT,
    pat_cagr_5yr REAL,
    pat_cagr_5yr_flag TEXT,
    pat_cagr_10yr REAL,
    pat_cagr_10yr_flag TEXT,
    eps_cagr_3yr REAL,
    eps_cagr_3yr_flag TEXT,
    eps_cagr_5yr REAL,
    eps_cagr_5yr_flag TEXT,
    eps_cagr_10yr REAL,
    eps_cagr_10yr_flag TEXT,
    cfo_pat_ratio_5yr REAL,
    cfo_quality_label TEXT,
    fcf_conversion_rate_pct REAL,
    composite_quality_score REAL,
    UNIQUE (company_id, year),
    FOREIGN KEY (company_id) REFERENCES companies(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_profitandloss_year
    ON profitandloss(year);
CREATE INDEX IF NOT EXISTS idx_balancesheet_year
    ON balancesheet(year);
CREATE INDEX IF NOT EXISTS idx_cashflow_year
    ON cashflow(year);
CREATE INDEX IF NOT EXISTS idx_documents_company_year
    ON documents(company_id, year);
CREATE INDEX IF NOT EXISTS idx_market_cap_year
    ON market_cap(year);
CREATE INDEX IF NOT EXISTS idx_stock_prices_company_date
    ON stock_prices(company_id, date);
CREATE INDEX IF NOT EXISTS idx_financial_ratios_year
    ON financial_ratios(year);
CREATE INDEX IF NOT EXISTS idx_financial_ratios_sector_year
    ON financial_ratios(broad_sector, year);
