# AyosNow MVP Backend

This repository now contains the first implementation scaffold for the AyosNow MVP backend, based on the final documentation package in `AYOSNOW_Final_Implementation_Package`.

## What Is Implemented

- Django project shell.
- Domain apps:
  - `accounts`
  - `geo`
  - `customers`
  - `providers`
  - `services`
  - `bookings`
  - `finance`
  - `complaints`
  - `audit`
  - `api`
- Models for MVP core entities.
- Django admin registration for all domain models.
- REST API endpoints matching the MVP OpenAPI package.
- JWT login and refresh endpoints.
- Development OTP verification flow.
- Standard success/error envelope helper.
- Payment checkout through a gateway adapter with idempotency key.
- Signed payment webhooks with gateway event uniqueness.
- Signed upload intents with file type, size, ownership, and purpose checks.
- Customer booking history and status tracking.
- Provider wallet ledger entries.
- Payout request creation.
- Complaint creation and booking dispute transition.

## Setup

Create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create local environment:

```powershell
Copy-Item .env.example .env
```

Run migrations:

```powershell
python manage.py makemigrations
python manage.py migrate
```

Create admin user:

```powershell
python manage.py createsuperuser
```

Run development server:

```powershell
python manage.py runserver
```

Open:

- API root: `http://127.0.0.1:8000/api/v1/`
- Admin: `http://127.0.0.1:8000/admin/`
- Operations dispatch desk: `http://127.0.0.1:8000/ops/`
- Customer booking app: `http://127.0.0.1:8000/app/`
- Provider job desk: `http://127.0.0.1:8000/provider/`

Seed MVP data:

```powershell
python manage.py seed_mvp
```

Seed demo customer/provider data:

```powershell
python manage.py seed_demo
```

Demo credentials:

- Customer: `+639170000100` / `DemoPass123`
- Provider: `+639170000200` / `DemoPass123`
- Demo dispatcher: `demo-dispatcher` / `DemoPass123`

Development OTP code:

- OTPs are now random 6-digit codes.
- In local development (`DJANGO_DEBUG=true`), auth responses include `dev_otp` so the UI/tests can proceed without a paid SMS provider.
- The console SMS backend also prints OTPs to the server console.

JWT login:

```http
POST /api/v1/auth/login
{
  "identifier": "+639170000100",
  "password": "DemoPass123",
  "user_type": "customer"
}
```

## Implementation Notes

Authentication now supports JWT access and refresh tokens. Django admin still uses normal Django session login.

Payment checkout uses `AYOSNOW_PAYMENT_GATEWAY_BACKEND`. The development backend creates local checkout references and verifies `X-AyosNow-Signature` using `PAYMENT_WEBHOOK_SECRET`. Future PayMongo/Xendit adapters can implement the same interface without changing the API views.

Uploads use `/api/v1/uploads/request` and `/api/v1/uploads/confirm`. New provider documents, complaint evidence, and completion evidence should pass confirmed `upload_ids`; raw evidence/document URLs are rejected for new attachments. Local development returns signed placeholder upload URLs, while production can swap the storage backend behind the same metadata contract.

OTP codes are generated randomly, stored hashed, expire, enforce attempt limits, and have resend cooldown. The local SMS backend prints codes to the console. Replace `AYOSNOW_SMS_BACKEND` with a real adapter such as Twilio or Semaphore before production.

Local settings are loaded from `.env`. Keep production secrets out of source control and use a long `DJANGO_SECRET_KEY`.

The database starts with Django models. The reference SQL remains in `AYOSNOW_Final_Implementation_Package/02_database_migration_001_mvp_core.sql`.

## Production Readiness

Health checks:

- Liveness: `GET /healthz`
- Readiness/database check: `GET /readyz`

Before deploying with `DJANGO_DEBUG=false`, set production values in your host environment or deployment secret manager:

```powershell
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<50+ character random secret>
DJANGO_ALLOWED_HOSTS=api.example.com,admin.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://api.example.com,https://admin.example.com
DATABASE_URL=postgres://ayosnow:<password>@db:5432/ayosnow?sslmode=require
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=true
DJANGO_SECURE_HSTS_PRELOAD=true
DJANGO_SECURE_PROXY_SSL_HEADER=true
PAYMENT_WEBHOOK_SECRET=<32+ character webhook secret>
AYOSNOW_PAYMENT_GATEWAY_BACKEND=<real gateway adapter>
AYOSNOW_SMS_BACKEND=<real SMS adapter>
```

