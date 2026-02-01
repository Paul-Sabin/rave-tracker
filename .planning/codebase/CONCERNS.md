# Codebase Concerns

**Analysis Date:** 2026-01-19

## Tech Debt

**Duplicate Code in Event Parsing:**
- Issue: The `Event` dataclass is defined in both `ra-tracker/ra_tracker/database.py` (lines 147-182) and as `RAEvent` in `ra-tracker/ra_tracker/api/ra_client.py` (lines 17-47) with nearly identical fields
- Files: `ra-tracker/ra_tracker/database.py`, `ra-tracker/ra_tracker/api/ra_client.py`
- Impact: Changes to event structure require updates in two places; conversion code in `fetcher.py` (lines 100-125) exists solely to map between these
- Fix approach: Extract a single shared Event model, or have database use RAEvent directly

**Repeated Query Patterns in GraphQL Client:**
- Issue: Three nearly identical query methods (`get_artist_events`, `get_venue_events`, `get_promoter_events`) with 100+ lines of duplicated GraphQL query strings
- Files: `ra-tracker/ra_tracker/api/ra_client.py` (lines 215-444)
- Impact: Bug fixes or field additions must be applied three times; easy to miss one
- Fix approach: Extract shared query fragment, parameterize entity type

**Global Singletons Pattern:**
- Issue: Multiple modules use global singleton pattern with `_db`, `_config`, `_scheduler` module-level variables
- Files: `ra-tracker/ra_tracker/database.py` (lines 646-662), `ra-tracker/ra_tracker/config.py` (lines 114-128), `ra-tracker/ra_tracker/scheduler/jobs.py` (line 17)
- Impact: Makes testing difficult, hidden dependencies, potential thread safety issues
- Fix approach: Use dependency injection or FastAPI's dependency system consistently

**Exploratory Scripts at Root Level:**
- Issue: Multiple test/exploration scripts (`test_ra_scrape.py`, `test_ra_api.py`, `explore_api.py`, `explore_api_v2.py`) exist at project root with no organization
- Files: `test_ra_scrape.py`, `test_ra_api.py`, `explore_api.py`, `explore_api_v2.py`
- Impact: Clutters project root, unclear relationship to main application, not integrated into test suite
- Fix approach: Move to `scripts/` or `exploration/` directory, or remove if no longer needed

**Stray File:**
- Issue: File named `nul` exists in project root (likely accidental Windows NUL device redirect)
- Files: `nul`
- Impact: Potential confusion, clutters project
- Fix approach: Delete the file

## Known Bugs

**Silent Exception Handling in Date Parsing:**
- Symptoms: Date parsing failures silently return None instead of logging or raising
- Files: `ra-tracker/ra_tracker/api/ra_client.py` (lines 127-152)
- Trigger: Malformed date strings from RA API
- Workaround: Events with parse failures have None dates, which are filtered out

**Artist List Truncation in Notifier:**
- Symptoms: Notification messages only show first 5 artists from `event.artists` but the tuple unpacking expects 2 elements when artists tuple actually has 3
- Files: `ra-tracker/ra_tracker/services/notifier.py` (lines 66-67)
- Trigger: Events with artists (which now contain 3-tuple with URL)
- Workaround: Code has `for _, name in event.artists[:5]` but artists are 3-tuples `(id, name, url)` - will raise ValueError

## Security Considerations

**CRITICAL: Exposed Telegram Bot Token:**
- Risk: Real Telegram bot token hardcoded in `config.yaml`: `8200624905:AAFcNY1sdCHpakoVbeJBh6PQvFon3xfxxac`
- Files: `ra-tracker/config.yaml` (line 7)
- Current mitigation: None - token is in plaintext
- Recommendations:
  1. Immediately revoke this token via BotFather
  2. Use environment variables for secrets
  3. Add `config.yaml` to `.gitignore`, keep only `config.example.yaml` in repo

**Web Server Binds to All Interfaces:**
- Risk: Default config binds to `0.0.0.0:8080`, exposing web UI to network
- Files: `ra-tracker/ra_tracker/config.py` (line 26), `ra-tracker/config.yaml` (lines 12-13)
- Current mitigation: None
- Recommendations: Default to `127.0.0.1` for local-only access; document network exposure if needed

**No Authentication on Web UI:**
- Risk: All web endpoints are publicly accessible without authentication
- Files: `ra-tracker/ra_tracker/web/routes.py` (all routes)
- Current mitigation: None
- Recommendations: Add basic auth or API key for sensitive operations like settings changes

**No Input Validation on API Endpoints:**
- Risk: Rule addition endpoints accept arbitrary `target_id` and `target_name` without sanitization
- Files: `ra-tracker/ra_tracker/web/routes.py` (lines 87-113, 301-329)
- Current mitigation: SQLite parameterized queries prevent SQL injection
- Recommendations: Add validation for reasonable ID ranges, name length limits

**No CSRF Protection:**
- Risk: Form submissions (add rule, delete rule, save settings) lack CSRF tokens
- Files: `ra-tracker/ra_tracker/web/routes.py` (POST endpoints)
- Current mitigation: None - personal tool assumption
- Recommendations: Add CSRF middleware if exposing to network

