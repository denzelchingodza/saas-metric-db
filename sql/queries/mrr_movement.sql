
-- MRR MOVEMENT-----------------------------------
-- Breaks down how MRR changed each month into 5 components:
-- New MRR       — revenue from brand new customers
-- Expansion MRR — existing customers upgraded to a higher plan
-- Contraction MRR — existing customers downgraded to a lower plan
-- Churned MRR   — revenue lost from cancellations
-- Net New MRR   — the actual change in MRR that month

WITH sub_monthly AS (
    SELECT
        s.customer_id,
        s.plan_id,
        s.status,
        s.billing_cycle,
        s.started_at,
        s.cancelled_at,
        p.price_monthly,
        p.price_annual,
        CASE
            WHEN s.billing_cycle = 'annual' THEN p.price_annual / 12
            ELSE p.price_monthly
        END AS monthly_value,
        DATE_TRUNC('month', s.started_at) AS start_month,
        DATE_TRUNC('month', s.cancelled_at) AS cancel_month
    FROM subscriptions s
    JOIN plans p ON p.id = s.plan_id
),
upgrades AS (
    SELECT
        DATE_TRUNC('month', e.occurred_at) AS month,
        SUM(
            CASE WHEN e.event_type = 'upgrade' THEN
                (SELECT price_monthly FROM plans WHERE id = e.new_plan_id) -
                (SELECT price_monthly FROM plans WHERE id = e.old_plan_id)
            ELSE 0 END
        ) AS expansion_mrr,
        SUM(
            CASE WHEN e.event_type = 'downgrade' THEN
                (SELECT price_monthly FROM plans WHERE id = e.old_plan_id) -
                (SELECT price_monthly FROM plans WHERE id = e.new_plan_id)
            ELSE 0 END
        ) AS contraction_mrr
    FROM events e
    WHERE e.event_type IN ('upgrade', 'downgrade')
    GROUP BY month
),
new_mrr AS (
    SELECT
        start_month AS month,
        SUM(monthly_value) AS new_mrr
    FROM sub_monthly
    WHERE start_month = (
        SELECT MIN(start_month) FROM sub_monthly s2
        WHERE s2.customer_id = sub_monthly.customer_id
    )
    GROUP BY start_month
),
churned_mrr AS (
    SELECT
        cancel_month AS month,
        SUM(monthly_value) AS churned_mrr
    FROM sub_monthly
    WHERE cancelled_at IS NOT NULL
    GROUP BY cancel_month
)
SELECT
    COALESCE(n.month, u.month, c.month)     AS month,
    ROUND(COALESCE(n.new_mrr, 0)::NUMERIC, 2)         AS new_mrr,
    ROUND(COALESCE(u.expansion_mrr, 0)::NUMERIC, 2)   AS expansion_mrr,
    ROUND(COALESCE(u.contraction_mrr, 0)::NUMERIC, 2) AS contraction_mrr,
    ROUND(COALESCE(c.churned_mrr, 0)::NUMERIC, 2)     AS churned_mrr,
    ROUND((
        COALESCE(n.new_mrr, 0) +
        COALESCE(u.expansion_mrr, 0) -
        COALESCE(u.contraction_mrr, 0) -
        COALESCE(c.churned_mrr, 0)
    )::NUMERIC, 2)                                     AS net_new_mrr
FROM new_mrr n
FULL OUTER JOIN upgrades u ON u.month = n.month
FULL OUTER JOIN churned_mrr c ON c.month = COALESCE(n.month, u.month)
ORDER BY month;