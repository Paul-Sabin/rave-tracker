# Phase 4: User Notifications - Research

**Researched:** 2026-01-30
**Domain:** Multi-channel user notifications (Telegram linking, Email SMTP, signed tokens)
**Confidence:** HIGH

## Summary

This phase implements per-user notification preferences, allowing users to independently configure Telegram and Email notification channels. The key technical challenges are:

1. **Telegram bot linking flow** - Users link their Telegram account by sending a verification code to the shared bot, which captures their chat_id
2. **Signed unsubscribe tokens** - Email unsubscribe links must work without login, requiring cryptographically signed tokens
3. **Per-user notification dispatch** - The scheduler must send notifications to each user's configured channels

The existing codebase already uses python-telegram-bot (v22.5) for sending notifications via a single configured chat_id. This phase extends that to support per-user chat_ids captured through a bot webhook/polling system. Email is a new capability requiring SMTP configuration and the fastapi-mail library.

**Primary recommendation:** Use webhook-based Telegram bot integration with FastAPI, itsdangerous for signed unsubscribe tokens, and fastapi-mail for SMTP. Polling is acceptable for simpler deployment but webhooks are preferred for production.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-telegram-bot | 22.5 (installed) | Telegram bot API | Already in use, well-maintained, async support |
| fastapi-mail | 1.6.x | SMTP email sending | FastAPI-native, async, Jinja2 templates, bulk sending |
| itsdangerous | 2.0.1 (installed) | Signed tokens | Pallets project (Flask ecosystem), URL-safe, timed tokens |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pyjwt | 2.x | JWT tokens | Alternative to itsdangerous if JWT ecosystem preferred |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| itsdangerous | PyJWT | JWT more complex, itsdangerous simpler for single-purpose tokens |
| fastapi-mail | smtplib (stdlib) | smtplib requires manual async handling, fastapi-mail is batteries-included |
| Webhook | Long polling | Polling simpler (no HTTPS cert needed), but higher latency and resource usage |

**Installation:**
```bash
pip install fastapi-mail
# python-telegram-bot and itsdangerous already installed
```

## Architecture Patterns

### Existing Codebase Integration Points

The existing codebase has these key files to modify/extend:

```
ra_tracker/
├── config.py              # Add EmailConfig dataclass, extend TelegramConfig
├── database.py            # Add notification preference columns, link_codes table
├── services/
│   ├── notifier.py        # Modify: per-user dispatch (currently uses single chat_id)
│   ├── telegram_bot.py    # NEW: bot command handlers, webhook/polling
│   └── email_sender.py    # NEW: SMTP email service
├── scheduler/
│   └── jobs.py            # Modify: call per-user notification dispatch
├── web/
│   ├── routes.py          # Add: notification settings routes
│   ├── app.py             # Add: lifespan for bot, webhook endpoint
│   └── unsubscribe.py     # NEW: email unsubscribe handler
└── templates/
    ├── email/             # NEW: email notification templates
    │   └── notification.html
    ├── settings.html      # Modify: add notification preferences section
    └── unsubscribed.html  # NEW: confirmation page
```

**Key existing code to modify:**

1. `notifier.py` - Currently sends to `config.telegram.chat_id` (lines 110-111, 117-119)
2. `jobs.py` - `fetch_and_notify()` calls `notifier.send_event_summary()` (line 103)
3. `database.py` - Users table already has `telegram_chat_id` column (line 97)
4. `config.py` - TelegramConfig has `bot_token` and `chat_id` (lines 12-14)

### Pattern 1: Telegram Linking Flow (Deep Linking with Verification Code)
**What:** User generates a code in the web app, sends it to the bot, bot validates and captures chat_id
**When to use:** Linking external accounts to Telegram

```python
# 1. Generate linking code (web route)
import secrets
from datetime import datetime, timedelta

def generate_link_code(user_id: int) -> str:
    code = secrets.token_urlsafe(8)  # Short, URL-safe code
    expires_at = datetime.now() + timedelta(hours=1)
    db.create_telegram_link_code(user_id, code, expires_at)
    return code

# 2. Bot command handler
async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /link YOUR_CODE")
        return

    code = context.args[0]
    chat_id = update.effective_chat.id

    # Validate code and get user
    link_record = db.get_telegram_link_code(code)
    if not link_record:
        await update.message.reply_text("Code not found.")
        return
    if link_record.used_at:
        await update.message.reply_text("Code already used.")
        return
    if link_record.expires_at < datetime.now():
        await update.message.reply_text("Code expired. Generate a new one.")
        return

    # Link successful
    db.update_user_telegram(link_record.user_id, chat_id)
    db.mark_link_code_used(code)
    await update.message.reply_text(
        "Linked successfully! You'll receive event notifications here."
    )
```

