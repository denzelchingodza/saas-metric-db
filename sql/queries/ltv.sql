--CUSTOMER LIFE TIME VALUE------------------------------------------
--LIV = total revenue a customer generated before they churned
--For active customers we calculate revenue up to today

SELECT
    c.id,
    c.name,
    c.country,
    p.name                                    AS plan,
    s.billing_cycle,
    s.status,
    s.started_at::date                        AS start_date,
    s.cancelled_at::date                      AS end_date,
    COALESCE(SUM(pay.amount), 0)              AS lifetime_revenue,
    COUNT(pay.id)                             AS total_payments,
    ROUND(
        (DATE_PART('day',
            COALESCE(s.cancelled_at, NOW()) - s.started_at
        ) / 30)::NUMERIC
    , 1)                                      AS months_as_customer
FROM customers c
JOIN subscriptions s   ON s.customer_id = c.id
JOIN plans p           ON p.id = s.plan_id
LEFT JOIN payments pay ON pay.customer_id = c.id
                      AND pay.status = 'succeeded'
GROUP BY c.id, c.name, c.country, p.name, s.billing_cycle,
         s.status, s.started_at, s.cancelled_at
ORDER BY lifetime_revenue DESC
LIMIT 20;