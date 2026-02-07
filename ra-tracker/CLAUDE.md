# CLAUDE.md

## Project UI Patterns
- Use Tailwind v4 for all styling (CDN-based).
- All rule-based toggles must support three modes: Global, Local, and Off.
- Form submissions for rule settings MUST use AJAX to preserve scroll position.
- Mobile target: Minimum 375px width with 44px touch targets.

## Configuration Patterns
- **Sensitive values** (secrets, API keys, passwords) go in `.env` file, never in config.yaml
- **python-dotenv** loads `.env` at startup before config parsing
- **config.yaml** can use placeholder syntax `${VAR_NAME}` - these get overridden by env vars
- **Environment variables** take priority over config.yaml values
- `.env` file is gitignored - use `config.example.yaml` to document required settings

## Security Patterns
- Argon2id for password hashing (OWASP 2025 recommendation)
- itsdangerous URLSafeTimedSerializer for signed tokens (verification, unsubscribe)
- Double Submit Cookie pattern for CSRF protection
- Dual rate limiting (IP + email hash) for login protection
- httponly/secure/samesite cookies for sessions
