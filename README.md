# SaaS Metrics DB

A PostgreSQL project that models the full subscription lifecycle of a SaaS business and calculates the metrics every real software company tracks: MRR, ARR, churn, LTV, ARPU, NRR, cohort retention, and MRR movement.

Served through a FastAPI backend and a live dashboard at `localhost:8000`.

Built with PostgreSQL 16 · FastAPI · asyncpg · Docker · Python

## What It Does

It models exactly how companies like Stripe, GitHub, and Notion track their subscription revenue from the moment a customer signs up, through every payment they make, to the day they cancel. The database answers the questions that actually matter:

How much recurring revenue does the business make every month? Which customers are most likely to leave? Of everyone who signed up in January, how many are still paying in June? How much is the average customer worth over their lifetime?

These are the questions data engineers and analytics engineers get asked to answer every day, and this project shows how to answer them properly.

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Database | PostgreSQL 16 | Relational schema, window functions, CTEs, date arithmetic |
| Containerization | Docker + Docker Compose | One command to run everything, identical on any machine |
| Seed Data | Python + Faker | 100 realistic customers across plans, billing cycles, and subscription states |
| API | FastAPI + asyncpg | HTTP endpoints for every metric with async database access |
| Frontend | Vanilla HTML/CSS/JS | Live dashboard served from the same container |

## Database Schema

Six tables, each modelling a distinct part of the business.

```
customers          plans
    │                │
    └──────────┬─────┘
               │
         subscriptions
               │
           invoices
               │
           payments

events  (standalone audit log, linked to customers + plans)
```

### customers

One row per customer. Tracks who is paying.

```sql
id           UUID PRIMARY KEY
name         VARCHAR NOT NULL
email        VARCHAR UNIQUE NOT NULL
country      CHAR(2)                  -- ISO code: ZA, US, GB
created_at   TIMESTAMPTZ DEFAULT NOW()
```

### plans

The pricing tiers available to customers.

```sql
id             UUID PRIMARY KEY
name           VARCHAR NOT NULL       -- Basic, Pro, Enterprise
price_monthly  NUMERIC(10,2)
price_annual   NUMERIC(10,2)          -- discounted vs monthly * 12
max_seats      INTEGER
```

### subscriptions

The relationship between a customer and a plan over time. A customer can hold multiple subscriptions across their lifetime if they cancel and resubscribe.

```sql
id             UUID PRIMARY KEY
customer_id    UUID REFERENCES customers(id)
plan_id        UUID REFERENCES plans(id)
status         VARCHAR                -- active | cancelled | paused | trialing
billing_cycle  VARCHAR                -- monthly | annual
started_at     TIMESTAMPTZ
cancelled_at   TIMESTAMPTZ            -- NULL if still active
trial_ends_at  TIMESTAMPTZ            -- NULL if no trial
```

### invoices

A bill generated for each billing period.

```sql
id               UUID PRIMARY KEY
subscription_id  UUID REFERENCES subscriptions(id)
customer_id      UUID REFERENCES customers(id)
amount           NUMERIC(10,2)
currency         CHAR(3)              -- ZAR | USD | GBP
status           VARCHAR              -- paid | unpaid | void
period_start     DATE
period_end       DATE
paid_at          TIMESTAMPTZ
```

### payments

The actual money movement. Each payment settles an invoice.

```sql
id              UUID PRIMARY KEY
invoice_id      UUID REFERENCES invoices(id)
customer_id     UUID REFERENCES customers(id)
amount          NUMERIC(10,2)
payment_method  VARCHAR               -- card | eft | paypal
status          VARCHAR               -- succeeded | failed | refunded
processed_at    TIMESTAMPTZ
```

### events

Immutable audit log. Every important customer action is recorded here.

```sql
id           UUID PRIMARY KEY
customer_id  UUID REFERENCES customers(id)
event_type   VARCHAR                  -- signup | upgrade | downgrade | churn | reactivate
old_plan_id  UUID REFERENCES plans(id)
new_plan_id  UUID REFERENCES plans(id)
occurred_at  TIMESTAMPTZ
metadata     JSONB
```

