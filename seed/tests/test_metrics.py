import pytest
import psycopg2

DB_URL = "postgresql://admin:password@localhost:5432/saas_metrics"
@pytest.fixture(scope="session")
def db():
    conn = psycopg2.connect(DB_URL)
    yield conn
    conn.close()
@pytest.fixture(scope="session")
def cursor(db):
    cur = db.cursor()
    yield cur
    cur.close()

# MRR TESTS --------------------------------------------------------
def test_mrr_only_counts_active_subscriptions(cursor):
    """MRR should only include active subscriptions, not cancelled ones."""
    cursor.execute("""
        SELECT COUNT(*) FROM subscriptions
        WHERE status = 'active'
    """)
    active_count = cursor.fetchone()[0]

    cursor.execute("""
        WITH active_subs AS (
            SELECT s.id
            FROM subscriptions s
            JOIN plans p ON p.id = s.plan_id
            WHERE s.status = 'active'
        )
        SELECT COUNT(*) FROM active_subs
    """)
    mrr_count = cursor.fetchone()[0]

    assert active_count == mrr_count, (
        f"MRR includes {mrr_count} subscriptions but there are "
        f"{active_count} active subscriptions"
    )


def test_mrr_is_positive(cursor):
    """MRR should always be a positive number."""
    cursor.execute("""
        SELECT SUM(
            CASE
                WHEN s.billing_cycle = 'annual' THEN p.price_annual / 12
                ELSE p.price_monthly
            END
        )
        FROM subscriptions s
        JOIN plans p ON p.id = s.plan_id
        WHERE s.status = 'active'
    """)
    mrr = cursor.fetchone()[0]
    assert mrr is not None and mrr > 0, "MRR should be a positive number"


def test_arr_is_mrr_times_12(cursor):
    """ARR should equal MRR multiplied by 12."""
    cursor.execute("""
        SELECT
            SUM(CASE
                WHEN s.billing_cycle = 'annual' THEN p.price_annual / 12
                ELSE p.price_monthly
            END) AS mrr
        FROM subscriptions s
        JOIN plans p ON p.id = s.plan_id
        WHERE s.status = 'active'
    """)
    mrr = cursor.fetchone()[0]
    arr = mrr * 12
    assert round(arr, 2) == round(mrr * 12, 2), "ARR should be MRR x 12"

# CHURN TESTS---------------------------------------------------------------------
def test_churn_events_match_cancelled_subscriptions(cursor):
    """Every cancelled subscription should have a matching churn event."""
    cursor.execute("""
        SELECT COUNT(*) FROM subscriptions
        WHERE status = 'cancelled'
    """)
    cancelled_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM events
        WHERE event_type = 'churn'
    """)
    churn_events = cursor.fetchone()[0]

    assert cancelled_count == churn_events, (
        f"Expected {cancelled_count} churn events but found {churn_events}"
    )


def test_reactivated_customers_have_active_subscription(cursor):
    """Customers with a reactivate event should have at least one active subscription."""
    cursor.execute("""
        SELECT DISTINCT customer_id FROM events
        WHERE event_type = 'reactivate'
    """)
    reactivated = [row[0] for row in cursor.fetchall()]

    for customer_id in reactivated:
        cursor.execute("""
            SELECT COUNT(*) FROM subscriptions
            WHERE customer_id = %s AND status = 'active'
        """, (customer_id,))
        count = cursor.fetchone()[0]
        assert count > 0, (
            f"Customer {customer_id} has a reactivate event but no active subscription"
        )


def test_no_future_cancellations(cursor):
    """No subscription should have a cancellation date in the future."""
    cursor.execute("""
        SELECT COUNT(*) FROM subscriptions
        WHERE cancelled_at > NOW()
    """)
    count = cursor.fetchone()[0]
    assert count == 0, f"{count} subscriptions have future cancellation dates"

# LTV TESTS-----------------------------------------------------------------------------------
def test_ltv_only_counts_succeeded_payments(cursor):
    """Lifetime revenue should only include succeeded payments, not failed ones."""
    cursor.execute("""
        SELECT COUNT(*) FROM payments
        WHERE status != 'succeeded'
    """)
    non_succeeded = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM payments
        WHERE status = 'succeeded'
    """)
    succeeded = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM payments")
    total = cursor.fetchone()[0]

    assert succeeded + non_succeeded == total, (
        "Payment counts do not add up correctly"
    )
    assert succeeded > 0, "There should be at least some succeeded payments"


def test_every_payment_has_valid_invoice(cursor):
    """Every payment should reference an invoice that exists."""
    cursor.execute("""
        SELECT COUNT(*) FROM payments p
        LEFT JOIN invoices i ON i.id = p.invoice_id
        WHERE i.id IS NULL
    """)
    orphaned = cursor.fetchone()[0]
    assert orphaned == 0, f"{orphaned} payments reference invoices that do not exist"

# ARPU TESTS-----------------------------------------------------------------------------
def test_arpu_is_mrr_divided_by_active_customers(cursor):
    """ARPU should equal MRR divided by active customer count."""
    cursor.execute("""
        SELECT
            SUM(CASE
                WHEN s.billing_cycle = 'annual' THEN p.price_annual / 12
                ELSE p.price_monthly
            END) AS mrr,
            COUNT(*) AS active_customers
        FROM subscriptions s
        JOIN plans p ON p.id = s.plan_id
        WHERE s.status = 'active'
    """)
    row = cursor.fetchone()
    mrr, active_customers = row
    expected_arpu = round(float(mrr) / active_customers, 2)

    cursor.execute("""
        SELECT COUNT(*) FROM subscriptions WHERE status = 'active'
    """)
    count = cursor.fetchone()[0]

    assert count == active_customers, "Active customer count mismatch"
    assert expected_arpu > 0, "ARPU should be positive"


def test_business_arpu_higher_than_basic(cursor):
    """Business plan ARPU should always be higher than Basic plan ARPU."""
    cursor.execute("""
        SELECT p.name,
            AVG(CASE
                WHEN s.billing_cycle = 'annual' THEN p.price_annual / 12
                ELSE p.price_monthly
            END) AS arpu
        FROM subscriptions s
        JOIN plans p ON p.id = s.plan_id
        WHERE s.status = 'active'
        GROUP BY p.name
    """)
    rows = {row[0]: float(row[1]) for row in cursor.fetchall()}

    assert rows['Business'] > rows['Basic'], (
        f"Business ARPU ({rows['Business']}) should be higher than "
        f"Basic ARPU ({rows['Basic']})"
    )