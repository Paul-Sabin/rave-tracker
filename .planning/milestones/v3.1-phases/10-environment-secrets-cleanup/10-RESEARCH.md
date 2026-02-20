# Phase 10: Environment & Secrets Cleanup - Research

**Researched:** 2026-02-11
**Domain:** Python environment variable management, secrets externalization, 12-factor app configuration
**Confidence:** HIGH

## Summary

Environment & Secrets Cleanup involves externalizing all hardcoded secrets from config.yaml to environment variables following 12-factor app methodology. The current codebase already has python-dotenv infrastructure in place (loaded in main.py line 84) and partial environment variable override logic in config.py (lines 108-136). However, config.yaml still contains hardcoded secrets (bot token, SMTP password, secret_key) that must be externalized and rotated.

The primary challenge is ensuring zero-downtime migration: config.yaml must be updated to use placeholder values or omit secrets entirely, .env.example must document all required variables, and all exposed secrets must be rotated immediately after externalization. The codebase already follows best practices for CSRF protection using Python's `secrets` module (csrf.py line 62), which can be reused for generating new secret keys.

**Primary recommendation:** Remove all secret values from config.yaml, add comprehensive .env.example documentation, rotate all exposed credentials (Telegram bot token, SMTP password, SECRET_KEY), and validate that the application starts successfully using only environment variables.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-dotenv | >=1.0.0 | Load .env files into environment | Industry standard for 12-factor apps, already installed |
| PyYAML | >=6.0 | YAML configuration parsing | Already used for config.yaml, safe_load prevents code injection |
| secrets | stdlib | Generate cryptographically secure tokens | Python stdlib, OWASP recommended for token generation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| os.environ | stdlib | Access environment variables | Already used throughout config.py |
| typing.Optional | stdlib | Type hints for nullable config | Already used in config dataclasses |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-dotenv | envparse | envparse adds type coercion, but python-dotenv is simpler and already installed |
| .env files | Secrets managers (Vault, AWS Secrets Manager) | Production should use secrets manager, but .env is standard for local dev |

**Installation:**
```bash
# Already installed via requirements.txt
pip install python-dotenv>=1.0.0 pyyaml>=6.0
```

## Architecture Patterns

### Recommended Configuration Loading Flow

Current implementation (main.py lines 83-88):
```python
# 1. Load .env file
load_dotenv()

# 2. Load config.yaml
config = Config.load(args.config)

# 3. Environment variables override config.yaml values (config.py lines 108-136)
```

This is the correct 12-factor pattern: `.env` → `config.yaml` → `environment variables` (highest priority).

### Pattern 1: Environment Variable Override Pattern
**What:** Config.load() reads config.yaml first, then overrides specific fields with environment variables
**When to use:** All secrets and deployment-specific settings (DATABASE_URL, BASE_URL, SECRET_KEY)
**Example:**
```python
# Source: config.py lines 133-136
if os.environ.get("SECRET_KEY") or os.environ.get("APP_SECRET_KEY"):
    config.app.secret_key = os.environ.get("SECRET_KEY") or os.environ["APP_SECRET_KEY"]
if os.environ.get("BASE_URL") or os.environ.get("APP_BASE_URL"):
    config.app.base_url = os.environ.get("BASE_URL") or os.environ["APP_BASE_URL"]
```

### Pattern 2: Multi-Name Environment Variable Support
**What:** Support both shorthand (BREVO_SMTP_PASSWORD) and generic (EMAIL_SMTP_PASSWORD) variable names
**When to use:** When migrating from provider-specific to generic naming or vice versa
**Example:**
```python
# Source: config.py lines 124-125
if os.environ.get("BREVO_SMTP_PASSWORD") or os.environ.get("EMAIL_SMTP_PASSWORD"):
    config.email.password = os.environ.get("BREVO_SMTP_PASSWORD") or os.environ["EMAIL_SMTP_PASSWORD"]
```

### Pattern 3: Placeholder Values in config.yaml
**What:** Use descriptive placeholder strings instead of actual secrets
**When to use:** For all secret fields in committed config files
**Example:**
```yaml
# Source: README.md lines 123-132 (recommended pattern)
email:
  server: smtp-relay.brevo.com
  port: 587
  username: "${BREVO_SMTP_USERNAME}"  # Placeholder - overridden by .env
  password: "${BREVO_SMTP_PASSWORD}"  # Placeholder - overridden by .env

app:
  secret_key: "${SECRET_KEY}"  # Placeholder - overridden by .env
  base_url: "${BASE_URL}"      # Placeholder - overridden by .env
```

