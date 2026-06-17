# ARP — Backend

**Accounts for Rubber Plantation** — FastAPI backend powering the ARP accounting system.

## Stack

- **Python 3.11+** · FastAPI · SQLAlchemy ORM
- **SQLite** (dev) — drop-in for PostgreSQL in production
- **JWT** authentication (python-jose)
- **Bcrypt** password hashing (passlib)

## Role Hierarchy

```
PlatformAdmin > SuperAdmin > Admin > Owner > Buyer
```

Each role inherits access from all roles below it.

## Revenue Formula

```
gross = rubber_weight × price_per_kg
tapper_share    = gross × 50%
owner_pool      = gross × 50%
backteam_amount = owner_pool × backteam_percentage%
owner_net       = owner_pool − backteam_amount
                → split among owners by share_percentage
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI: http://localhost:8000/docs

## Seed First Admin

```bash
curl -X POST http://localhost:8000/api/seed-platform
# email: admin@arp.local  password: admin1234
```

> Change the password immediately after seeding.

## API Endpoints

| Group | Prefix | Min Role |
|---|---|---|
| Auth | `/auth` | Public |
| Platform | `/platform` | PlatformAdmin |
| Organizations | `/organizations` | PlatformAdmin |
| Users | `/users` | Admin |
| Plantations & Plots & Tappers | `/plantations`, `/plots`, `/tappers` | Buyer (read) / Admin (write) |
| Transactions | `/transactions` | Buyer |
| Debts | `/debts` | Admin |
| Reports | `/reports` | Owner / Admin |
| Export | `/export` | Admin |

## Multi-tenancy

Every model carries `organization_id`. All queries are scoped to the current user's organization — no cross-tenant data leakage.