## Metrics Tracked

| Metric | What It Measures |
|---|---|
| MRR | Total recurring revenue collected per month across all active subscriptions |
| ARR | MRR multiplied by 12, the annual revenue projection |
| Churn Rate | Percentage of customers who cancelled in a given month |
| LTV | Total revenue earned per customer from first payment to last |
| ARPU | Average revenue earned from each active subscriber per month |
| NRR | Whether existing customers are spending more over time (above 100% means yes) |
| Cohort Retention | What percentage of a signup cohort is still active at month 1, 3, 6, 12 |
| MRR Movement | Breakdown of why MRR changed: new, expansion, contraction, churned |

## API Endpoints

| Method | Endpoint | Returns |
|---|---|---|
| GET | `/metrics/mrr` | Current MRR, ARR, and active subscription count |
| GET | `/metrics/churn` | Monthly churn rate history |
| GET | `/metrics/ltv` | Lifetime revenue per customer |
| GET | `/metrics/arpu` | Average revenue per user, overall and by plan |
| GET | `/metrics/nrr` | Net revenue retention per cohort month |
| GET | `/metrics/mrr-movement` | Monthly breakdown of new, expansion, contraction, and churned MRR |

Interactive docs available at `http://localhost:8000/docs`.

## Project Structure

```
saas-metrics-db/
├── docker-compose.yml               # PostgreSQL + FastAPI services
├── Dockerfile                       # API container build
├── .env.example                     # Environment variable template
├── .gitignore
├── README.md
│
├── frontend/
│   └── index.html                   # Live metrics dashboard
│
├── sql/
│   ├── migrations/
│   │   └── 001_initial_schema.sql   # All table definitions
│   ├── queries/
│   │   ├── mrr.sql
│   │   ├── churn.sql
│   │   ├── ltv.sql
│   │   ├── arpu.sql
│   │   ├── cohorts.sql
│   │   ├── mrr_movement.sql
│   │   └── nrr.sql
│   └── views/
│       └── active_subscriptions.sql
│
├── seed/
│   └── generate_seed.py             # Faker-based data generator
│
└── api/
    ├── main.py                      # FastAPI app with CORS and static file serving
    ├── database.py                  # asyncpg connection pool
    └── routers/
        └── metrics.py               # All /metrics/* route handlers
```

## Getting Started

**Prerequisites:** Docker Desktop, Git

### 1. Clone the repo

```bash
git clone https://github.com/denzelchingodza/saas-metric-db.git
cd saas-metrics-db
```

### 2. Start everything

```bash
docker compose up --build
```

This builds the API container and starts both services. PostgreSQL initialises with the schema automatically on first run. The API is ready when you see `Application startup complete` in the logs.

### 3. Open the dashboard

Go to `http://localhost:8000` in your browser. The dashboard fetches all metrics from the API and renders them live.

### 4. Seed the database (first time only)

```bash
pip install faker psycopg2-binary
python seed/generate_seed.py
```

Generates 100 customers across Basic, Pro, and Enterprise plans with a mix of monthly and annual billing cycles, upgrades, cancellations, trials, and refunds. Refresh the dashboard after seeding to see real numbers.

### 5. Connect directly to Postgres

```bash
docker exec -it saas-metrics-db psql -U admin -d saas_metrics
```

Or point any SQL client (TablePlus, DBeaver, pgAdmin) at `localhost:5432` with username `admin` and password `password`.

## Build Phases

- [x] Phase 1 — Project setup: Docker, Postgres, empty database
- [x] Phase 2 — Schema: all 6 tables with constraints and indexes
- [x] Phase 3 — Seed data: 100 realistic records via Python Faker
- [x] Phase 4 — Core metric queries: MRR, ARR, churn, ARPU, LTV
- [x] Phase 5 — Advanced queries: cohort analysis, MRR movement, NRR
- [x] Phase 6 — FastAPI layer: HTTP endpoints for every metric + live dashboard
- [ ] Phase 7 — Polish: database views, performance indexes, final tuning

