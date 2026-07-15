# SaaS Metrics & Subscription Analytics Database

A professional PostgreSQL project that models the full subscription lifecycle of a SaaS business and calculates the key metrics every real software company tracks MRR, ARR, churn, LTV, ARPU, cohort retention, and NRR.

Built with PostgreSQL · Docker · Python · FastAPI · GitHub Actions

---

## What This Project Does

It models exactly how companies like Stripe, GitHub, and Notion and other companies that basically tracks users subscriptions track their (the company) revenue and customers from the moment someone signs up, through every payment they make, to the day they cancel. Then it answers the questions that actually matter to a business like:

- How much recurring revenue do we make every month?
- Which customers are most likely to leave?
- Of everyone who signed up in January, how many are still paying in June?
- How much is the average customer worth over their lifetime?

These are the questions that data engineers, analytics engineers, and backend developers get asked to answer every day.

---

## Tech Stack Used

| Layer | Technology | Why |
|---|---|---|
| Database | PostgreSQL 16 | Industry standard relational DB. Window functions, CTEs, advanced date math. |
| Containerization | Docker + Docker Compose | Runs identically on any machine. One command to start everything. |
| Seed Data | Python + Faker | Generates 100+ realistic customers, subscriptions, payments. |
| API | FastAPI + asyncpg | Exposes metrics over HTTP. Auto generates Swagger docs. |
| Version Control | Git (dev + main) | Clean commit history. Feature branches merged to main. |

---

## Database Schema

Six tables. Each one models a distinct part of the business.

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

events (standalone audit log links to customers + plans)
```

### customers
Who is paying. One row per customer (company or individual).

```sql
id           UUID PRIMARY KEY
name         VARCHAR NOT NULL
email        VARCHAR UNIQUE NOT NULL
country      CHAR(2)                  -- ISO code: ZA, US, GB
created_at   TIMESTAMPTZ DEFAULT NOW()
```

### plans
The pricing tiers. Basic, Pro, Business.

```sql
id             UUID PRIMARY KEY
name           VARCHAR NOT NULL
price_monthly  NUMERIC(10,2)
price_annual   NUMERIC(10,2)          -- usually discounted vs monthly * 12
max_seats      INTEGER
```

### subscriptions
The relationship between a customer and a plan over time. A customer can have multiple subscriptions across their lifetime (cancel + resubscribe).

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
Immutable audit log. Every important action logged here.

```sql
id           UUID PRIMARY KEY
customer_id  UUID REFERENCES customers(id)
event_type   VARCHAR                  -- signup | upgrade | downgrade | churn | reactivate
old_plan_id  UUID REFERENCES plans(id)
new_plan_id  UUID REFERENCES plans(id)
occurred_at  TIMESTAMPTZ
metadata     JSONB                    -- flexible extra data
```

---

## Metrics Tracked

| Metric | Formula | What It Tells You |
|---|---|---|
| **MRR** | Sum of all active monthly subscription values | Total recurring revenue per month |
| **ARR** | MRR × 12 | Annual revenue projection |
| **Churn Rate** | Customers lost ÷ Customers at period start | What % of customers left |
| **LTV** | ARPU ÷ Monthly Churn Rate | How much one customer is worth over their lifetime |
| **ARPU** | MRR ÷ Active Customers | Average revenue per user per month |
| **NRR** | (MRR end − churned + expansion) ÷ MRR start | Are existing customers spending more over time? |
| **Cohort Retention** | % of month-X signups still active at month X+N | Which customer groups stick around |
| **MRR Movement** | New + Expansion − Contraction − Churned | Why MRR changed this month |

---

## Project Structure

```
saas-metrics-db/
├── docker-compose.yml          # Postgres + FastAPI services
├── Dockerfile                  # FastAPI container
├── .env.example                # Environment variable template
├── .gitignore
├── README.md
│
├── sql/
│   ├── migrations/
│   │   └── 001_initial_schema.sql   # All table definitions
│   ├── queries/
│   │   ├── mrr.sql                  # MRR + ARR calculations
│   │   ├── churn.sql                # Monthly churn rate
│   │   ├── ltv.sql                  # Customer lifetime value
│   │   ├── arpu.sql                 # Average revenue per user
│   │   ├── cohorts.sql              # Cohort retention analysis
│   │   ├── mrr_movement.sql         # New / expansion / churn breakdown
│   │   └── nrr.sql                  # Net revenue retention
│   └── views/
│       └── active_subscriptions.sql # Reusable view
│
├── seed/
│   └── generate_seed.py            # Faker-based seed data generator
│
└── api/
    ├── main.py                     # FastAPI app
    ├── database.py                 # asyncpg connection pool
    └── routers/
        └── metrics.py              # /metrics/* endpoints
```

---

## Getting Started

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Git](https://git-scm.com/)
- Python 3.11+ (for seed script)

### 1. Clone the repo

```bash
git clone https://github.com/denzelchingodza/saas-metrics-db.git
cd saas-metrics-db
git checkout dev
```

### 2. Start the database

```bash
docker compose up -d
```

This starts a PostgreSQL 16 container with the schema already applied and listening on port 5432.

### 3. Seed with realistic data

```bash
pip install faker psycopg2-binary
python seed/generate_seed.py
```

Generates ~100 customers across multiple plans, billing cycles, and subscription states — including upgrades, cancellations, and trials.

### 4. Connect to the database

```bash
docker exec -it saas-metrics-db-db-1 psql -U admin -d saas_metrics
```

Or connect with any SQL client (TablePlus, DBeaver, pgAdmin) to `localhost:5432`.

### 5. Run a metric query

```bash
# Inside psql
\i sql/queries/mrr.sql
```

### 6. Start the API (optional)

```bash
docker compose up
```

Then open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive Swagger UI.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/metrics/mrr` | Current MRR and ARR |
| GET | `/metrics/churn` | Monthly churn rate history |
| GET | `/metrics/ltv` | LTV per customer |
| GET | `/metrics/arpu` | Average revenue per user |
| GET | `/metrics/cohorts` | Cohort retention table |
| GET | `/metrics/mrr-movement` | MRR movement breakdown |
| GET | `/customers` | All customers with current plan |

---

## Git Workflow

```
main   ──●────────────────────────────●──── (stable, always works)
          \                          /
dev        ●──●──●──●──●──●──●──●──●  (all active development)
```

All work happens on `dev`. When a phase is complete and tested, it is merged into `main`.

**Commit message convention:**
```
feat: add customers table schema
feat: add MRR calculation query
fix: handle division by zero in churn rate query
feat: seed 100 realistic customer records
feat: add /metrics/mrr FastAPI endpoint
```

---

## Build Phases

- [x] **Phase 1** — Project setup: Docker, Postgres, empty database
- [x] **Phase 2** — Schema: all 6 tables with constraints and indexes
- [x] **Phase 3** — Seed data: 100+ realistic records via Python Faker
- [x] **Phase 4** — Core metric queries: MRR, ARR, churn, ARPU, LTV
- [ ] **Phase 5** — Advanced queries: cohort analysis, MRR movement, NRR
- [ ] **Phase 6** — FastAPI layer: HTTP endpoints for every metric
- [ ] **Phase 7** — Polish: views, indexes, performance tuning, final README

---

## Why I Built This

I wanted a portfolio project that goes beyond a basic CRUD database and shows real business logic the kind of SQL and data modelling that actually gets used in production. SaaS metrics are something every software company cares about. Building this taught me normalized schema design, advanced SQL (window functions, CTEs, date arithmetic), Docker containerization, and how to expose database results through a clean API.

---
