import random
import os
from datetime import datetime, timedelta, timezone
from faker import Faker
import psycopg2

fake = Faker()

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@localhost:5432/saas_metrics")

def get_connection():
    return psycopg2.connect(DB_URL)

PLANS = {
    'Basic':    {'monthly': 199.00, 'annual': 1990.00},
    'Pro':      {'monthly': 499.00, 'annual': 4990.00},
    'Business': {'monthly': 999.00, 'annual': 9990.00},
}

COUNTRIES = ['ZA', 'US', 'GB', 'NG', 'KE', 'CA', 'AU', 'DE']

# Churn rates by plan
CHURN_RATE = {
    'Basic':    0.35,
    'Pro':      0.25,
    'Business': 0.15,
}

# Reactivation chance for churned customers
REACTIVATION_RATE = 0.08

# Chance of a mid lifecycle plan change for active customers
PLAN_CHANGE_RATE = 0.18
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

    cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    subscriptions = []

    for customer_id, created_at in customers:
        plan_name = random.choice(list(PLANS.keys()))
        billing_cycle = random.choice(['monthly', 'annual'])

        # Earlier cohorts churn more simulates improving onboarding
        base_churn = CHURN_RATE[plan_name]
        if created_at < cutoff:
            churn_rate = min(base_churn + 0.15, 0.80)
        else:
            churn_rate = base_churn

        is_cancelled = random.random() < churn_rate
        cancelled_at = None
        status = 'active'

        if is_cancelled:
            cancelled_at = created_at + timedelta(
                days=random.randint(30, 400)
            )
            # Don't cancel in the future
            if cancelled_at > datetime.now(timezone.utc):
                cancelled_at = None
                status = 'active'
            else:
                status = 'cancelled'

        cursor.execute("""
            INSERT INTO subscriptions
                (customer_id, plan_id, status, billing_cycle, started_at, cancelled_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, customer_id, plan_id, billing_cycle, started_at, cancelled_at
        """, (
            customer_id,
            plan_ids[plan_name],
            status,
            billing_cycle,
            created_at,
            cancelled_at
        ))
        subscriptions.append(cursor.fetchone())

    return subscriptions, plan_ids
def seed_invoices(cursor, subscriptions, plan_ids):
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

            # 92% of invoices succeed on first attempt
            first_attempt = random.random() < 0.92
            if first_attempt:
                status = 'paid'
                paid_at = current + timedelta(days=random.randint(1, 5))
                involuntary_churn = False
            else:
                # Retry — 60% of retries succeed
                retry_success = random.random() < 0.60
                if retry_success:
                    status = 'paid'
                    paid_at = current + timedelta(days=random.randint(6, 12))
                    involuntary_churn = False
                else:
                    # Retry exhausted — involuntary churn
                    status = 'unpaid'
                    paid_at = None
                    involuntary_churn = True

            invoices.append((
                sub_id,
                customer_id,
                amount,
                'ZAR',
                status,
                current.date(),
                period_end.date(),
                paid_at,
                involuntary_churn
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
        """, inv[:8])
        row = cursor.fetchone()
        results.append((*row, inv[8]))  # append involuntary_churn flag

    return results
def seed_payments(cursor, invoices):
    for invoice_id, customer_id, amount, paid_at, involuntary_churn in invoices:
        if paid_at is None:
            continue

        cursor.execute("""
            INSERT INTO payments
                (invoice_id, customer_id, amount, payment_method, status, processed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            invoice_id,
            customer_id,
            amount,
            random.choice(['card', 'eft', 'paypal']),
            'succeeded',
            paid_at
        ))
def seed_events(cursor, subscriptions, invoices, plan_ids):
    now = datetime.now(timezone.utc)

    # Track which customers had involuntary churn
    involuntary_churned = set()
    for invoice_id, customer_id, amount, paid_at, involuntary_churn in invoices:
        if involuntary_churn:
            involuntary_churned.add(customer_id)

    for sub_id, customer_id, plan_id, billing_cycle, started_at, cancelled_at in subscriptions:
        # Signup event
        cursor.execute("""
            INSERT INTO events
                (customer_id, event_type, new_plan_id, occurred_at)
            VALUES (%s, %s, %s, %s)
        """, (customer_id, 'signup', plan_id, started_at))

        # Churn event
        if cancelled_at:
            event_type = 'churn'
            if customer_id in involuntary_churned:
                event_type = 'churn'
                cursor.execute("""
                    INSERT INTO events
                        (customer_id, event_type, old_plan_id, occurred_at,
                         metadata)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    customer_id, event_type, plan_id, cancelled_at,
                    '{"reason": "involuntary", "cause": "payment_failure"}'
                ))
            else:
                cursor.execute("""
                    INSERT INTO events
                        (customer_id, event_type, old_plan_id, occurred_at,
                         metadata)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    customer_id, event_type, plan_id, cancelled_at,
                    '{"reason": "voluntary"}'
                ))

            # Reactivation — 8% chance
            if random.random() < REACTIVATION_RATE:
                reactivation_date = cancelled_at + timedelta(
                    days=random.randint(60, 180)
                )
                if reactivation_date < now:
                    new_plan = random.choice(list(PLANS.keys()))
                    cursor.execute("""
                        INSERT INTO subscriptions
                            (customer_id, plan_id, status, billing_cycle, started_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        customer_id,
                        plan_ids[new_plan],
                        'active',
                        random.choice(['monthly', 'annual']),
                        reactivation_date
                    ))
                    cursor.execute("""
                        INSERT INTO events
                            (customer_id, event_type, new_plan_id, occurred_at,
                             metadata)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        customer_id, 'reactivate', plan_ids[new_plan],
                        reactivation_date,
                        '{"source": "reactivation"}'
                    ))
