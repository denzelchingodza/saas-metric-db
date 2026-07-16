from fastapi import APIRouter, HTTPException
from api.database import get_pool

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/mrr")
async def get_mrr():
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            WITH active_subs AS (
                SELECT
                    CASE
                        WHEN s.billing_cycle = 'annual' THEN p.price_annual / 12
                        ELSE p.price_monthly
                    END AS monthly_value
                FROM subscriptions s
                JOIN plans p ON p.id = s.plan_id
                WHERE s.status = 'active'
            )
            SELECT
                ROUND(SUM(monthly_value)::NUMERIC, 2)       AS mrr,
                ROUND(SUM(monthly_value)::NUMERIC * 12, 2)  AS arr,
                COUNT(*)                                     AS active_subscriptions
            FROM active_subs
        """)
    return {
        "mrr": float(row["mrr"]),
        "arr": float(row["arr"]),
        "active_subscriptions": row["active_subscriptions"]
    }


@router.get("/churn")
async def get_churn():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            WITH monthly_starts AS (
                SELECT DATE_TRUNC('month', started_at) AS month, COUNT(*) AS new_subs
                FROM subscriptions GROUP BY month
            ),
            monthly_churned AS (
                SELECT DATE_TRUNC('month', cancelled_at) AS month, COUNT(*) AS churned
                FROM subscriptions WHERE cancelled_at IS NOT NULL GROUP BY month
            )
            SELECT
                ms.month::date AS month,
                ms.new_subs,
                COALESCE(mc.churned, 0) AS churned,
                ROUND(COALESCE(mc.churned, 0)::NUMERIC / NULLIF(ms.new_subs, 0) * 100, 2) AS churn_rate_pct
            FROM monthly_starts ms
            LEFT JOIN monthly_churned mc ON mc.month = ms.month
            ORDER BY ms.month
        """)
    return [dict(row) for row in rows]


@router.get("/ltv")
async def get_ltv():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                c.name,
                c.country,
                p.name AS plan,
                s.status,
                COALESCE(SUM(pay.amount), 0) AS lifetime_revenue,
                COUNT(pay.id) AS total_payments,
                ROUND((DATE_PART('day', COALESCE(s.cancelled_at, NOW()) - s.started_at) / 30)::NUMERIC, 1) AS months_as_customer
            FROM customers c
            JOIN subscriptions s ON s.customer_id = c.id
            JOIN plans p ON p.id = s.plan_id
            LEFT JOIN payments pay ON pay.customer_id = c.id AND pay.status = 'succeeded'
            GROUP BY c.id, c.name, c.country, p.name, s.status, s.started_at, s.cancelled_at
            ORDER BY lifetime_revenue DESC
            LIMIT 20
        """)
    return [dict(row) for row in rows]


@router.get("/arpu")
async def get_arpu():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            WITH arpu_by_plan AS (
                SELECT
                    p.name AS plan,
                    COUNT(*) AS customers,
                    ROUND(SUM(
                        CASE WHEN s.billing_cycle = 'annual' THEN p.price_annual / 12
                        ELSE p.price_monthly END
                    )::NUMERIC / NULLIF(COUNT(*), 0), 2) AS arpu
                FROM subscriptions s
                JOIN plans p ON p.id = s.plan_id
                WHERE s.status = 'active'
                GROUP BY p.name
            ),
            overall AS (
                SELECT
                    'Overall' AS plan,
                    COUNT(*) AS customers,
                    ROUND(SUM(
                        CASE WHEN s.billing_cycle = 'annual' THEN p.price_annual / 12
                        ELSE p.price_monthly END
                    )::NUMERIC / NULLIF(COUNT(*), 0), 2) AS arpu
                FROM subscriptions s
                JOIN plans p ON p.id = s.plan_id
                WHERE s.status = 'active'
            )
            SELECT * FROM overall
            UNION ALL
            SELECT * FROM arpu_by_plan
            ORDER BY arpu DESC
        """)
    return [dict(row) for row in rows]