### Pattern 2: FastAPI + python-telegram-bot Webhook Integration
**What:** Receive Telegram updates via HTTP POST endpoint
**When to use:** Production deployment with public HTTPS endpoint

```python
# Source: python-telegram-bot wiki + freeCodeCamp tutorial (verified 2026)
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler

# Build application without updater (webhook mode)
# IMPORTANT: Use .updater(None) for webhook mode in ptb v20+
ptb = (
    Application.builder()
    .updater(None)  # No polling
    .token(BOT_TOKEN)
    .build()
)

# Register handlers
ptb.add_handler(CommandHandler("link", link_command))
ptb.add_handler(CommandHandler("stop", stop_command))
ptb.add_handler(CommandHandler("start", start_command))

@asynccontextmanager
async def lifespan(_: FastAPI):
    webhook_url = f"{BASE_URL}/telegram/webhook"
    await ptb.bot.setWebhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET  # Security: verify requests
    )
    async with ptb:
        await ptb.start()
        yield
        await ptb.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    # Verify secret token header - CRITICAL for security
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return Response(status_code=403)

    data = await request.json()
    update = Update.de_json(data, ptb.bot)
    await ptb.process_update(update)
    return Response(status_code=200)
```

### Pattern 3: Polling Mode (Simpler Alternative)
**What:** Bot polls Telegram servers for updates
**When to use:** Development, or production without public HTTPS

```python
# Run in separate thread/process alongside FastAPI
from telegram.ext import Application, CommandHandler
import threading
import asyncio

def run_bot_polling():
    """Run bot polling in a new event loop (for thread safety)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("link", link_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("start", start_command))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

# Start in background thread (daemon=True for clean shutdown)
bot_thread = threading.Thread(target=run_bot_polling, daemon=True)
bot_thread.start()
```

### Pattern 4: Signed Unsubscribe Tokens with itsdangerous
**What:** Generate tamper-proof, time-limited tokens for email unsubscribe
**When to use:** One-click unsubscribe without login

```python
# Source: itsdangerous documentation (2.x API)
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

# Create serializer with secret key and salt for context separation
unsubscribe_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="email-unsubscribe")

def generate_unsubscribe_token(user_id: int) -> str:
    """Generate signed token containing user_id."""
    return unsubscribe_serializer.dumps({"user_id": user_id})

def verify_unsubscribe_token(token: str, max_age_days: int = 30) -> dict:
    """Verify and decode token. Raises on invalid/expired."""
    max_age_seconds = max_age_days * 24 * 60 * 60
    return unsubscribe_serializer.loads(token, max_age=max_age_seconds)

# Route handler
@router.get("/unsubscribe")
async def unsubscribe(request: Request, token: str):
    templates = get_templates(request)
    try:
        data = verify_unsubscribe_token(token)
        user_id = data["user_id"]
        db.set_user_email_enabled(user_id, False)
        return templates.TemplateResponse("unsubscribed.html", {
            "request": request,
            "message": "Email notifications disabled."
        })
    except SignatureExpired:
        return templates.TemplateResponse("unsubscribe_error.html", {
            "request": request,
            "error": "This link has expired."
        })
    except BadSignature:
        return templates.TemplateResponse("unsubscribe_error.html", {
            "request": request,
            "error": "Invalid unsubscribe link."
        })
```

### Pattern 5: fastapi-mail Configuration and Usage
**What:** Send HTML emails via SMTP with Jinja2 templates
**When to use:** Email notifications

```python
# Source: fastapi-mail documentation (1.6.x API)
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pathlib import Path

# Configuration from config.yaml
email_conf = ConnectionConfig(
    MAIL_USERNAME=config.email.username,
    MAIL_PASSWORD=config.email.password,
    MAIL_FROM=config.email.from_address,
    MAIL_PORT=config.email.port,  # 587 for STARTTLS, 465 for SSL
    MAIL_SERVER=config.email.server,
    MAIL_FROM_NAME="RA Tracker",
    MAIL_STARTTLS=config.email.starttls,
    MAIL_SSL_TLS=config.email.ssl_tls,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path(__file__).parent / "templates" / "email"
)

async def send_notification_email(
    user_email: str,
    events: list,
    unsubscribe_token: str
):
    message = MessageSchema(
        subject=f"RA Tracker: {len(events)} new event(s) found!",
        recipients=[user_email],
        template_body={
            "events": events,
            "unsubscribe_url": f"{BASE_URL}/unsubscribe?token={unsubscribe_token}"
        },
        subtype=MessageType.html
    )

    fm = FastMail(email_conf)
    await fm.send_message(message, template_name="notification.html")
```