## Performance Bottlenecks

**N+1 Query Pattern in Event Retrieval:**
- Problem: `get_upcoming_events()` fetches events, then for each event issues 3 additional queries (artists, promoters, rules)
- Files: `ra-tracker/ra_tracker/database.py` (lines 477-555)
- Cause: Sequential queries in loop instead of JOINs
- Improvement path: Use JOINs or batch load related data; alternatively use SQLAlchemy ORM with eager loading

**Full Event Cache Clear on Each Fetch:**
- Problem: `clear_all_events()` deletes all events before each fetch cycle
- Files: `ra-tracker/ra_tracker/scheduler/jobs.py` (line 63), `ra-tracker/ra_tracker/database.py` (lines 578-584)
- Cause: Simplistic "delete all, re-fetch all" approach
- Improvement path: Implement incremental updates, only fetch events not already cached

**Synchronous API Requests in Scheduler:**
- Problem: Event fetching uses synchronous `requests` library blocking the scheduler thread
- Files: `ra-tracker/ra_tracker/api/ra_client.py` (line 106), `ra-tracker/ra_tracker/scheduler/jobs.py`
- Cause: No async HTTP client used
- Improvement path: Use `httpx` with async/await, or run fetcher in thread pool

## Fragile Areas

**Undocumented GraphQL API Dependency:**
- Files: `ra-tracker/ra_tracker/api/ra_client.py`
- Why fragile: Relies on undocumented ra.co GraphQL API that could change without notice
- Safe modification: Add defensive checks for missing fields, log API responses on error
- Test coverage: No tests; manual testing only via `if __name__ == "__main__"` blocks

**Telegram Message Formatting:**
- Files: `ra-tracker/ra_tracker/services/notifier.py` (lines 52-97, 99-106)
- Why fragile: MarkdownV2 escaping is complex; special characters in event titles can break formatting
- Safe modification: Always test with special characters (`*`, `_`, `[`, etc.)
- Test coverage: None

**Migration System:**
- Files: `ra-tracker/ra_tracker/database.py` (lines 89-132)
- Why fragile: Migrations run via try/except, catching OperationalError - if a migration partially fails, schema could be inconsistent
- Safe modification: Test migrations on fresh DB and existing DB before deploying
- Test coverage: None

## Scaling Limits

**SQLite Single-File Database:**
- Current capacity: Handles hundreds of events fine
- Limit: Concurrent writes will fail; single-user assumption
- Scaling path: If needed, migrate to PostgreSQL; current schema is compatible

**In-Memory Scheduler State:**
- Current capacity: Single instance only
- Limit: Cannot run multiple instances; `_last_fetch_time` is process-local
- Scaling path: Store scheduler state in database if distributed deployment needed

## Dependencies at Risk

**Undocumented External API:**
- Risk: ra.co GraphQL API is undocumented and could change or block requests at any time
- Impact: Core functionality (event fetching) would break
- Migration plan: API exploration scripts suggest web scraping as fallback (see `test_ra_scrape.py`), but scraping is more fragile

**Rate Limiting Concerns:**
- Risk: Only 1-second delay between requests (`MIN_REQUEST_INTERVAL = 1.0`)
- Impact: RA could rate-limit or block if fetching many rules
- Migration plan: Implement exponential backoff, respect 429 responses

## Missing Critical Features

**No Error Recovery for Failed Fetches:**
- Problem: If a rule fetch fails, it's logged but no retry mechanism exists
- Blocks: Unreliable notifications if RA API has temporary issues

**No Database Backup:**
- Problem: SQLite file is only data store; no backup mechanism
- Blocks: Data loss if file corrupted or deleted

**No Logging to File:**
- Problem: Logs go to stdout only; lost when application restarts
- Blocks: Debugging production issues

## Test Coverage Gaps

**Zero Test Files for Main Application:**
- What's not tested: Everything in `ra-tracker/ra_tracker/`
- Files: All of `ra-tracker/ra_tracker/`
- Risk: Any change could break existing functionality unnoticed
- Priority: High - core business logic has no tests

**Exploration Scripts Are Not Tests:**
- What's not tested: `test_ra_scrape.py` and `test_ra_api.py` are manual exploration scripts, not automated tests
- Files: `test_ra_scrape.py`, `test_ra_api.py`
- Risk: Name suggests tests but provides no regression protection
- Priority: Medium - rename to avoid confusion, or convert to actual tests

**Database Operations Untested:**
- What's not tested: All CRUD operations in `database.py`
- Files: `ra-tracker/ra_tracker/database.py`
- Risk: Migration changes, schema updates could break data access
- Priority: High - data layer is foundation for application

**Notification Formatting Untested:**
- What's not tested: Telegram message formatting, MarkdownV2 escaping
- Files: `ra-tracker/ra_tracker/services/notifier.py`
- Risk: Special characters in event data could cause notification failures
- Priority: Medium - affects user experience but app continues working

---

*Concerns audit: 2026-01-19*
