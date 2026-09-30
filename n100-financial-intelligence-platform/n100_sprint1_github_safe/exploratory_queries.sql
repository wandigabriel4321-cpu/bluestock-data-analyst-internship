-- N100 Financial Intelligence Platform
-- Day 21: ten reproducible exploratory SQLite queries

-- Q01: Row counts for every Sprint 1 table
SELECT 'companies' AS table_name, COUNT(*) AS row_count FROM companies
UNION ALL SELECT 'profitandloss', COUNT(*) FROM profitandloss
UNION ALL SELECT 'balancesheet', COUNT(*) FROM balancesheet
UNION ALL SELECT 'cashflow', COUNT(*) FROM cashflow
UNION ALL SELECT 'analysis', COUNT(*) FROM analysis
UNION ALL SELECT 'documents', COUNT(*) FROM documents
UNION ALL SELECT 'prosandcons', COUNT(*) FROM prosandcons
UNION ALL SELECT 'sectors', COUNT(*) FROM sectors
UNION ALL SELECT 'market_cap', COUNT(*) FROM market_cap
UNION ALL SELECT 'stock_prices', COUNT(*) FROM stock_prices;

-- Q02: Company distribution by broad sector
SELECT
    s.broad_sector,
    COUNT(DISTINCT s.company_id) AS company_count,
    ROUND(SUM(s.index_weight_pct), 2) AS total_index_weight_pct
FROM sectors AS s
GROUP BY s.broad_sector
ORDER BY company_count DESC, s.broad_sector;

-- Q03: Ten largest companies by their latest available market capitalisation
WITH latest_year AS (
    SELECT company_id, MAX(year) AS year
    FROM market_cap
    GROUP BY company_id
)
SELECT
    c.id AS company_id,
    c.company_name,
    m.year,
    ROUND(m.market_cap_crore, 2) AS market_cap_crore,
    ROUND(m.enterprise_value_crore, 2) AS enterprise_value_crore
FROM latest_year AS ly
JOIN market_cap AS m
  ON m.company_id = ly.company_id AND m.year = ly.year
JOIN companies AS c ON c.id = m.company_id
ORDER BY m.market_cap_crore DESC
LIMIT 10;

-- Q04: Ten companies with the highest sales in their latest reporting year
WITH latest_year AS (
    SELECT company_id, MAX(year) AS year
    FROM profitandloss
    GROUP BY company_id
)
SELECT
    c.id AS company_id,
    c.company_name,
    p.year,
    ROUND(p.sales, 2) AS sales,
    ROUND(p.net_profit, 2) AS net_profit
FROM latest_year AS ly
JOIN profitandloss AS p
  ON p.company_id = ly.company_id AND p.year = ly.year
JOIN companies AS c ON c.id = p.company_id
ORDER BY p.sales DESC
LIMIT 10;

-- Q05: Highest calculated operating margins in the latest reporting year
WITH latest_year AS (
    SELECT company_id, MAX(year) AS year
    FROM profitandloss
    GROUP BY company_id
)
SELECT
    c.id AS company_id,
    c.company_name,
    p.year,
    ROUND(p.opm_percentage, 2) AS source_opm_pct,
    ROUND(100.0 * p.operating_profit / NULLIF(p.sales, 0), 2) AS calculated_opm_pct
FROM latest_year AS ly
JOIN profitandloss AS p
  ON p.company_id = ly.company_id AND p.year = ly.year
JOIN companies AS c ON c.id = p.company_id
WHERE p.sales > 0
ORDER BY calculated_opm_pct DESC
LIMIT 10;

-- Q06: Borrowings relative to assets in the latest balance-sheet year
WITH latest_year AS (
    SELECT company_id, MAX(year) AS year
    FROM balancesheet
    GROUP BY company_id
)
SELECT
    c.id AS company_id,
    c.company_name,
    b.year,
    ROUND(b.borrowings, 2) AS borrowings,
    ROUND(b.total_assets, 2) AS total_assets,
    ROUND(100.0 * b.borrowings / NULLIF(b.total_assets, 0), 2) AS borrowings_to_assets_pct
FROM latest_year AS ly
JOIN balancesheet AS b
  ON b.company_id = ly.company_id AND b.year = ly.year
JOIN companies AS c ON c.id = b.company_id
WHERE b.total_assets > 0
ORDER BY borrowings_to_assets_pct DESC
LIMIT 10;

