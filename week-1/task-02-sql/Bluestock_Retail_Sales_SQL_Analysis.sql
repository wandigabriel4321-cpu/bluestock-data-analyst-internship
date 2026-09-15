/*
===============================================================================
BLUESTOCK FINTECH INTERNSHIP - WEEK 1
RETAIL SALES SQL ANALYSIS
Author: Efigénia Wandi Filipe Gabriel
Updated: 10 September 2026
Dataset: Cleaned_Sales_Dataset.csv (simulated training data)
SQL dialect: SQLite 3
===============================================================================

PURPOSE
Analyse customer orders, revenue, profit and product performance while
demonstrating SELECT, WHERE, ORDER BY, GROUP BY, HAVING, JOINs, aggregate
functions, subqueries and basic window functions.

IMPORTANT BUSINESS RULE
Only orders with order_status = 'Completed' contribute revenue, cost and profit.
Cancelled and returned orders remain in the dataset for status analysis, but
their financial values are zero.

HOW TO PREPARE THE DATA IN SQLITE
1. Run the CREATE TABLE statement below.
2. Import Cleaned_Sales_Dataset.csv into sales_data.
3. Keep the option "first row contains column names" enabled, or skip row 1.
4. Confirm that 500 records were imported by running Query 0.

SQLite command-line alternative (run after CREATE TABLE):
    .mode csv
    .import --skip 1 Cleaned_Sales_Dataset.csv sales_data
*/

-- -----------------------------------------------------------------------------
-- DATABASE STRUCTURE
-- The CSV is imported into this table in the exact column order shown below.
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sales_data (
    order_id       TEXT,
    order_date     TEXT,
    customer_id    TEXT,
    customer_name  TEXT,
    segment        TEXT,
    city           TEXT,
    region         TEXT,
    product_id     TEXT,
    product_name   TEXT,
    category       TEXT,
    quantity       INTEGER,
    unit_price     REAL,
    discount       REAL,
    revenue        REAL,
    unit_cost      REAL,
    total_cost     REAL,
    profit         REAL,
    payment_method TEXT,
    order_status   TEXT,
    month          TEXT,
    year           INTEGER
);

-- These views separate the dataset into three logical business entities.
-- Their names use the vw_ prefix to avoid confusion with physical tables.
DROP VIEW IF EXISTS vw_customers;
DROP VIEW IF EXISTS vw_products;
DROP VIEW IF EXISTS vw_orders;

CREATE VIEW vw_customers AS
SELECT
    customer_id,
    MAX(customer_name) AS customer_name,
    MAX(segment) AS segment
FROM sales_data
GROUP BY customer_id;

CREATE VIEW vw_products AS
SELECT
    product_id,
    MAX(product_name) AS product_name,
    MAX(category) AS category,
    MAX(unit_price) AS unit_price,
    MAX(unit_cost) AS unit_cost
FROM sales_data
GROUP BY product_id;

CREATE VIEW vw_orders AS
SELECT
    order_id,
    order_date,
    customer_id,
    product_id,
    city,
    region,
    quantity,
    discount,
    revenue,
    total_cost,
    profit,
    payment_method,
    order_status
FROM sales_data;