### Pattern 4: Secret Generation with Python stdlib
**What:** Use `secrets.token_urlsafe(32)` for generating cryptographically secure tokens
**When to use:** Generating SECRET_KEY, CSRF secrets, webhook secrets
**Example:**
```python
# Source: csrf.py line 62 (already in use for CSRF tokens)
csrf_token = secrets.token_urlsafe(32)
```

### Anti-Patterns to Avoid
- **Committing .env files:** Never commit .env to version control (already prevented by .gitignore line 5)
- **Storing secrets in config.yaml:** Current config.yaml has hardcoded bot_token, password, secret_key (MUST be removed)
- **Using random module for secrets:** Use `secrets` module instead (random is not cryptographically secure)
- **Missing validation:** Don't wait for runtime errors - validate required env vars on startup
- **Zero environment variables:** config.py needs to enforce required secrets via environment (not just override if present)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| .env file parsing | Custom parser | python-dotenv.load_dotenv() | Handles quotes, multiline, escaping, comments correctly |
| Secret token generation | random.SystemRandom() | secrets.token_urlsafe(32) | OWASP recommended, designed for security-critical operations |
| Environment variable validation | Manual checks in main() | Pydantic BaseSettings or similar | Type coercion, missing value detection, clear error messages |
| DATABASE_URL parsing | String splitting | SQLAlchemy.engine.url.make_url() | Handles all edge cases (URL encoding, SSL params, ports) |
| Secrets rotation | Manual process | Scripts + checklist | Human error, forgotten steps, incomplete rotation |

**Key insight:** Environment variable management seems simple but has many edge cases (quoting, multiline values, variable expansion, type coercion). Use battle-tested libraries that handle these correctly.

## Common Pitfalls

### Pitfall 1: Secrets Still Readable in config.yaml After "Externalization"
**What goes wrong:** Placeholder strings like `"${SECRET_KEY}"` remain in config.yaml, but actual secrets are still committed in git history
**Why it happens:** Forgetting that git history is immutable - removing secrets from current file doesn't remove from history
**How to avoid:** After externalization, rotate ALL exposed secrets immediately (new bot token, new SMTP password, new SECRET_KEY)
**Warning signs:** Secrets visible in `git log -p config.yaml`, GitHub security alerts

### Pitfall 2: Application Fails to Start Due to Missing Environment Variables
**What goes wrong:** App reads empty string from environment variable, fails at runtime (e.g., Telegram auth fails)
**Why it happens:** config.py uses `os.environ.get()` which returns None, then config.yaml placeholder is used, resulting in invalid value
**How to avoid:** Add startup validation that checks required secrets are non-empty before initializing services
**Warning signs:** Cryptic errors from third-party libraries (telegram, SMTP), "authentication failed" messages

### Pitfall 3: .env.example and .env Drift Over Time
**What goes wrong:** .env.example doesn't document newly added environment variables, new developers missing config
**Why it happens:** Adding new env var to code but forgetting to update .env.example
**How to avoid:** Make .env.example updates part of the same commit that adds new environment variable usage
**Warning signs:** Developers asking "what env vars do I need?", KeyError on startup for new developers

### Pitfall 4: Incomplete Secret Rotation
**What goes wrong:** Rotate bot token but forget SMTP password, or vice versa
**Why it happens:** Manual rotation without checklist
**How to avoid:** Create rotation checklist with ALL secrets, test application startup after each rotation
**Warning signs:** Some services work (email) but others fail (Telegram), partial functionality

