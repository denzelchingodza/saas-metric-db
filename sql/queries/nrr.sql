
-- NET REVENUE RETENTION------------------------------------------------------------------
-- NRR measures whether existing customers are spending more over time
-- NRR > 100% means expansion revenue outweighs churn + contraction
-- NRR < 100% means you are losing more than you are gaining from existing customers

WITH month_series AS (
    SELECT DISTINCT DATE_TRUNC('month', started_at) AS month
    FROM subscriptions
    ORDER BY month
),
starting_mrr AS (
    SELECT
        DATE_TRUNC('month', s.started_at) AS month,
        SUM(
            CASE
                WHEN s.billing_cycle = 'annual' THEN p.price_annual / 12
                ELSE p.price_monthly
            END
        ) AS mrr
    FROM subscriptions s
    JOIN plans p ON p.id = s.plan_id
    GROUP BY month
),
ending_mrr AS (
    SELECT
        DATE_TRUNC('month', s.started_at) AS cohort_month,
        SUM(
            CASE
                WHEN s.status = 'active' AND s.billing_cycle = 'annual'
                    THEN p.price_annual / 12
                WHEN s.status = 'active'
                    THEN p.price_monthly
                ELSE 0
            END
        ) AS retained_mrr
    FROM subscriptions s
    JOIN plans p ON p.id = s.plan_id
    GROUP BY cohort_month
)
SELECT
    sm.month::date                                      AS month,
    ROUND(s.mrr::NUMERIC, 2)                            AS starting_mrr,
    ROUND(e.retained_mrr::NUMERIC, 2)                   AS retained_mrr,
    ROUND(
        e.retained_mrr::NUMERIC
        / NULLIF(s.mrr, 0) * 100
    , 1)                                                AS nrr_pct
FROM month_series sm
JOIN starting_mrr s ON s.month = sm.month
JOIN ending_mrr e   ON e.cohort_month = sm.month
ORDER BY sm.month;