Validate production configuration:

```powershell
python manage.py check_deploy_env
```

Container build:

```powershell
docker compose build
docker compose up
```

The compose command expects `.env` to contain production-safe values. Keep the development defaults only for local work.

### Render Deployment

Recommended first host: Render with managed PostgreSQL. This repo includes `render.yaml` so you can deploy it as a Render Blueprint.

Before applying the Blueprint, create secret values for:

- `PAYMENT_WEBHOOK_SECRET`
- `PAYMONGO_SECRET_KEY`
- `PAYMONGO_WEBHOOK_SECRET`
- `SEMAPHORE_API_KEY`

Render will generate `DJANGO_SECRET_KEY`, inject `DATABASE_URL` from the managed PostgreSQL service, and use the configured PayMongo/Semaphore adapter paths. Add the actual provider API credentials before enabling live payments or live OTP delivery.

Payment and SMS adapters:

- PayMongo checkout uses `PAYMONGO_SECRET_KEY`, creates checkout sessions through `PAYMONGO_CHECKOUT_URL`, and redirects customers to `PAYMONGO_SUCCESS_URL` or `PAYMONGO_CANCEL_URL`.
- Payment webhooks are verified with `PAYMONGO_WEBHOOK_SECRET` when the PayMongo adapter is enabled.
- Semaphore OTP delivery uses `SEMAPHORE_API_KEY`, optional `SEMAPHORE_SENDER_NAME`, and `SEMAPHORE_OTP_TEMPLATE`.
- `python manage.py check_deploy_env` fails production deploys if any required live credential is missing.

After the first deploy finishes, open the Render shell and create the first production admin:

```powershell
python manage.py createsuperuser
```

If you use a custom domain, update these environment variables in Render:

```powershell
DJANGO_ALLOWED_HOSTS=your-domain.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain.com
```

### Railway Deployment

Railway is also supported. This repo includes `railway.json`, which tells Railway to build with the Dockerfile, run migrations before deploy, start Gunicorn on Railway's `$PORT`, and health-check `/readyz`.

Deploy from GitHub:

1. Push this repository to GitHub.
2. In Railway, create a new project and choose **Deploy from GitHub repo**.
3. Add a PostgreSQL service to the Railway project. Your screenshot shows this is already done as `ayosnow-db`.
4. Open the Django app service variables and paste values from `.env.railway.example`.
5. Replace the secret placeholders:
   - `DJANGO_SECRET_KEY`
   - `PAYMENT_WEBHOOK_SECRET`
   - `PAYMONGO_SECRET_KEY`
   - `PAYMONGO_WEBHOOK_SECRET`
   - `SEMAPHORE_API_KEY`
6. Generate a Railway public domain, then confirm these variables point to it:
   - `DJANGO_ALLOWED_HOSTS`
   - `DJANGO_CSRF_TRUSTED_ORIGINS`
   - `PAYMONGO_SUCCESS_URL`
   - `PAYMONGO_CANCEL_URL`
7. Deploy the service and open `/readyz`.

Railway's PostgreSQL service exposes `DATABASE_URL`, which this project reads directly. If your database service name is different, update `DATABASE_URL` to reference that service, for example `${{your-db-service.DATABASE_URL}}`.

Railway health checks may use the host `healthcheck.railway.app`; the settings include `RAILWAY_HEALTHCHECK_HOST=healthcheck.railway.app` so Django allows those probes.

## Documentation Package

Build documents are in:

- `AYOSNOW_Final_Implementation_Package/01_Final_MVP_PRD.md`
- `AYOSNOW_Final_Implementation_Package/02_database_migration_001_mvp_core.sql`
- `AYOSNOW_Final_Implementation_Package/03_OpenAPI_MVP_v1.yaml`
- `AYOSNOW_Final_Implementation_Package/04_Admin_Screen_Specs.md`
- `AYOSNOW_Final_Implementation_Package/05_QA_Acceptance_Test_Checklist.md`

## Next Engineering Tasks

1. Install dependencies.
2. Generate and review Django migrations.
3. Seed roles, permissions, locations, and service catalog.
4. Implement real OTP delivery.
5. Integrate selected payment gateway.
6. Expand automated API tests from the QA checklist.
7. Add booking history and richer status tracking for customer/provider frontends.