### Pitfall 5: config.yaml Placeholders Not Actually Overridden
**What goes wrong:** config.yaml contains `"${SECRET_KEY}"` as literal string, not parsed by shell, application uses literal string as secret
**Why it happens:** Expecting YAML parser to do variable substitution (it doesn't - YAML reads literal string)
**How to avoid:** Rely on config.py environment variable override logic (lines 108-136), not YAML variable expansion
**Warning signs:** Tokens fail signature verification, secrets literally contain "${}" characters

### Pitfall 6: DATABASE_URL for PostgreSQL Not Set Before Migration
**What goes wrong:** Phase 10 externalizes secrets, but DATABASE_URL is only needed for PostgreSQL (later phase)
**Why it happens:** Trying to migrate database config before database migration phase
**How to avoid:** For SQLite-to-PostgreSQL migration, DATABASE_URL externalization happens in database migration phase, not this phase
**Warning signs:** Confusion about whether to add DATABASE_URL now or later

## Code Examples

Verified patterns from project codebase:

### Generating New SECRET_KEY
```python
# Source: config.example.yaml line 46 (documented pattern)
# Run in terminal to generate new secret:
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Loading Environment Variables at Startup
```python
# Source: main.py lines 83-88
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()

# Load configuration (env vars override config file values)
config = Config.load(args.config)
set_config(config)
```

### Environment Variable Override with Fallback
```python
# Source: config.py lines 122-125
# Supports both BREVO_SMTP_* and EMAIL_SMTP_* naming conventions
if os.environ.get("BREVO_SMTP_USERNAME") or os.environ.get("EMAIL_SMTP_USERNAME"):
    config.email.username = os.environ.get("BREVO_SMTP_USERNAME") or os.environ["EMAIL_SMTP_USERNAME"]
if os.environ.get("BREVO_SMTP_PASSWORD") or os.environ.get("EMAIL_SMTP_PASSWORD"):
    config.email.password = os.environ.get("BREVO_SMTP_PASSWORD") or os.environ["EMAIL_SMTP_PASSWORD"]
```

### Safe CSRF Token Generation (Reusable for SECRET_KEY)
```python
# Source: csrf.py line 62
import secrets

# Generate cryptographically secure token
csrf_token = secrets.token_urlsafe(32)
```

### Recommended .env File Format
```bash
# Source: README.md lines 79-85 (documented example)
# .env (gitignored - never commit this file)
SECRET_KEY=your-generated-secret-key
BREVO_SMTP_USERNAME=your-smtp-username
BREVO_SMTP_PASSWORD=your-smtp-password
BASE_URL=http://localhost:8080
TELEGRAM_BOT_TOKEN=your-bot-token
```

### Recommended config.yaml Pattern (Post-Cleanup)
```yaml
# Source: README.md lines 123-133 (recommended future state)
email:
  server: smtp-relay.brevo.com
  port: 587
  username: ""  # Set via BREVO_SMTP_USERNAME env var
  password: ""  # Set via BREVO_SMTP_PASSWORD env var
  from_address: "noreply@example.com"
  from_name: "RA Tracker"
  starttls: true
  ssl_tls: false

telegram:
  bot_token: ""  # Set via TELEGRAM_BOT_TOKEN env var
  chat_id: ""    # Legacy, now per-user in database
  webhook_secret: ""
  use_webhook: false
  webhook_url: ""

app:
  secret_key: ""  # Set via SECRET_KEY env var
  base_url: "http://localhost:8080"  # Override via BASE_URL env var for production
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| config files with secrets | Environment variables | 12-factor apps (2011) | Secrets separated from code, works across all platforms |
| random module for tokens | secrets module | Python 3.6 (2016) | Cryptographically secure token generation in stdlib |
| .env committed to git | .env in .gitignore | Always (security best practice) | Prevents accidental secret exposure |
| Manual .env parsing | python-dotenv library | 2013 | Handles edge cases, supports .env.local overrides |
| Single environment | .env.development, .env.production | Modern dev practice | Different configs per environment without file renaming |

**Deprecated/outdated:**
- **Placeholder syntax `${VAR_NAME}` in YAML**: Does NOT work - YAML reads literal string. Must use config.py override logic instead.
- **RA_TRACKER_CONFIG environment variable**: Already supported (main.py line 82) but not documented in .env.example
- **SQLite database.path in config.yaml**: Will be replaced by DATABASE_URL in later PostgreSQL migration phase (not this phase)

## Open Questions

1. **Should DATABASE_URL be added in this phase or PostgreSQL migration phase?**
   - What we know: Phase 10 is "Environment & Secrets Cleanup", Phase 11+ includes PostgreSQL migration
   - What's unclear: Whether to externalize database.path now (as non-secret) or wait for DATABASE_URL (PostgreSQL format)
   - Recommendation: Keep database.path in config.yaml for now (it's not a secret). Add DATABASE_URL in PostgreSQL migration phase when switching from SQLite to PostgreSQL.

2. **Should telegram.webhook_secret be generated now or when webhooks are enabled?**
   - What we know: webhook_secret is currently empty string, use_webhook is false
   - What's unclear: Whether this should be pre-generated or left empty until webhooks are configured
   - Recommendation: Leave empty for now (not currently used). Generate when enabling webhooks in production deployment.

3. **Should old secrets be revoked before or after new secrets are deployed?**
   - What we know: Zero-downtime rotation requires deploying new key before revoking old one
   - What's unclear: Timing sequence for this local development setup
   - Recommendation: For bot token, generate new token first, update .env, verify app works, then revoke old token via BotFather. For SECRET_KEY, no revocation needed (just generate new one). For SMTP password, generate new app password in Brevo, test, then delete old one.

4. **How to validate required environment variables on startup?**
   - What we know: Current code uses `os.environ.get()` which returns None silently
   - What's unclear: Whether to add validation in config.py or main.py, and what error message to show
   - Recommendation: Add validation in Config.load() that checks required secrets (bot_token, secret_key) are non-empty strings. Raise ValueError with helpful message pointing to .env.example.

## Sources

### Primary (HIGH confidence)
- **Project codebase analysis**:
  - `ra-tracker/config.yaml` - Current hardcoded secrets requiring externalization
  - `ra-tracker/ra_tracker/config.py` - Existing environment variable override logic (lines 108-136)
  - `ra-tracker/ra_tracker/main.py` - python-dotenv usage (line 84)
  - `ra-tracker/ra_tracker/web/csrf.py` - secrets.token_urlsafe() pattern (line 62)
  - `ra-tracker/README.md` - Documented configuration patterns
  - `ra-tracker/config.example.yaml` - Example configuration structure
  - `.env` - Current environment variable usage
  - `.gitignore` - .env already gitignored (line 5)

- **Python official documentation**:
  - [Python secrets module documentation](https://docs.python.org/3/library/secrets.html) - Official stdlib docs for cryptographically secure token generation

### Secondary (MEDIUM confidence)
- [12-factor app configuration methodology](https://12factor.net/config) - Industry standard for environment-based config
- [python-dotenv GitHub repository](https://github.com/theskumar/python-dotenv) - Official python-dotenv docs
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html) - Security best practices for secrets rotation
- [GitGuardian: API Key Rotation Best Practices](https://blog.gitguardian.com/api-key-rotation-best-practices/) - Secrets rotation workflow
- [Telegram Bot API Tutorial](https://core.telegram.org/bots/tutorial) - Official Telegram bot token generation via BotFather
- [GitGuardian: Remediating Telegram Bot Token leaks](https://www.gitguardian.com/remediation/telegram-bot-token) - Telegram token rotation via /revoke command
- [PostgreSQL Connection String Format](https://www.geeksforgeeks.org/postgresql/postgresql-connection-string/) - DATABASE_URL pattern for future PostgreSQL migration
- [How to Work with Environment Variables in Python (2026)](https://oneuptime.com/blog/post/2026-01-26-work-with-environment-variables-python/view) - Current best practices
- [Python Secrets Management Best Practices](https://blog.gitguardian.com/how-to-handle-secrets-in-python/) - GitGuardian security guide
- [Best Practices for .env Files in Version Control](https://www.getfishtank.com/insights/best-practices-for-committing-env-files-to-version-control) - .env.example pattern

### Tertiary (LOW confidence)
- Web search discussions on secrets.token_urlsafe length - Consistent 32-byte recommendation, but no official 2026 OWASP update found

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - python-dotenv and secrets module already installed and in use
- Architecture: HIGH - Config.load() pattern already implemented, just needs secret removal from YAML
- Pitfalls: HIGH - Based on codebase analysis and verified security best practices

**Research date:** 2026-02-11
**Valid until:** 2026-03-11 (30 days - configuration patterns are stable)

**Secrets requiring rotation:**
1. TELEGRAM_BOT_TOKEN (config.yaml line 22) - Revoke via @BotFather /revoke command
2. SMTP password (config.yaml line 9) - Generate new app password in Brevo dashboard
3. SECRET_KEY (config.yaml line 3) - Generate new via `secrets.token_urlsafe(32)`

**Files requiring modification:**
1. `.env` - Add all required secrets
2. `.env.example` - Document all required environment variables with example format
3. `ra-tracker/config.yaml` - Remove all hardcoded secrets, replace with empty strings or placeholders
4. `ra-tracker/ra_tracker/config.py` - Add validation for required environment variables (optional enhancement)