-- Q07: Operating cash flow compared with net profit for matching years
SELECT
    c.id AS company_id,
    c.company_name,
    cf.year,
    ROUND(cf.operating_activity, 2) AS operating_cash_flow,
    ROUND(p.net_profit, 2) AS net_profit,
    ROUND(cf.operating_activity / NULLIF(p.net_profit, 0), 2) AS cash_to_profit_ratio
FROM cashflow AS cf
JOIN profitandloss AS p
  ON p.company_id = cf.company_id AND p.year = cf.year
JOIN companies AS c ON c.id = cf.company_id
WHERE p.net_profit > 0
ORDER BY cash_to_profit_ratio DESC
LIMIT 15;

-- Q08: Stock-price return from first to last available date
WITH date_bounds AS (
    SELECT company_id, MIN(date) AS first_date, MAX(date) AS last_date
    FROM stock_prices
    GROUP BY company_id
), price_bounds AS (
    SELECT
        d.company_id,
        d.first_date,
        d.last_date,
        first_price.adjusted_close AS first_adjusted_close,
        last_price.adjusted_close AS last_adjusted_close
    FROM date_bounds AS d
    JOIN stock_prices AS first_price
      ON first_price.company_id = d.company_id AND first_price.date = d.first_date
    JOIN stock_prices AS last_price
      ON last_price.company_id = d.company_id AND last_price.date = d.last_date
)
SELECT
    c.id AS company_id,
    c.company_name,
    p.first_date,
    p.last_date,
    ROUND(p.first_adjusted_close, 2) AS first_adjusted_close,
    ROUND(p.last_adjusted_close, 2) AS last_adjusted_close,
    ROUND(100.0 * (p.last_adjusted_close / NULLIF(p.first_adjusted_close, 0) - 1), 2) AS return_pct
FROM price_bounds AS p
JOIN companies AS c ON c.id = p.company_id
ORDER BY return_pct DESC
LIMIT 10;

-- Q09: Annual-data coverage by company
WITH pl AS (
    SELECT company_id, COUNT(DISTINCT year) AS pl_years
    FROM profitandloss GROUP BY company_id
), bs AS (
    SELECT company_id, COUNT(DISTINCT year) AS bs_years
    FROM balancesheet GROUP BY company_id
), cf AS (
    SELECT company_id, COUNT(DISTINCT year) AS cf_years
    FROM cashflow GROUP BY company_id
)
SELECT
    c.id AS company_id,
    c.company_name,
    COALESCE(pl.pl_years, 0) AS profitandloss_years,
    COALESCE(bs.bs_years, 0) AS balancesheet_years,
    COALESCE(cf.cf_years, 0) AS cashflow_years,
    CASE
        WHEN MIN(COALESCE(pl.pl_years, 0), COALESCE(bs.bs_years, 0), COALESCE(cf.cf_years, 0)) >= 5
        THEN 'PASS' ELSE 'REVIEW'
    END AS coverage_status
FROM companies AS c
LEFT JOIN pl ON pl.company_id = c.id
LEFT JOIN bs ON bs.company_id = c.id
LEFT JOIN cf ON cf.company_id = c.id
ORDER BY coverage_status DESC, c.id;

-- Q10: Latest integrated financial and market snapshot
WITH latest_pl AS (
    SELECT company_id, MAX(year) AS year FROM profitandloss GROUP BY company_id
), latest_mc AS (
    SELECT company_id, MAX(year) AS year FROM market_cap GROUP BY company_id
), latest_price AS (
    SELECT company_id, MAX(date) AS date FROM stock_prices GROUP BY company_id
)
SELECT
    c.id AS company_id,
    c.company_name,
    s.broad_sector,
    p.year AS financial_year,
    ROUND(p.sales, 2) AS sales,
    ROUND(p.net_profit, 2) AS net_profit,
    ROUND(m.market_cap_crore, 2) AS market_cap_crore,
    sp.date AS price_date,
    ROUND(sp.adjusted_close, 2) AS adjusted_close
FROM companies AS c
LEFT JOIN sectors AS s ON s.company_id = c.id
LEFT JOIN latest_pl AS lp ON lp.company_id = c.id
LEFT JOIN profitandloss AS p
  ON p.company_id = lp.company_id AND p.year = lp.year
LEFT JOIN latest_mc AS lm ON lm.company_id = c.id
LEFT JOIN market_cap AS m
  ON m.company_id = lm.company_id AND m.year = lm.year
LEFT JOIN latest_price AS lpr ON lpr.company_id = c.id
LEFT JOIN stock_prices AS sp
  ON sp.company_id = lpr.company_id AND sp.date = lpr.date
ORDER BY m.market_cap_crore DESC, c.id;
