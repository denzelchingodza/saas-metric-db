
-- COHORT RETENTION-------------------------------------------------------
-- Groups customers by the month they signed up (cohort)
-- Then tracks what % are still active at month 1, 3, 6, 12

WITH cohorts AS (
    SELECT
        customer_id,
        DATE_TRUNC('month', started_at) AS cohort_month,
        started_at
    FROM subscriptions
    WHERE started_at = (
        SELECT MIN(started_at) FROM subscriptions s2
        WHERE s2.customer_id = subscriptions.customer_id
    )
),
cohort_sizes AS (
    SELECT
        cohort_month,
        COUNT(DISTINCT customer_id) AS cohort_size
    FROM cohorts
    GROUP BY cohort_month
),
retention AS (
    SELECT
        c.cohort_month,
        COUNT(DISTINCT CASE
            WHEN s.started_at <= c.started_at + INTERVAL '1 month'
            AND (s.cancelled_at IS NULL OR s.cancelled_at > c.started_at + INTERVAL '1 month')
            THEN c.customer_id END) AS retained_m1,
        COUNT(DISTINCT CASE
            WHEN s.started_at <= c.started_at + INTERVAL '3 months'
            AND (s.cancelled_at IS NULL OR s.cancelled_at > c.started_at + INTERVAL '3 months')
            THEN c.customer_id END) AS retained_m3,
        COUNT(DISTINCT CASE
            WHEN s.started_at <= c.started_at + INTERVAL '6 months'
            AND (s.cancelled_at IS NULL OR s.cancelled_at > c.started_at + INTERVAL '6 months')
            THEN c.customer_id END) AS retained_m6,
        COUNT(DISTINCT CASE
            WHEN s.started_at <= c.started_at + INTERVAL '12 months'
            AND (s.cancelled_at IS NULL OR s.cancelled_at > c.started_at + INTERVAL '12 months')
            THEN c.customer_id END) AS retained_m12
    FROM cohorts c
    JOIN subscriptions s ON s.customer_id = c.customer_id
    GROUP BY c.cohort_month
)
SELECT
    r.cohort_month::date                                          AS cohort,
    cs.cohort_size,
    ROUND(r.retained_m1  * 100.0 / NULLIF(cs.cohort_size, 0), 1) AS pct_m1,
    ROUND(r.retained_m3  * 100.0 / NULLIF(cs.cohort_size, 0), 1) AS pct_m3,
    ROUND(r.retained_m6  * 100.0 / NULLIF(cs.cohort_size, 0), 1) AS pct_m6,
    ROUND(r.retained_m12 * 100.0 / NULLIF(cs.cohort_size, 0), 1) AS pct_m12
FROM retention r
JOIN cohort_sizes cs ON cs.cohort_month = r.cohort_month
ORDER BY r.cohort_month;