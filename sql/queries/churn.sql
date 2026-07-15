-- MONTHLY CHURN RATE-------------------------------------------------

-- Churn rate = customers lost in a month / customers at the start of that month

WITH monthly_starts AS (
    SELECT
        DATE_TRUNC('month', started_at) AS month,
        COUNT(*)                         AS new_subs
    FROM subscriptions
    GROUP BY month
),
monthly_churned AS (
    SELECT
        DATE_TRUNC('month', cancelled_at) AS month,
        COUNT(*)                           AS churned
    FROM subscriptions
    WHERE cancelled_at IS NOT NULL
    GROUP BY month
)
SELECT
    ms.month,
    ms.new_subs,
    COALESCE(mc.churned, 0)            AS churned,
    ROUND(
        COALESCE(mc.churned, 0)::NUMERIC
        / NULLIF(ms.new_subs, 0) * 100
    , 2)                               AS churn_rate_pct
FROM monthly_starts ms
LEFT JOIN monthly_churned mc ON mc.month = ms.month
ORDER BY ms.month;