# Railway Deployment Guide

## Overview

This application is configured for deployment on Railway using Docker + Procfile for multi-service orchestration.

## Architecture

**Services:**
- **Web Service:** FastAPI application with gunicorn + uvicorn workers
- **Scheduler Service:** APScheduler background process for event monitoring
- **PostgreSQL Database:** Managed PostgreSQL instance

## Deployment Steps

### 1. Create Railway Project

```bash
# Install Railway CLI (if not already installed)
npm i -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init
```

### 2. Add PostgreSQL Database

In the Railway dashboard:
1. Click "New" → "Database" → "Add PostgreSQL"
2. Railway will automatically create a `DATABASE_URL` environment variable
3. **CRITICAL:** Deploy a backup template (see Backup Configuration below)

### 3. Configure Environment Variables

In Railway dashboard, add these environment variables:

**Required Secrets:**
- `SECRET_KEY` - Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `BREVO_SMTP_USERNAME` - Your Brevo login email
- `BREVO_SMTP_PASSWORD` - Brevo **SMTP key** (Brevo dashboard > Settings > SMTP & API > SMTP tab). Only used for local development; Railway blocks SMTP (see Production Email Transport below)
- `BREVO_API_KEY` - Brevo **HTTP API key** (Brevo dashboard > Settings > SMTP & API > API Keys tab). Required in production. This is a *different credential* from `BREVO_SMTP_PASSWORD` and the two are not interchangeable
- `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather

**Application Config:**
- `BASE_URL` - Your Railway deployment URL (e.g., `https://your-app.railway.app`)
- `WEB_CONCURRENCY=2` - Number of gunicorn workers (Railway starter: use 2)
- `PORT=8080` - Railway auto-injects PORT, but we default to 8080

**Email Config (pre-configured):**
- `EMAIL_USE_API=true` - **Required in production.** Sends mail over Brevo's HTTPS API instead of SMTP. Accepted truthy values: `true`, `1`, `yes`. Any other value falls back to SMTP, which does not work on Railway
- `EMAIL_SMTP_SERVER=smtp-relay.brevo.com`
- `EMAIL_SMTP_PORT=587`
- `EMAIL_FROM_ADDRESS=ravetracker@whotrustswho.com`
- `EMAIL_FROM_NAME=Rave Tracker`
- `SENTRY_DSN` - Optional. When set, `logger.error()` calls (including failed email sends) are captured as Sentry events
- `LOGTAIL_SOURCE_TOKEN` - Optional. When set, the application log stream is shipped to Better Stack

**Auto-provided by Railway:**
- `DATABASE_URL` - Automatically injected when PostgreSQL is added

### 3a. Production Email Transport (IMPORTANT)

Railway blocks outbound SMTP (ports 25, 465, 587, 2525) and recommends HTTPS-based
transactional email APIs instead. Sending mail over `smtp-relay.brevo.com:587` from a
Railway service therefore fails - typically by hanging until the worker timeout rather
than raising a clean error, which is why the failures were invisible for a while.

Production must use Brevo's HTTP API:

1. In the Brevo dashboard, go to **Settings > SMTP & API > API Keys** and create a key.
   This is *not* the value in `BREVO_SMTP_PASSWORD` - the SMTP key is on the neighbouring
   **SMTP** tab and Brevo's API rejects it with `401 Unauthorized`.
2. In Railway, set `BREVO_API_KEY` to that key.
3. In Railway, set `EMAIL_USE_API=true`.
4. Redeploy the web service (and the scheduler service, which sends event notifications).

Both variables are required together. With `EMAIL_USE_API=true` and no `BREVO_API_KEY`,
the app deliberately reports email as not configured and sends nothing rather than
authenticating with the wrong credential - notification sends are skipped and the
settings page shows email as unconfigured.

Keep the `EMAIL_SMTP_*` / `BREVO_SMTP_*` variables set: the SMTP path remains available
for local development, where port 587 is not blocked.

**Never** paste a real key into this file, `.env.example`, or any other tracked file.

### 4. Deploy Multiple Services

Railway supports multiple services from the same repository using Procfile:

1. **Deploy Web Service:**
   - Create a new service in your Railway project
   - Connect to your GitHub repository
   - Set the start command: Use the `web` entry from Procfile
   - Railway will automatically detect and use: `gunicorn ra_tracker.web.app:app ...`

2. **Deploy Scheduler Service:**
   - Create another service in the same Railway project
   - Connect to the same GitHub repository
   - Set the start command: Use the `scheduler` entry from Procfile
   - Railway will run: `python -m ra_tracker.main --scheduler-only -c config.yaml`

3. **Share Environment Variables:**
   - Both services share the same environment variables
   - Both connect to the same PostgreSQL database via `DATABASE_URL`

### 5. Health Check Configuration

The application provides a health check endpoint at `/health`.

Railway will automatically monitor your service health. Configure in Railway dashboard:
- Health check path: `/health`
- Health check interval: 30 seconds
- Health check timeout: 10 seconds

## Backup Configuration

⚠️ **CRITICAL:** Railway does NOT provide native PostgreSQL backups.

**Required Action:**
Deploy a third-party backup solution using Railway's template marketplace:

