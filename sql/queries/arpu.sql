--AVERAGE REVENUE PER USER---------------------------------------------
-- ARPU = MRR divided by number of active customers
-- Tells you how much the average customer pays per month

WITH mrr_calc AS (
    SELECT
        SUM(
            CASE
                WHEN s.billing_cycle = 'annual' THEN p.price_annual / 12
                ELSE p.price_monthly
            END
        ) AS mrr,
        COUNT(*) AS active_customers
    FROM subscriptions s
    JOIN plans p ON p.id = s.plan_id
    WHERE s.status = 'active'
),
arpu_by_plan AS (
    SELECT
        p.name                             AS plan,
        COUNT(*)                           AS customers,
        ROUND(
            SUM(
                CASE
                    WHEN s.billing_cycle = 'annual' THEN p.price_annual / 12
                    ELSE p.price_monthly
                END
            )::NUMERIC / NULLIF(COUNT(*), 0)
        , 2)                               AS arpu
    FROM subscriptions s
    JOIN plans p ON p.id = s.plan_id
    WHERE s.status = 'active'
    GROUP BY p.name
    ORDER BY arpu DESC
)
SELECT
    'Overall'          AS plan,
    m.active_customers AS customers,
    ROUND(m.mrr::NUMERIC / NULLIF(m.active_customers, 0), 2) AS arpu
FROM mrr_calc m

UNION ALL

SELECT plan, customers, arpu
FROM arpu_by_plan;