-- -----------------------------------------------------------------------------
-- QUERY 0 - IMPORT CHECK
-- Expected result: 500 records, 323 completed, 77 cancelled and 100 returned.
-- -----------------------------------------------------------------------------
SELECT
    COUNT(*) AS total_records,
    SUM(CASE WHEN order_status = 'Completed' THEN 1 ELSE 0 END) AS completed,
    SUM(CASE WHEN order_status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled,
    SUM(CASE WHEN order_status = 'Returned' THEN 1 ELSE 0 END) AS returned
FROM sales_data;

-- -----------------------------------------------------------------------------
-- QUERY 1 - SELECT
-- Preview the first ten records to understand the dataset structure.
-- -----------------------------------------------------------------------------
SELECT *
FROM sales_data
LIMIT 10;

-- -----------------------------------------------------------------------------
-- QUERY 2 - WHERE + ORDER BY
-- Show the ten completed orders with the highest revenue.
-- -----------------------------------------------------------------------------
SELECT
    order_id,
    order_date,
    customer_name,
    product_name,
    revenue,
    profit
FROM sales_data
WHERE order_status = 'Completed'
ORDER BY revenue DESC, order_id
LIMIT 10;

-- -----------------------------------------------------------------------------
-- QUERY 3 - AGGREGATE FUNCTIONS
-- Calculate the five main KPIs used in the Excel dashboard.
-- -----------------------------------------------------------------------------
SELECT
    COUNT(*) AS completed_orders,
    ROUND(SUM(revenue), 2) AS total_revenue,
    ROUND(SUM(profit), 2) AS total_profit,
    ROUND(100.0 * SUM(profit) / NULLIF(SUM(revenue), 0), 2)
        AS profit_margin_pct,
    ROUND(AVG(revenue), 2) AS average_order_value
FROM sales_data
WHERE order_status = 'Completed';

-- -----------------------------------------------------------------------------
-- QUERY 4 - GROUP BY
-- Compare revenue, profit and margin by product category.
-- -----------------------------------------------------------------------------
SELECT
    category,
    COUNT(*) AS completed_orders,
    SUM(quantity) AS units_sold,
    ROUND(SUM(revenue), 2) AS revenue,
    ROUND(SUM(profit), 2) AS profit,
    ROUND(100.0 * SUM(profit) / NULLIF(SUM(revenue), 0), 2) AS margin_pct
FROM sales_data
WHERE order_status = 'Completed'
GROUP BY category
ORDER BY revenue DESC;

-- -----------------------------------------------------------------------------
-- QUERY 5 - GROUP BY
-- Compare sales performance across regions.
-- -----------------------------------------------------------------------------
SELECT
    region,
    COUNT(*) AS completed_orders,
    ROUND(SUM(revenue), 2) AS revenue,
    ROUND(SUM(profit), 2) AS profit,
    ROUND(100.0 * SUM(profit) / NULLIF(SUM(revenue), 0), 2) AS margin_pct
FROM sales_data
WHERE order_status = 'Completed'
GROUP BY region
ORDER BY revenue DESC;

-- -----------------------------------------------------------------------------
-- QUERY 6 - HAVING
-- Find customers whose completed purchases generated more than 15,000 revenue.
-- WHERE filters individual rows; HAVING filters the grouped customer totals.
-- -----------------------------------------------------------------------------
SELECT
    customer_id,
    customer_name,
    COUNT(*) AS completed_orders,
    ROUND(SUM(revenue), 2) AS customer_revenue,
    ROUND(SUM(profit), 2) AS customer_profit
FROM sales_data
WHERE order_status = 'Completed'
GROUP BY customer_id, customer_name
HAVING SUM(revenue) > 15000
ORDER BY customer_revenue DESC;

-- -----------------------------------------------------------------------------
-- QUERY 7 - INNER JOIN
-- Combine orders with customer and product details held in separate views.
-- -----------------------------------------------------------------------------
SELECT
    o.order_id,
    o.order_date,
    c.customer_name,
    c.segment,
    o.region,
    p.product_name,
    p.category,
    o.quantity,
    o.revenue,
    o.profit
FROM vw_orders AS o
INNER JOIN vw_customers AS c
    ON o.customer_id = c.customer_id
INNER JOIN vw_products AS p
    ON o.product_id = p.product_id
WHERE o.order_status = 'Completed'
ORDER BY o.order_date, o.order_id;

-- -----------------------------------------------------------------------------
-- QUERY 8 - PRODUCT PERFORMANCE
-- Rank products by completed-sales revenue.
-- -----------------------------------------------------------------------------
SELECT
    product_id,
    product_name,
    category,
    COUNT(*) AS completed_orders,
    SUM(quantity) AS units_sold,
    ROUND(SUM(revenue), 2) AS revenue,
    ROUND(SUM(profit), 2) AS profit,
    ROUND(100.0 * SUM(profit) / NULLIF(SUM(revenue), 0), 2) AS margin_pct
FROM sales_data
WHERE order_status = 'Completed'
GROUP BY product_id, product_name, category
ORDER BY revenue DESC;

-- -----------------------------------------------------------------------------
-- QUERY 9 - CUSTOMER ORDER ANALYSIS
-- Identify the most valuable customers by completed-sales revenue.
-- -----------------------------------------------------------------------------
SELECT
    customer_id,
    customer_name,
    segment,
    COUNT(*) AS completed_orders,
    ROUND(SUM(revenue), 2) AS total_revenue,
    ROUND(AVG(revenue), 2) AS average_order_value
FROM sales_data
WHERE order_status = 'Completed'
GROUP BY customer_id, customer_name, segment
ORDER BY total_revenue DESC
LIMIT 10;

-- -----------------------------------------------------------------------------
-- QUERY 10 - SUBQUERY
-- Return products whose revenue is above the average product revenue.
-- -----------------------------------------------------------------------------
SELECT
    product_id,
    product_name,
    ROUND(SUM(revenue), 2) AS product_revenue
FROM sales_data
WHERE order_status = 'Completed'
GROUP BY product_id, product_name
HAVING SUM(revenue) > (
    SELECT AVG(product_revenue)
    FROM (
        SELECT SUM(revenue) AS product_revenue
        FROM sales_data
        WHERE order_status = 'Completed'
        GROUP BY product_id
    ) AS product_totals
)
ORDER BY product_revenue DESC;

-- -----------------------------------------------------------------------------
-- QUERY 11 - MONTHLY TREND
-- Summarise completed revenue, profit and orders by month.
-- -----------------------------------------------------------------------------
SELECT
    strftime('%Y-%m', order_date) AS sales_month,
    COUNT(*) AS completed_orders,
    ROUND(SUM(revenue), 2) AS revenue,
    ROUND(SUM(profit), 2) AS profit
FROM sales_data
WHERE order_status = 'Completed'
GROUP BY strftime('%Y-%m', order_date)
ORDER BY sales_month;

-- -----------------------------------------------------------------------------
-- QUERY 12 - WINDOW FUNCTION: RANK
-- Rank products by revenue inside their own category.
-- -----------------------------------------------------------------------------
WITH product_totals AS (
    SELECT
        category,
        product_name,
        SUM(revenue) AS revenue,
        SUM(profit) AS profit
    FROM sales_data
    WHERE order_status = 'Completed'
    GROUP BY category, product_name
)
SELECT
    category,
    product_name,
    ROUND(revenue, 2) AS revenue,
    ROUND(profit, 2) AS profit,
    RANK() OVER (
        PARTITION BY category
        ORDER BY revenue DESC
    ) AS revenue_rank
FROM product_totals
ORDER BY category, revenue_rank, product_name;

-- -----------------------------------------------------------------------------
-- QUERY 13 - WINDOW FUNCTION: LAG
-- Compare each month with the previous month.
-- -----------------------------------------------------------------------------
WITH monthly_sales AS (
    SELECT
        strftime('%Y-%m', order_date) AS sales_month,
        SUM(revenue) AS revenue
    FROM sales_data
    WHERE order_status = 'Completed'
    GROUP BY strftime('%Y-%m', order_date)
), monthly_comparison AS (
    SELECT
        sales_month,
        revenue,
        LAG(revenue) OVER (ORDER BY sales_month) AS previous_month_revenue
    FROM monthly_sales
)
SELECT
    sales_month,
    ROUND(revenue, 2) AS revenue,
    ROUND(previous_month_revenue, 2) AS previous_month_revenue,
    ROUND(
        100.0 * (revenue - previous_month_revenue)
        / NULLIF(previous_month_revenue, 0),
        2
    ) AS month_over_month_pct
FROM monthly_comparison
ORDER BY sales_month;

-- -----------------------------------------------------------------------------
-- QUERY 14 - WINDOW FUNCTION: RUNNING TOTAL
-- Show how revenue accumulates throughout the year.
-- -----------------------------------------------------------------------------
WITH monthly_sales AS (
    SELECT
        strftime('%Y-%m', order_date) AS sales_month,
        SUM(revenue) AS revenue
    FROM sales_data
    WHERE order_status = 'Completed'
    GROUP BY strftime('%Y-%m', order_date)
)
SELECT
    sales_month,
    ROUND(revenue, 2) AS monthly_revenue,
    ROUND(
        SUM(revenue) OVER (
            ORDER BY sales_month
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ),
        2
    ) AS cumulative_revenue
FROM monthly_sales
ORDER BY sales_month;

-- -----------------------------------------------------------------------------
-- QUERY 15 - PAYMENT METHOD ANALYSIS
-- Compare order completion and revenue by payment method.
-- -----------------------------------------------------------------------------
SELECT
    payment_method,
    COUNT(*) AS all_orders,
    SUM(CASE WHEN order_status = 'Completed' THEN 1 ELSE 0 END)
        AS completed_orders,
    ROUND(
        100.0 * SUM(CASE WHEN order_status = 'Completed' THEN 1 ELSE 0 END)
        / COUNT(*),
        2
    ) AS completion_rate_pct,
    ROUND(SUM(revenue), 2) AS completed_revenue
FROM sales_data
GROUP BY payment_method
ORDER BY completed_revenue DESC;

-- -----------------------------------------------------------------------------
-- QUERY 16 - ORDER STATUS DISTRIBUTION
-- Show the volume and percentage of completed, cancelled and returned orders.
-- -----------------------------------------------------------------------------
SELECT
    order_status,
    COUNT(*) AS orders,
    ROUND(
        100.0 * COUNT(*) / (SELECT COUNT(*) FROM sales_data),
        2
    ) AS share_pct
FROM sales_data
GROUP BY order_status
ORDER BY orders DESC;

-- -----------------------------------------------------------------------------
-- QUERY 17 - DISCOUNT ANALYSIS
-- Compare sales and profitability across discount ranges.
-- -----------------------------------------------------------------------------
SELECT
    CASE
        WHEN discount = 0 THEN 'No discount'
        WHEN discount <= 0.10 THEN '1%-10%'
        ELSE 'Above 10%'
    END AS discount_band,
    COUNT(*) AS completed_orders,
    ROUND(SUM(revenue), 2) AS revenue,
    ROUND(SUM(profit), 2) AS profit,
    ROUND(100.0 * SUM(profit) / NULLIF(SUM(revenue), 0), 2) AS margin_pct
FROM sales_data
WHERE order_status = 'Completed'
GROUP BY discount_band
ORDER BY revenue DESC;

-- -----------------------------------------------------------------------------
-- QUERY 18 - DATA QUALITY CHECK
-- Every result below should be zero after cleaning.
-- -----------------------------------------------------------------------------
SELECT
    SUM(CASE WHEN order_id IS NULL OR TRIM(order_id) = '' THEN 1 ELSE 0 END)
        AS missing_order_ids,
    SUM(CASE WHEN customer_name IS NULL OR TRIM(customer_name) = '' THEN 1 ELSE 0 END)
        AS missing_customer_names,
    SUM(CASE WHEN product_name IS NULL OR TRIM(product_name) = '' THEN 1 ELSE 0 END)
        AS missing_product_names,
    SUM(CASE WHEN region NOT IN ('North', 'South', 'East', 'West') THEN 1 ELSE 0 END)
        AS invalid_regions,
    SUM(CASE WHEN discount < 0 OR discount > 1 THEN 1 ELSE 0 END)
        AS invalid_discounts,
    COUNT(*) - COUNT(DISTINCT order_id) AS duplicate_order_ids
FROM sales_data;

-- -----------------------------------------------------------------------------
-- QUERY 19 - DASHBOARD RECONCILIATION CHECK
-- Expected result: PASS for every line.
-- This proves that SQL and Excel use the same business rules and totals.
-- -----------------------------------------------------------------------------
WITH actual AS (
    SELECT
        COUNT(*) AS completed_orders,
        ROUND(SUM(revenue), 0) AS total_revenue,
        ROUND(SUM(profit), 0) AS total_profit,
        ROUND(100.0 * SUM(profit) / NULLIF(SUM(revenue), 0), 1)
            AS profit_margin_pct,
        ROUND(AVG(revenue), 0) AS average_order_value
    FROM sales_data
    WHERE order_status = 'Completed'
)
SELECT 'Completed Orders' AS metric,
       completed_orders AS actual_value,
       323 AS expected_value,
       CASE WHEN completed_orders = 323 THEN 'PASS' ELSE 'CHECK' END AS result
FROM actual
UNION ALL
SELECT 'Total Revenue', total_revenue, 1164271,
       CASE WHEN total_revenue = 1164271 THEN 'PASS' ELSE 'CHECK' END
FROM actual
UNION ALL
SELECT 'Total Profit', total_profit, 397041,
       CASE WHEN total_profit = 397041 THEN 'PASS' ELSE 'CHECK' END
FROM actual
UNION ALL
SELECT 'Profit Margin (%)', profit_margin_pct, 34.1,
       CASE WHEN profit_margin_pct = 34.1 THEN 'PASS' ELSE 'CHECK' END
FROM actual
UNION ALL
SELECT 'Average Order Value', average_order_value, 3605,
       CASE WHEN average_order_value = 3605 THEN 'PASS' ELSE 'CHECK' END
FROM actual;

/*
EXPECTED HIGH-LEVEL INSIGHTS
- Total revenue: 1,164,271
- Total profit: 397,041
- Profit margin: 34.1%
- Completed orders: 323
- Average order value: 3,605
- Highest-revenue category: Electronics
- Highest-revenue region: North
- Highest-revenue month: October 2025
*/
