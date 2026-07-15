--REVENUE BY COUNTRY--------------------------------------
-- Total payments received grouped by customer country
-- Shows which markets are generating the most revenue
SELECT
    c.country,
    COUNT(DISTINCT c.id)              AS customers,
    COUNT(pay.id)                     AS total_payments,
    ROUND(SUM(pay.amount)::NUMERIC, 2) AS total_revenue,
    ROUND(AVG(pay.amount)::NUMERIC, 2) AS avg_payment,
    ROUND(
        SUM(pay.amount)::NUMERIC
        / NULLIF(COUNT(DISTINCT c.id), 0)
    , 2)                              AS revenue_per_customer
FROM customers c
JOIN payments pay ON pay.customer_id = c.id
WHERE pay.status = 'succeeded'
GROUP BY c.country
ORDER BY total_revenue DESC;