## Why I Built This

I wanted a portfolio project that goes beyond basic CRUD and shows real business logic the kind of SQL and data modelling that actually gets used in production. SaaS metrics are something every software company cares about. Building this covered normalised schema design, advanced SQL (window functions, CTEs, date arithmetic), Docker containerisation, and exposing database results through a clean async API with a frontend that consumes it.

---

## What broke and how I fixed it

**Annual billing producing wrong MRR**

The first version of the MRR query summed `price_monthly` for all active subscriptions. Customers on annual billing were contributing their monthly equivalent at the wrong rate because `price_annual` is discounted (not simply `price_monthly * 12`). Fixed by normalising billing cycle in every metric query:

```sql
CASE
    WHEN s.billing_cycle = 'annual' THEN p.price_annual / 12
    ELSE p.price_monthly
END AS monthly_value
```

This pattern is repeated in MRR, ARR, ARPU, NRR, and MRR movement — every query that touches revenue has to handle both cycles.

**Division by zero in churn rate**

The churn rate query divides churned subscriptions by new subscriptions per month. In months with no new subscriptions (early seed data, edge months), this produced a PostgreSQL division-by-zero error. Fixed with `NULLIF`:

```sql
ROUND(churned::NUMERIC / NULLIF(new_subs, 0) * 100, 2) AS churn_rate_pct
```

`NULLIF(new_subs, 0)` returns NULL when `new_subs` is zero, which makes the division return NULL instead of throwing.

**asyncpg connection pool not ready on first request**

The pool uses a lazy initialisation pattern — it's created on first use, not at startup. On the very first request after a cold start, `get_pool()` had to `await asyncpg.create_pool()` before returning. Under concurrent first requests this caused a race condition where multiple coroutines all entered the `if _pool is None` branch simultaneously and each tried to create a separate pool. Fixed by ensuring the pool is initialised in FastAPI's startup event before any requests are served, so `get_pool()` always returns an already-created pool.

**asyncpg returning Record objects instead of dicts**

`conn.fetchrow()` and `conn.fetch()` return asyncpg `Record` objects, not Python dicts. FastAPI's JSON serialiser doesn't know how to handle them and raises `TypeError: Object of type Record is not JSON serializable`. Fixed by converting at the return site:

```python
return [dict(row) for row in rows]   # for lists
return dict(row)                      # for single rows
```

**`NUMERIC` type not serialising cleanly**

PostgreSQL `NUMERIC` columns (used for currency precision) come back as Python `Decimal` objects via asyncpg. FastAPI's default JSON encoder doesn't handle `Decimal`. Fixed by casting to `float` at the return site for all monetary values: `"mrr": float(row["mrr"])`.

---

## Technical notes

- **asyncpg over psycopg2** — asyncpg is a pure-async PostgreSQL driver with no synchronous fallback. It's significantly faster than psycopg2 for async workloads because it uses PostgreSQL's binary protocol and avoids the GIL overhead of the C extension.
- **Connection pool** — `asyncpg.create_pool()` maintains a pool of persistent connections. Each route handler acquires a connection with `async with pool.acquire() as conn:` and releases it automatically on exit — no manual connection management needed.
- **CTEs for complex metrics** — NRR, MRR movement, and cohort retention are all structured as chains of CTEs rather than nested subqueries. CTEs are materialised once and reused, making the query plan easier to read and debug.
- **NULLIF as a zero guard** — used in every query that divides by a count. PostgreSQL raises an error on integer division by zero; `NULLIF(denominator, 0)` short-circuits cleanly to NULL which propagates through the arithmetic.
- **Docker Compose** — `docker-compose.yml` defines both the PostgreSQL service and the FastAPI service. PostgreSQL initialises with the schema SQL on first run via the `init.sql` mount. `docker compose up --build` is the only command needed to run the full stack locally.

---

Built by Denzel · 2026
