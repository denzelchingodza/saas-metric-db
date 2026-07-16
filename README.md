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

I wanted a portfolio project that goes beyond basic CRUD and shows real business logic — the kind of SQL and data modelling that actually gets used in production. SaaS metrics are something every software company cares about. Building this covered normalised schema design, advanced SQL (window functions, CTEs, date arithmetic), Docker containerisation, and exposing database results through a clean async API with a frontend that consumes it.

Built by Denzel · 2026