### Pattern 6: Per-User Notification Dispatch
**What:** Scheduler sends to each user's enabled channels
**When to use:** Main notification job (replaces current single-chat logic)

```python
async def notify_users_for_events(new_events: List[Tuple[Event, List[Rule]]]):
    """Send notifications to each user based on their preferences.

    Replaces the current notifier.send_event_summary() which sends to
    a single config-defined chat_id.
    """

    # Group events by user (via their rules)
    user_events: Dict[int, List[Tuple[Event, List[Rule]]]] = {}
    for event, rules in new_events:
        for rule in rules:
            if rule.user_id not in user_events:
                user_events[rule.user_id] = []
            # Avoid duplicates per user
            if event.id not in [e.id for e, _ in user_events[rule.user_id]]:
                user_events[rule.user_id].append((event, rules))

    # Send to each user's enabled channels
    for user_id, events in user_events.items():
        user = db.get_user_by_id(user_id)
        if not user:
            continue

        # Check telegram
        if user.telegram_enabled and user.telegram_chat_id:
            try:
                await send_telegram_notification(user.telegram_chat_id, events)
            except Exception as e:
                logger.warning(f"Telegram notification failed for user {user_id}: {e}")

        # Check email
        if user.email_enabled:
            try:
                token = generate_unsubscribe_token(user_id)
                await send_notification_email(user.email, events, token)
            except Exception as e:
                logger.warning(f"Email notification failed for user {user_id}: {e}")
```

### Anti-Patterns to Avoid
- **Storing unsubscribe tokens in database:** Use signed tokens instead - stateless, no DB lookup needed
- **Single chat_id for all users:** The old pattern - must now dispatch per-user
- **Blocking email sends:** Always use async or background tasks
- **Exposing user IDs in URLs:** Use signed tokens that contain user_id internally
- **Mixing polling and webhooks:** Use one or the other, never both simultaneously
- **Not verifying webhook secret token:** 97% of bots skip this, creating security vulnerabilities

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Signed URLs | Custom HMAC | itsdangerous URLSafeTimedSerializer | Handles encoding, expiry, signature in one call |
| Email sending | smtplib directly | fastapi-mail | Async, connection pooling, template support |
| Telegram updates | Custom HTTP polling | python-telegram-bot Application | Handles rate limits, retries, update parsing |
| Deep linking URLs | String concatenation | helpers.create_deep_linked_url() | Proper encoding, bot username handling |

**Key insight:** The libraries handle edge cases (encoding, timing attacks, rate limits) that custom implementations miss. itsdangerous uses constant-time comparison for signatures.

## Common Pitfalls

### Pitfall 1: Telegram Rate Limits
**What goes wrong:** Sending too many messages causes 429 errors and temporary bans
**Why it happens:** Not respecting Telegram's rate limits (1 msg/sec per chat, 30 msg/sec bulk)
**How to avoid:** Add delays between messages (existing code has 0.5s delay), batch notifications into single messages
**Warning signs:** TelegramError with "Too Many Requests" or status code 429

### Pitfall 2: Webhook Security
**What goes wrong:** Anyone can send fake updates to your webhook endpoint
**Why it happens:** Not verifying the secret_token header
**How to avoid:** Always set and verify `secret_token` in setWebhook and request headers (X-Telegram-Bot-Api-Secret-Token)
**Warning signs:** Bot responding to commands you didn't send

### Pitfall 3: Expired Link Codes Remain in Database
**What goes wrong:** Database fills with expired/used codes
**Why it happens:** No cleanup job for telegram_link_codes table
**How to avoid:** Add cleanup to existing session cleanup job, or use signed tokens instead
**Warning signs:** Table growing unbounded

### Pitfall 4: Unsubscribe Token Enumeration
**What goes wrong:** Attacker guesses user IDs via unsubscribe URLs
**Why it happens:** Using predictable user IDs in URLs without signing
**How to avoid:** itsdangerous embeds user_id in signed payload, not visible in URL
**Warning signs:** N/A - use signed tokens from the start