1. In Railway dashboard: "New" → "Template"
2. Search for "PostgreSQL Backup" templates
3. Deploy a backup template (options: pgbackups, postgres-backup-s3, etc.)
4. Configure backup schedule (recommended: daily backups with 7-day retention)
5. Connect backup service to your PostgreSQL database

**Backup Template Options:**
- **pgbackups:** Simple S3-based backups (recommended for simplicity)
- **postgres-backup-s3:** More configurable, requires AWS S3 bucket
- **Custom solution:** Use Railway Cron + pg_dump script

**Without backups, you risk data loss.** This is Railway's primary limitation compared to Render/Fly.io.

## Build Configuration

The application uses Docker for builds via `railway.json`:

```json
{
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  }
}
```

**Dockerfile highlights:**
- Base image: `python:3.11-slim`
- Installs `libpq-dev` + `gcc` for psycopg2 source compilation
- Avoids `psycopg2-binary` to prevent libpq/libssl version conflicts
- Uses layer caching for pip dependencies

**Alternative:** Railway can also use Nixpacks/Railpack (auto-detect Python), but Dockerfile provides explicit control.

## Database Migration

After deploying for the first time:

1. Railway will auto-create PostgreSQL tables on first startup (if using SQLAlchemy migrations)
2. Or manually run migration: `railway run python migrate.py` (if migration script exists)
3. For SQLite → PostgreSQL migration, see `scripts/migrate_sqlite_to_postgres.py`

## Monitoring

Railway provides:
- **Logs:** Real-time logs in dashboard (stdout/stderr)
- **Metrics:** CPU, memory, network usage
- **Deployments:** Git commit tracking, rollback support

**Application logs:**
- Web service logs: API requests, errors
- Scheduler logs: Event scraping, notification delivery

## Scaling

**Horizontal scaling (not needed initially):**
- Web service: Increase replicas in Railway dashboard
- Scheduler: Keep at 1 replica (APScheduler doesn't support distributed mode)

**Vertical scaling:**
- Railway auto-scales resources based on usage
- For predictable pricing, consider fixed-size plans

## Cost Estimation

Railway uses usage-based pricing:
- **Compute:** ~$0.000231/GB-hour (memory) + ~$0.000463/vCPU-hour
- **PostgreSQL:** Included in compute costs + storage
- **Egress:** First 100GB free, then $0.10/GB

**Typical monthly cost for low-traffic app:**
- Web service (always-on): $5-10/mo
- Scheduler (always-on): $5-10/mo
- PostgreSQL: $5-10/mo
- **Total: $15-30/mo** (usage-based, scales with traffic)

Compare to Render ($21/mo flat) and Fly.io ($38+/mo for managed Postgres).

## Troubleshooting

### Emails are not being delivered

1. Confirm `EMAIL_USE_API=true` is set on the service (exact value; `True`/`yes`/`1` also
   work, anything else silently selects SMTP).
2. Confirm `BREVO_API_KEY` is set and is an **API key**, not the SMTP key. A wrong key
   shows up in the logs as `Brevo API error 401: ...`.
3. A missing key logs `Brevo API key not configured - set BREVO_API_KEY` and sends nothing.
4. Check `/admin/audit-log?event_type=auth.verification_send_failed` - a row there means
   the app tried and Brevo refused. No rows and no `auth.verification_sent` rows means the
   send was never attempted (usually a missing key).
5. Do not "fix" this by switching back to SMTP. Railway blocks the ports.

**Build fails:**
- Check `railway logs` for build errors
- Verify `Dockerfile` installs `libpq-dev` (required for psycopg2)

**Web service won't start:**
- Check `DATABASE_URL` is set and accessible
- Verify `SECRET_KEY` is configured
- Check logs for startup validation errors

**Scheduler not running:**
- Verify scheduler service is deployed separately
- Check that `config.yaml` exists in container
- Scheduler logs should show "Scheduler started"

**Database connection errors:**
- Railway PostgreSQL uses SSL by default (psycopg2 handles this)
- Verify `DATABASE_URL` format: `postgresql://user:pass@host:port/db`
- Check connection pool settings (max = WEB_CONCURRENCY + 2)

## Security Notes

- All secrets are environment variables (never in code)
- Railway provides automatic HTTPS/SSL via Let's Encrypt
- `DATABASE_URL` includes credentials - never log or expose
- Session cookies use `httponly`, `secure`, `samesite=lax`
- CSRF protection via Double Submit Cookie pattern

## Custom Domain

To use a custom domain:
1. Railway dashboard → Settings → Domains
2. Add your custom domain (e.g., `ravetracker.example.com`)
3. Configure DNS CNAME to point to Railway's provided URL
4. Railway auto-provisions SSL certificate via Let's Encrypt
5. Update `BASE_URL` environment variable to match custom domain

## Next Steps

After deployment:
1. ✅ Verify health check is passing: `https://your-app.railway.app/health`
2. ✅ Test login/registration flow
3. ✅ Configure backup template for PostgreSQL
4. ✅ Set up custom domain (optional)
5. ✅ Monitor logs for scraping errors or rate limiting issues