def seed_plan_changes(cursor, subscriptions, plan_ids):
    plan_order = ['Basic', 'Pro', 'Business']
    plan_names = {v: k for k, v in plan_ids.items()}

    for sub_id, customer_id, plan_id, billing_cycle, started_at, cancelled_at in subscriptions:
        if cancelled_at:
            continue
        if random.random() > PLAN_CHANGE_RATE:
            continue

        current_plan = plan_names.get(plan_id)
        if not current_plan:
            continue

        current_idx = plan_order.index(current_plan)

        # Decide upgrade or downgrade
        if current_idx == 0:
            direction = 'upgrade'
        elif current_idx == 2:
            direction = 'downgrade'
        else:
            direction = random.choice(['upgrade', 'downgrade'])

        new_idx = current_idx + 1 if direction == 'upgrade' else current_idx - 1
        new_plan = plan_order[new_idx]
        new_plan_id = plan_ids[new_plan]

        # Change happens partway through subscription
        days_active = (datetime.now(timezone.utc) - started_at).days
        if days_active < 60:
            continue

        change_date = started_at + timedelta(days=random.randint(30, days_active - 30))

        # Proration — charge difference for remaining days in current month
        days_remaining = 30 - (change_date.day % 30)
        old_daily = PLANS[current_plan]['monthly'] / 30
        new_daily = PLANS[new_plan]['monthly'] / 30
        proration_amount = round((new_daily - old_daily) * days_remaining, 2)

        if proration_amount != 0:
            cursor.execute("""
                INSERT INTO invoices
                    (subscription_id, customer_id, amount, currency,
                     status, period_start, period_end, paid_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                sub_id,
                customer_id,
                abs(proration_amount),
                'ZAR',
                'paid',
                change_date.date(),
                (change_date + timedelta(days=days_remaining)).date(),
                change_date + timedelta(days=2)
            ))

        # Update subscription to new plan
        cursor.execute("""
            UPDATE subscriptions SET plan_id = %s WHERE id = %s
        """, (new_plan_id, sub_id))

        # Log the event
        event_type = 'upgrade' if direction == 'upgrade' else 'downgrade'
        cursor.execute("""
            INSERT INTO events
                (customer_id, event_type, old_plan_id, new_plan_id, occurred_at,
                 metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            customer_id, event_type, plan_id, new_plan_id, change_date,
            f'{{"from": "{current_plan}", "to": "{new_plan}", "proration": {proration_amount}}}'
        ))
def main():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        print("Seeding customers...")
        customers = seed_customers(cursor)
        conn.commit()

        print("Seeding subscriptions...")
        subscriptions, plan_ids = seed_subscriptions(cursor, customers)
        conn.commit()

        print("Seeding invoices...")
        invoices = seed_invoices(cursor, subscriptions, plan_ids)
        conn.commit()

        print("Seeding payments...")
        seed_payments(cursor, invoices)
        conn.commit()

        print("Seeding events and reactivations...")
        seed_events(cursor, subscriptions, invoices, plan_ids)
        conn.commit()

        print("Seeding plan changes...")
        seed_plan_changes(cursor, subscriptions, plan_ids)
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