### Pitfall 5: Email Deliverability
**What goes wrong:** Emails go to spam or bounce
**Why it happens:** Missing SPF/DKIM records, bad SMTP reputation
**How to avoid:** Use reputable SMTP provider, configure DNS records properly
**Warning signs:** Low delivery rates, bounces in logs

### Pitfall 6: Blocking the Scheduler
**What goes wrong:** Notification sending blocks event fetching
**Why it happens:** Synchronous email/telegram calls in scheduler job
**How to avoid:** Use async sending with proper error handling (existing notifier uses ThreadPoolExecutor for async-from-sync)
**Warning signs:** Scheduler job takes much longer than expected

### Pitfall 7: Event Loop Conflicts
**What goes wrong:** RuntimeError "This event loop is already running"
**Why it happens:** Mixing sync/async code incorrectly (existing code handles this in notifier.py)
**How to avoid:** Follow existing pattern in notifier.py using ThreadPoolExecutor for async operations
**Warning signs:** RuntimeError on notification send

## Code Examples

Verified patterns from official sources:

### Database Schema Extensions

```sql
-- User notification preferences (extends users table)
-- Note: telegram_chat_id column already exists in current schema
ALTER TABLE users ADD COLUMN telegram_enabled BOOLEAN DEFAULT 0;
ALTER TABLE users ADD COLUMN email_enabled BOOLEAN DEFAULT 1;

-- Telegram link codes (temporary, for linking flow)
CREATE TABLE IF NOT EXISTS telegram_link_codes (
    code TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    used_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_link_codes_user ON telegram_link_codes(user_id);
CREATE INDEX IF NOT EXISTS idx_link_codes_expires ON telegram_link_codes(expires_at);
```

### Config Schema Extension

```yaml
# config.yaml additions
email:
  server: smtp.example.com
  port: 587                    # 587 for STARTTLS, 465 for SSL
  username: notifications@example.com
  password: "app-password"
  from_address: notifications@example.com
  from_name: "RA Tracker"
  starttls: true
  ssl_tls: false

telegram:
  bot_token: "existing-token"  # Shared bot token (existing)
  chat_id: ""                  # DEPRECATED - now per-user, kept for admin test
  webhook_secret: "random-secret-for-webhook-verification"
  use_webhook: false           # false = polling, true = webhook
  webhook_url: ""              # Required if use_webhook is true
```

### Config Dataclass Extensions

```python
# In config.py - add EmailConfig dataclass
@dataclass
class EmailConfig:
    server: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    from_address: str = ""
    from_name: str = "RA Tracker"
    starttls: bool = True
    ssl_tls: bool = False

# Extend TelegramConfig
@dataclass
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""  # Kept for backwards compatibility / admin test
    webhook_secret: str = ""
    use_webhook: bool = False
    webhook_url: str = ""

# Add to Config dataclass
@dataclass
class Config:
    # ... existing fields ...
    email: EmailConfig = field(default_factory=EmailConfig)
```

### Toggle Switch UI Pattern (Settings Page)

```html
<!-- Telegram Section -->
<div class="notification-channel">
    <div class="channel-header">
        <span class="channel-icon">TG</span>
        <span class="channel-name">Telegram</span>
    </div>

    {% if user.telegram_chat_id %}
        <!-- Linked state -->
        <div class="channel-status">
            <span class="badge badge-success">Linked</span>
            <form action="/settings/telegram/unlink" method="post" class="inline">
                <button type="submit" class="btn btn-sm btn-secondary">Unlink</button>
            </form>
        </div>
        <label class="toggle">
            <input type="checkbox" name="telegram_enabled"
                   {% if user.telegram_enabled %}checked{% endif %}>
            <span class="toggle-slider"></span>
            <span class="toggle-label">Send notifications</span>
        </label>
    {% else %}
        <!-- Not linked state -->
        <div class="channel-status text-muted">
            Not linked
        </div>
        <button type="button" class="btn btn-primary" onclick="showLinkDialog()">
            Link Telegram
        </button>
    {% endif %}
</div>

<!-- Email Section -->
<div class="notification-channel">
    <div class="channel-header">
        <span class="channel-icon">@</span>
        <span class="channel-name">Email</span>
    </div>
    <div class="channel-status">
        <span class="text-muted">{{ user.email }}</span>
    </div>
    <label class="toggle">
        <input type="checkbox" name="email_enabled"
               {% if user.email_enabled %}checked{% endif %}>
        <span class="toggle-slider"></span>
        <span class="toggle-label">Send notifications</span>
    </label>
</div>
```

