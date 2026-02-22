# Phase 4 Context: User Notifications

**Gathered:** 2026-01-30
**Phase Goal:** Allow each user to configure notification channels (Telegram and/or Email) with independent on/off toggles

## Decisions

### Telegram Linking Experience

| Question | Decision | Rationale |
|----------|----------|-----------|
| Linking code validity | 1 hour | Long enough to complete flow, short enough for security |
| Already linked state | Show 'Already linked' status | Require unlink first to change Telegram account |
| Invalid code response | Specific error reasons | "Code expired" vs "Code not found" vs "Already used" - helps users understand |
| After successful link | Send test message | "Linked successfully! You'll receive event notifications here." |

### Notification Content & Timing

| Question | Decision | Rationale |
|----------|----------|-----------|
| Timing | Immediate | Send as soon as scheduler detects match |
| Detail level | Rich details | Event name, date, venue, lineup, ticket link |
| Multi-match handling | Single notification | One notification mentioning all matching rules |
| Match reason display | Compact with visual distinction | Icon or color coding to distinguish artist/venue/promoter matches |

### Settings Page Layout

| Question | Decision | Rationale |
|----------|----------|-----------|
| Placement | Top section | Notifications first, other settings below |
| Toggle style | Toggle switches | Modern on/off switches like iOS/Android |
| Unconfigured channels | Greyed toggle + Setup button | Clear visual state, obvious action |
| Test button | One combined | Single button sends to all enabled channels |

### Unsubscribe Handling

| Question | Decision | Rationale |
|----------|----------|-----------|
| Email unsubscribe action | Disable email only | Keep account and Telegram active |
| Unsubscribe confirmation | Confirmation page | Simple page with link to re-enable in settings |
| Telegram /stop action | Disable + confirm | Disable notifications, confirm with re-enable instructions |
| Re-enable method | Both options | /start in Telegram OR toggle in settings |

## Technical Implications

1. **Database changes needed:**
   - Add `telegram_chat_id` column to users table
   - Add `telegram_enabled` boolean to users table
   - Add `email_enabled` boolean to users table
   - Add `telegram_link_codes` table (code, user_id, created_at, used_at)
   - Add `email_unsubscribe_tokens` table (token, user_id, created_at)

2. **Bot implementation:**
   - Webhook or polling for Telegram updates
   - Handle /link, /stop, /start commands
   - Validate codes and associate chat_id

3. **Email implementation:**
   - SMTP configuration in config.yaml
   - Signed unsubscribe tokens (no login required)
   - Rich HTML email templates

4. **Notification formatting:**
   - Visual icons/colors for rule types (artist 🎵, venue 📍, promoter 🎪)
   - Rich event details in both Telegram and Email
   - Merge multiple rule matches into single notification

---
*Context gathered: 2026-01-30*
