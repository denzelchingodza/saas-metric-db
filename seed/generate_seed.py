import random
from datetime import datetime, timedelta, timezone
from faker import Faker
import psycopg2

fake = Faker()

DB_URL = "postgresql://admin:password@localhost:5432/saas_metrics"

def get_connection():
    return psycopg2.connect(DB_URL)
PLANS = {
    'Basic':    {'monthly': 199.00, 'annual': 1990.00},
    'Pro':      {'monthly': 499.00, 'annual': 4990.00},
    'Business': {'monthly': 999.00, 'annual': 9990.00},
}

COUNTRIES = ['ZA', 'US', 'GB', 'NG', 'KE', 'CA', 'AU', 'DE']
def seed_customers(cursor, count=100):
    customers = []
    for _ in range(count):
        cursor.execute("""
            INSERT INTO customers (name, email, country, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id, created_at
        """, (
            fake.company(),
            fake.unique.email(),
            random.choice(COUNTRIES),
            fake.date_time_between(
                start_date='-2y',
                end_date='now',
                tzinfo=timezone.utc
            )
        ))
        customers.append(cursor.fetchone())

    return customers

def seed_subscriptions(cursor, customers):
    plan_ids = {}
    cursor.execute("SELECT id, name FROM plans")
    for row in cursor.fetchall():
        plan_ids[row[1]] = row[0]

    subscriptions = []
    for customer_id, created_at in customers:
        plan_name = random.choice(list(PLANS.keys()))
        billing_cycle = random.choice(['monthly', 'annual'])
        is_cancelled = random.random() < 0.25
        cancelled_at = None

        if is_cancelled:
            cancelled_at = created_at + timedelta(
                days=random.randint(30, 400)
            )
        subscriptions.append((
            customer_id,
            plan_ids[plan_name],
            'cancelled' if is_cancelled else 'active',
            billing_cycle,
            created_at,
            cancelled_at
        ))
    results = []
    for sub in subscriptions:
        cursor.execute("""
            INSERT INTO subscriptions
                (customer_id, plan_id, status, billing_cycle, started_at, cancelled_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, customer_id, plan_id, billing_cycle, started_at, cancelled_at
        """, sub)
        results.append(cursor.fetchone())

    return results
def seed_invoices(cursor, subscriptions):
    invoices = []

    for sub_id, customer_id, plan_id, billing_cycle, started_at, cancelled_at in subscriptions:
        cursor.execute("SELECT name FROM plans WHERE id = %s", (plan_id,))
        plan_name = cursor.fetchone()[0]

        if billing_cycle == 'monthly':
            amount = PLANS[plan_name]['monthly']
            interval = 30
        else:
            amount = PLANS[plan_name]['annual']
            interval = 365

        end_date = cancelled_at if cancelled_at else datetime.now(timezone.utc)
        current = started_at

        while current < end_date:
            period_end = current + timedelta(days=interval)
            is_paid = random.random() < 0.95
            invoices.append((
                sub_id,
                customer_id,
                amount,
                'ZAR',
                'paid' if is_paid else 'unpaid',
                current.date(),
                period_end.date(),
                current + timedelta(days=random.randint(1, 5)) if is_paid else None
            ))
            current = period_end

    results = []
    for inv in invoices:
        cursor.execute("""
            INSERT INTO invoices
                (subscription_id, customer_id, amount, currency,
                 status, period_start, period_end, paid_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, customer_id, amount, paid_at
        """, inv)
        results.append(cursor.fetchone())

    return results
def seed_payments(cursor, invoices):
    payments = []

    for invoice_id, customer_id, amount, paid_at in invoices:
        if paid_at is None:
            continue

        payments.append((
            invoice_id,
            customer_id,
            amount,
            random.choice(['card', 'eft', 'paypal']),
            'succeeded',
            paid_at
        ))

    cursor.executemany("""
        INSERT INTO payments
            (invoice_id, customer_id, amount, payment_method, status, processed_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, payments)
def main():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        print("Seeding customers...")
        customers = seed_customers(cursor)
        conn.commit()

        print("Seeding subscriptions...")
        subscriptions = seed_subscriptions(cursor, customers)
        conn.commit()

        print("Seeding invoices...")
        invoices = seed_invoices(cursor, subscriptions)
        conn.commit()

        print("Seeding payments...")
        seed_payments(cursor, invoices)
        conn.commit()

        print("Done. Database seeded successfully.")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()