### Bot Command Handlers

```python
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop - disable Telegram notifications."""
    chat_id = update.effective_chat.id
    user = db.get_user_by_telegram_chat_id(chat_id)

    if not user:
        await update.message.reply_text(
            "This Telegram account is not linked to any RA Tracker account."
        )
        return

    db.set_user_telegram_enabled(user.id, False)
    await update.message.reply_text(
        "Telegram notifications disabled.\n\n"
        "To re-enable, visit your RA Tracker settings page or send /start"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start - re-enable notifications or show welcome."""
    chat_id = update.effective_chat.id
    user = db.get_user_by_telegram_chat_id(chat_id)

    if user:
        # Already linked - re-enable notifications
        db.set_user_telegram_enabled(user.id, True)
        await update.message.reply_text(
            "Telegram notifications re-enabled!\n\n"
            "You'll receive event alerts here when matches are found."
        )
    else:
        # Not linked - show instructions
        await update.message.reply_text(
            "Welcome to RA Tracker Bot!\n\n"
            "To link your account:\n"
            "1. Log in to RA Tracker\n"
            "2. Go to Settings > Notifications\n"
            "3. Click 'Link Telegram'\n"
            "4. Send the code here with /link CODE"
        )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Global chat_id in config | Per-user chat_id in database | This phase | Multi-user support |
| No email notifications | fastapi-mail SMTP | This phase | Second channel option |
| DB-stored unsubscribe tokens | Signed stateless tokens | Current best practice | No DB bloat, no cleanup needed |
| Polling only | Webhook preferred | python-telegram-bot v20+ | Lower latency, better scaling |

**Deprecated/outdated:**
- **Global telegram.chat_id config:** Still works for admin test messages, but notifications now per-user
- **python-telegram-bot Updater class:** Deprecated in v20+, use Application directly

## Open Questions

Things that couldn't be fully resolved:

1. **Webhook vs Polling Decision**
   - What we know: Webhooks are better for production (lower latency, 60-80% resource savings)
   - What's unclear: Does the deployment environment have public HTTPS?
   - Recommendation: Implement both, config toggle. Default to polling for simplicity.

2. **Link Code Storage**
   - What we know: Can use DB table or signed tokens
   - What's unclear: User preference on code format (short code vs deep link)
   - Recommendation: Use DB table with 1-hour expiry, simple alphanumeric codes (per CONTEXT.md decision)

3. **SMTP Provider**
   - What we know: fastapi-mail works with any SMTP
   - What's unclear: Which SMTP service will admin use?
   - Recommendation: Document common providers (Gmail, SendGrid, Mailgun) in config.example.yaml

4. **Secret Key Management**
   - What we know: itsdangerous needs a secret key for signing
   - What's unclear: Where to store the secret key
   - Recommendation: Add to config.yaml as `app.secret_key`, or generate from existing session config

## Sources

### Primary (HIGH confidence)
- [python-telegram-bot Wiki - Webhooks](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Webhooks) - Application builder, webhook setup, secret token verification
- [itsdangerous Documentation](https://itsdangerous.palletsprojects.com/) - URLSafeTimedSerializer, salt, exception handling
- [fastapi-mail PyPI/Docs](https://sabuhish.github.io/fastapi-mail/) - ConnectionConfig, MessageSchema, template usage
- [Telegram Bot API FAQ](https://core.telegram.org/bots/faq) - Rate limits, deep linking

### Secondary (MEDIUM confidence)
- [Telegram Bot Webhook vs Polling Guide](https://hostman.com/tutorials/difference-between-polling-and-webhook-in-telegram-bots/) - Resource comparison, deployment considerations
- [freeCodeCamp Webhook Tutorial](https://www.freecodecamp.org/) - FastAPI integration pattern (verified against official docs)

### Tertiary (LOW confidence)
- Community discussions on multi-user notification architecture - General patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified in official docs, python-telegram-bot 22.5 and itsdangerous 2.0.1 already installed
- Architecture: HIGH - Patterns verified against official docs and working examples
- Pitfalls: MEDIUM - Based on documentation warnings and community experience

**Research date:** 2026-01-30
**Valid until:** 60 days (stable libraries, no major version changes expected)
