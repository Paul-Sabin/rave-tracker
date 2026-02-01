# Testing Patterns

**Analysis Date:** 2026-01-19

## Test Framework

**Runner:**
- No formal test framework configured
- No pytest.ini, pyproject.toml, or setup.cfg with test configuration
- No test suite exists for the main `ra-tracker` application

**Assertion Library:**
- Not applicable (no test framework)

**Run Commands:**
```bash
# No test commands configured
# Manual execution of exploration scripts:
python explore_api.py        # API exploration
python test_ra_api.py        # GraphQL API test
python test_ra_scrape.py     # Playwright scraping test
```

## Current Test-Like Scripts

**Location:**
- Root directory: `C:/Users/psabi/onedrive/mysyncfolder/claude/ra-tips/`
- NOT part of main `ra-tracker` application

**Files:**
- `test_ra_api.py` - GraphQL API connectivity test
- `test_ra_scrape.py` - Playwright web scraping feasibility test
- `explore_api.py` - API exploration/discovery script
- `explore_api_v2.py` - Additional API exploration

**Purpose:**
- These are exploration/feasibility scripts, NOT automated tests
- Used during development to validate API access
- Run manually, not via test runner

## Test File Organization

**Location:**
- No dedicated test directory exists
- No `tests/` folder in `ra-tracker/`

**Naming:**
- Exploration scripts use `test_` prefix but are not actual tests
- Pattern if tests were added: co-located or `tests/` directory

**Recommended Structure (not yet implemented):**
```
ra-tracker/
├── ra_tracker/
│   └── ...
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_database.py
    ├── test_ra_client.py
    ├── test_fetcher.py
    └── test_notifier.py
```

## Test Patterns in Exploration Scripts

**Main Function Pattern:**
```python
def main():
    print("=" * 60)
    print("RA.co GraphQL API Test")
    print("=" * 60)

    results = fetch_events()

    if results["success"]:
        print("SUCCESS! GraphQL API is accessible.")
    else:
        print("FAILED - API not accessible")

    # Save results to JSON
    with open("test_api_output.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
```

**Result Dictionary Pattern:**
```python
results = {
    "success": False,
    "error": None,
    "events": [],
    "page_title": None,
    "status_code": None
}
```

## Mocking

**Framework:** Not established

**What Would Need Mocking:**
- `requests.Session` / HTTP calls to ra.co GraphQL API
- `telegram.Bot` for notification tests
- SQLite database for isolated tests
- `asyncio` event loops

**Recommended Mocking Pattern (not implemented):**
```python
from unittest.mock import Mock, patch

def test_ra_client_search():
    with patch('ra_tracker.api.ra_client.requests.Session') as mock_session:
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"search": []}}
        mock_session.return_value.post.return_value = mock_response

        client = RAClient()
        results = client.search_artists("test")

        assert results == []
```

## Fixtures and Factories

**Test Data:**
- Not established (no formal test infrastructure)

**Sample Data Files:**
- `api_exploration.json` - Captured API responses
- `test_api_output.json` - Test run output
- `test_output.json` - Scraping test output

**Recommended Fixture Pattern:**
```python
# conftest.py
import pytest
from datetime import date

@pytest.fixture
def sample_rule():
    from ra_tracker.database import Rule
    return Rule(
        id=1,
        rule_type="artist",
        target_id=11019,
        target_name="Maya Jane Coles",
        is_active=True,
        notify_mode="local"
    )

@pytest.fixture
def sample_event():
    from ra_tracker.database import Event
    return Event(
        id=12345,
        title="Test Event",
        date=date.today(),
        venue_name="Test Venue",
        artists=[(11019, "Maya Jane Coles", "/dj/mayajanecoles")]
    )

@pytest.fixture
def test_db(tmp_path):
    from ra_tracker.database import Database
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    db.init_schema()
    return db
```

## Coverage

**Requirements:** Not established

**View Coverage:**
```bash
# Would require pytest-cov installation:
# pip install pytest-cov
# pytest --cov=ra_tracker tests/
```

## Test Types

**Unit Tests:**
- Not implemented
- Should cover: Database operations, data parsing, notification formatting

**Integration Tests:**
- Not implemented
- Should cover: End-to-end fetch flow, scheduler jobs

**E2E Tests:**
- `test_ra_scrape.py` is a manual E2E validation (Playwright browser automation)
- Not automated in CI

## Manual Testing Scripts

**API Connectivity Test (`test_ra_api.py`):**
```python
def fetch_events():
    """Fetch events from ra.co GraphQL API."""
    # Makes actual HTTP request to ra.co
    # Validates response structure
    # Returns success/failure dict with events
```

**Scraping Feasibility Test (`test_ra_scrape.py`):**
```python
async def scrape_ra_events():
    """Attempt to scrape using Playwright."""
    # Launches headless browser
    # Tests anti-bot detection measures
    # Extracts event data from DOM
```

**API Exploration (`explore_api.py`):**
```python
def explore_event_listings():
    """Explore all available fields in event listings."""
    # Tests GraphQL query structure
    # Discovers available fields
    # Saves results to JSON
```

## Inline Test Blocks

**Pattern in Source Files:**
Several source files include `if __name__ == "__main__":` blocks for manual testing:

**`ra_tracker/api/ra_client.py`:**
```python
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    client = RAClient()

    print("Testing targeted queries...\n")

    # Test artist events
    print("Artist events (Maya Jane Coles - ID 11019):")
    events = client.get_artist_events(11019)
    for e in events[:3]:
        print(f"  {e.date} | {e.title} @ {e.venue_name}")
```

**`ra_tracker/services/fetcher.py`:**
```python
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from ..database import Rule

    db = get_db()

    # Add test rules
    if not db.rule_exists("venue", 75457):
        db.add_rule(Rule(id=None, rule_type="venue", target_id=75457, target_name="OHM Berlin"))

    results = run_fetch()
    for rule_id, events in results.items():
        rule = db.get_rule(rule_id)
        print(f"\n{rule.target_name}: {len(events)} events")
```

## Recommendations for Test Implementation

**Priority 1 - Database Tests:**
```python
# tests/test_database.py
def test_add_rule(test_db):
    rule = Rule(id=None, rule_type="artist", target_id=123, target_name="Test")
    rule_id = test_db.add_rule(rule)
    assert rule_id is not None
    assert test_db.rule_exists("artist", 123)

def test_upsert_event(test_db, sample_event):
    test_db.upsert_event(sample_event)
    retrieved = test_db.get_event(sample_event.id)
    assert retrieved.title == sample_event.title
```

**Priority 2 - API Client Tests (mocked):**
```python
# tests/test_ra_client.py
def test_parse_event():
    client = RAClient()
    event_data = {
        "id": "123",
        "title": "Test Event",
        "date": "2026-01-20",
        "venue": {"id": "1", "name": "Test Venue"}
    }
    event = client._parse_event(event_data)
    assert event.id == 123
    assert event.title == "Test Event"
```

**Priority 3 - Notifier Tests (mocked):**
```python
# tests/test_notifier.py
def test_format_message(sample_event, sample_rule):
    notifier = Notifier()
    message = notifier.format_message(sample_event, sample_rule)
    assert sample_event.title in message
    assert sample_rule.target_name in message
```

---

*Testing analysis: 2026-01-19*