@router.get("/nrr")
async def get_nrr():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            WITH starting_mrr AS (
                SELECT
                    DATE_TRUNC('month', s.started_at) AS month,
                    SUM(CASE WHEN s.billing_cycle = 'annual' THEN p.price_annual / 12
                        ELSE p.price_monthly END) AS mrr
                FROM subscriptions s
                JOIN plans p ON p.id = s.plan_id
                GROUP BY month
            ),
            ending_mrr AS (
                SELECT
                    DATE_TRUNC('month', s.started_at) AS cohort_month,
                    SUM(CASE
                        WHEN s.status = 'active' AND s.billing_cycle = 'annual' THEN p.price_annual / 12
                        WHEN s.status = 'active' THEN p.price_monthly
                        ELSE 0 END) AS retained_mrr
                FROM subscriptions s
                JOIN plans p ON p.id = s.plan_id
                GROUP BY cohort_month
            )
            SELECT
                s.month::date AS month,
                ROUND(s.mrr::NUMERIC, 2) AS starting_mrr,
                ROUND(e.retained_mrr::NUMERIC, 2) AS retained_mrr,
                ROUND(e.retained_mrr::NUMERIC / NULLIF(s.mrr, 0) * 100, 1) AS nrr_pct
            FROM starting_mrr s
            JOIN ending_mrr e ON e.cohort_month = s.month
            ORDER BY s.month
        """)
    return [dict(row) for row in rows]


@router.get("/mrr-movement")
async def get_mrr_movement():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            WITH upgrades AS (
                SELECT
                    DATE_TRUNC('month', e.occurred_at) AS month,
                    SUM(CASE WHEN e.event_type = 'upgrade' THEN
                        (SELECT price_monthly FROM plans WHERE id = e.new_plan_id) -
                        (SELECT price_monthly FROM plans WHERE id = e.old_plan_id)
                    ELSE 0 END) AS expansion_mrr,
                    SUM(CASE WHEN e.event_type = 'downgrade' THEN
                        (SELECT price_monthly FROM plans WHERE id = e.old_plan_id) -
                        (SELECT price_monthly FROM plans WHERE id = e.new_plan_id)
                    ELSE 0 END) AS contraction_mrr
                FROM events e
                WHERE e.event_type IN ('upgrade', 'downgrade')
                GROUP BY month
            ),
            new_mrr AS (
                SELECT
                    DATE_TRUNC('month', started_at) AS month,
                    SUM(CASE WHEN billing_cycle = 'annual' THEN
                        (SELECT price_annual FROM plans WHERE id = plan_id) / 12
                        ELSE (SELECT price_monthly FROM plans WHERE id = plan_id)
                    END) AS new_mrr
                FROM subscriptions
                WHERE DATE_TRUNC('month', started_at) = (
                    SELECT MIN(DATE_TRUNC('month', started_at))
                    FROM subscriptions s2 WHERE s2.customer_id = subscriptions.customer_id
                )
                GROUP BY month
            ),
            churned_mrr AS (
                SELECT
                    DATE_TRUNC('month', cancelled_at) AS month,
                    SUM(CASE WHEN billing_cycle = 'annual' THEN
                        (SELECT price_annual FROM plans WHERE id = plan_id) / 12
                        ELSE (SELECT price_monthly FROM plans WHERE id = plan_id)
                    END) AS churned_mrr
                FROM subscriptions WHERE cancelled_at IS NOT NULL
                GROUP BY month
            )
            SELECT
                COALESCE(n.month, u.month, c.month)::date AS month,
                ROUND(COALESCE(n.new_mrr, 0)::NUMERIC, 2) AS new_mrr,
                ROUND(COALESCE(u.expansion_mrr, 0)::NUMERIC, 2) AS expansion_mrr,
                ROUND(COALESCE(u.contraction_mrr, 0)::NUMERIC, 2) AS contraction_mrr,
                ROUND(COALESCE(c.churned_mrr, 0)::NUMERIC, 2) AS churned_mrr,
                ROUND((COALESCE(n.new_mrr, 0) + COALESCE(u.expansion_mrr, 0) -
                    COALESCE(u.contraction_mrr, 0) - COALESCE(c.churned_mrr, 0))::NUMERIC, 2) AS net_new_mrr
            FROM new_mrr n
            FULL OUTER JOIN upgrades u ON u.month = n.month
            FULL OUTER JOIN churned_mrr c ON c.month = COALESCE(n.month, u.month)
            ORDER BY month
        """)
    return [dict(row) for row in rows]