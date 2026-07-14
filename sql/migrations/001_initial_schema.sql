-- enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- CUSTOMERS----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    country CHAR(2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_customers_country ON customers(country);
CREATE INDEX idx_customers_created_at ON customers(created_at);

-- PLANS-----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plans(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    price_monthly NUMERIC(10, 2) NOT NULL,
    price_annual NUMERIC(10, 2) NOT NULL,
    max_seats INTEGER NOT NULL DEFAULT 1
);

--Seed the triple pricing tiers
INSERT INTO plans (name, price_monthly, price_annual, max_seats) VALUES
    ('Basic', 199.00, 1990.00, 3),
    ('Pro', 499.00, 4990.00, 10),
    ('Business', 999.00, 9990.00, 50)
ON CONFLICT (name) DO NOTHING;

--SUBSCRIPTIONS------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subscriptions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id    UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    plan_id        UUID NOT NULL REFERENCES plans(id),
    status         VARCHAR(20) NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'cancelled', 'paused', 'trialing')),
    billing_cycle  VARCHAR(10) NOT NULL DEFAULT 'monthly'
                   CHECK (billing_cycle IN ('monthly', 'annual')),
    started_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cancelled_at   TIMESTAMPTZ,
    trial_ends_at  TIMESTAMPTZ
);

CREATE INDEX idx_subscriptions_customer_id ON subscriptions(customer_id);
CREATE INDEX idx_subscriptions_status      ON subscriptions(status);
CREATE INDEX idx_subscriptions_started_at  ON subscriptions(started_at);

--INVOICES-------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoices(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    amount NUMERIC(10, 2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'ZAR',
    status VARCHAR(10) NOT NULL DEFAULT 'unpaid'
           CHECK (status IN ('paid', 'unpaid', 'void')),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW() 
);
CREATE INDEX idx_invoices_customer_id     ON invoices(customer_id);
CREATE INDEX idx_invoices_subscription_id ON invoices(subscription_id);
CREATE INDEX idx_invoices_status          ON invoices(status);
CREATE INDEX idx_invoices_period_start    ON invoices(period_start);

--PAYMENTS-----------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    amount NUMERIC(10, 2) NOT NULL,
    payment_method VARCHAR(20) DEFAULT 'card'
                   CHECK (payment_method IN ('card', 'eft', 'paypal')),
    status VARCHAR(15) NOT NULL DEFAULT 'succeeded'
           CHECK (status IN ('succeeded', 'failed', 'refunded')),
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()  

);
CREATE INDEX idx_payments_customer_id  ON payments(customer_id);
CREATE INDEX idx_payments_invoice_id   ON payments(invoice_id);
CREATE INDEX idx_payments_status       ON payments(status);
CREATE INDEX idx_payments_processed_at ON payments(processed_at);

--EVENTS---------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id),
    event_type VARCHAR(20) NOT NULL 
               CHECK (event_type IN ('signup', 'upgrade', 'downgrade', 'churn', 'reactivate', 'trial_start', 'trial_end')),
    old_plan_id UUID REFERENCES plans(id),
    new_plan_id UUID REFERENCES plans(id),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB 
);
CREATE INDEX idx_events_customer_id ON events(customer_id);
CREATE INDEX idx_events_event_type  ON events(event_type);
CREATE INDEX idx_events_occurred_at ON events(occurred_at);