--MRR & ARR-------------------------------
--MRR = is basically about all the active subscription monthly values
--Annual subscribers are divided by 12 to get their monthly contribution
WITH active_subs AS (
    SELECT
        s.id,
        s.billing_cycle,
        p.price_monthly,
        p.price_annual
    FROM subscriptions s 
    JOIN plans p ON p.id = s.plan_id
    WHERE s.status = 'active'
),
monthly_value AS (
    SELECT
        CASE
            WHEN billing_cycle = 'annual' THEN price_annual / 12
            ELSE price_monthly
        END AS mrr_contribution
    FROM active_subs

)
SELECT
    ROUND(SUM(mrr_contribution), 2)       AS mrr,
    ROUND(SUM(mrr_contribution) * 12, 2)  AS arr,
    COUNT(*)                              AS active_subscriptions
FROM monthly_value;