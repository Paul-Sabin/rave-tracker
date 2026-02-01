# Coding Conventions

**Analysis Date:** 2026-02-01

## Naming Patterns

**Files:**
- Python modules: `snake_case.py`
- Module directories: `snake_case/`
- Entry points: `main.py` within package
- Config files: `config.yaml`, `config.example.yaml`

**Functions:**
- Functions: `snake_case()`
- Private/helper: `_leading_underscore()`
- Async functions: `function_name_async()` suffix for async variants

**Variables:**
- Variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE` (e.g., `RA_GRAPHQL_URL`, `MIN_REQUEST_INTERVAL`)
- Private module globals: `_leading_underscore` (e.g., `_config`, `_db`, `_scheduler`)

**Types/Classes:**
- Classes: `PascalCase` (e.g., `RAClient`, `Database`, `Fetcher`)
- Dataclasses: `PascalCase` (e.g., `RAEvent`, `Rule`, `Event`)
- Type hints used consistently with `Optional`, `List`, `Dict`, `Tuple`

## Code Style

**Formatting:**
- No explicit formatter configured (no `.prettierrc`, `black.toml`, etc.)
- Implicit style: 4-space indentation
- Line lengths: Generally under 100 characters

**Linting:**
- No explicit linter configured (no `.flake8`, `pylint.rc`, `ruff.toml`)
- Standard Python conventions followed

**Type Hints:**
- Use type hints on function signatures
- Use `Optional[T]` for nullable parameters
- Use `List[T]`, `Dict[K, V]`, `Tuple[T, ...]` for collections

Example:
```python
def get_rule(self, rule_id: int) -> Optional[Rule]:
def fetch_for_rule(self, rule: Rule) -> List[Event]:
def search_artists(self, query: str, limit: int = 10) -> List[RAArtist]:
```

## Import Organization

**Order:**
1. Standard library imports (`import json`, `import logging`, `from datetime import...`)
2. Third-party imports (`import requests`, `from fastapi import...`)
3. Local/relative imports (`from ..config import get_config`, `from .routes import router`)

**Path Aliases:**
- Relative imports within package: `from ..module import thing`
- No custom path aliases configured

**Example Pattern:**
```python
"""Module docstring."""

import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any

import requests
from fastapi import APIRouter, Request

from ..api.ra_client import RAClient
from ..config import get_config
from ..database import get_db, Rule
```

## Error Handling

**Patterns:**
- Use try/except with specific exception types
- Log errors with `logger.error()` or `logger.warning()`
- Return empty collections or `None` on failure (no exceptions propagated to callers for non-critical operations)
- Re-raise only for critical failures

**HTTP/API Error Pattern:**
```python
try:
    response = self.session.post(url, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "errors" in data:
        logger.error(f"GraphQL errors: {data['errors']}")
        raise Exception(f"GraphQL errors: {data['errors']}")
    return data.get("data", {})
except requests.RequestException as e:
    logger.error(f"Request failed: {e}")
    raise
```

**Database Error Pattern:**
```python
try:
    yield conn
    conn.commit()
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
```

**Graceful Failure Pattern:**
```python
try:
    # operation
except Exception as e:
    logger.warning(f"Failed to send notification (non-blocking): {e}")
    return False
```

## Logging

**Framework:** Python standard `logging` module

**Setup Pattern:**
```python
import logging
logger = logging.getLogger(__name__)
```

**Patterns:**
- `logger.info()` - Normal operations, milestones
- `logger.warning()` - Non-critical failures, missing config
- `logger.error()` - Critical failures, with optional `exc_info=True`
- `logger.debug()` - Skip messages when condition not met

**Examples:**
```python
logger.info(f"Fetched {len(events)} events for {rule.target_name}")
logger.warning(f"Telegram chat_id not configured")
logger.error(f"Failed to fetch events for rule {rule.target_name}: {e}")
logger.debug("Telegram not configured, skipping notification")
```

## Comments

**When to Comment:**
- Module-level docstrings explaining purpose
- Class-level docstrings
- Function docstrings (Google-style)
- Inline comments for non-obvious logic

**Docstring Style:**
```python
"""Module description.

Additional details if needed.
"""

class Fetcher:
    """Service for fetching events based on tracking rules."""

def fetch_for_rule(self, rule: Rule) -> List[Event]:
    """Fetch events for a specific rule.

    Args:
        rule: The tracking rule

    Returns:
        List of events fetched for this rule
    """
```

## Function Design

**Size:**
- Functions kept reasonably short (typically under 50 lines)
- Complex logic split into helper methods (e.g., `_parse_event()`, `_convert_event()`)

**Parameters:**
- Required parameters first, optional with defaults after
- Use keyword arguments for form data and API parameters
- Use dataclasses for structured data

**Return Values:**
- Explicit return types with type hints
- Return empty collections (`[]`, `{}`) rather than `None` when applicable
- Return `Optional[T]` for single-item lookups that may not exist
- Return boolean for success/failure operations

## Module Design

**Exports:**
- No explicit `__all__` definitions
- Implicit exports via module structure

**Barrel Files:**
- `__init__.py` files are minimal or empty
- Main package `__init__.py` contains version: `__version__ = "0.1.0"`

**Singleton/Global Pattern:**
- Module-level private globals: `_config: Optional[Config] = None`
- Getter/setter functions: `get_config()`, `set_config()`

```python
# Global database instance
_db: Optional[Database] = None

def get_db() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
        _db.init_schema()
    return _db

def set_db(db: Database) -> None:
    """Set the global database instance."""
    global _db
    _db = db
```

## Dataclass Patterns

**Definition Style:**
```python
@dataclass
class Rule:
    """Tracking rule for artist, venue, or promoter."""
    id: Optional[int]
    rule_type: str  # 'artist', 'venue', 'promoter'
    target_id: int  # RA ID
    target_name: str  # Display name
    is_active: bool = True
    notify_mode: str = 'local'  # 'all', 'local', 'none'
    created_at: Optional[datetime] = None
```

**Post-init for defaults:**
```python
def __post_init__(self):
    if self.artists is None:
        self.artists = []
    if self.promoters is None:
        self.promoters = []
```

## Async Patterns

**Mixed sync/async:**
- Provide both sync and async variants where needed
- Use `_run_async()` helper to call async from sync contexts
- Name async variants with `_async` suffix

```python
async def send_notification_async(self, event: Event, rule: Rule) -> bool:
    """Send a notification asynchronously."""
    ...

def send_notification(self, event: Event, rule: Rule) -> bool:
    """Send a notification synchronously."""
    return _run_async(self.send_notification_async(event, rule))
```

## Configuration Patterns

**YAML Configuration:**
- Use dataclasses for typed config sections
- Support environment variable overrides
- Provide sensible defaults

```python
@dataclass
class SchedulerConfig:
    fetch_interval_hours: int = 6
    event_horizon_days: int = 30
```

**Environment Override Pattern:**
```python
# Override with environment variables
if os.environ.get("TELEGRAM_BOT_TOKEN"):
    config.telegram.bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
```

## UI Conventions

### Styling Framework

**Framework:** Tailwind CSS v4 (CDN-based)

**CSS Variables:** Use CSS custom properties for theming
- `var(--color-bg-dark)` - dark background
- `var(--color-border)` - border color
- `var(--color-text)` - primary text
- `var(--color-text-muted)` - secondary/muted text
- `var(--color-accent)` - accent color

### Rule Toggle UI Pattern

**Three-State Cycling Buttons (Artists):**
- Buttons cycle through: Global -> Local -> Off -> Global
- Each click sets the current value and displays the next state

**Two-State Toggle Buttons (Venues/Promoters):**
- Buttons toggle between: On <-> Off

**Implementation Pattern:**
```html
<!-- Artist rule with 3-state cycle -->
<form action="/rules/{{ rule.id }}/notify-mode" method="post" class="cycle-form">
    {% if rule.notify_mode == 'none' %}
    <button type="submit" name="mode" value="all" class="cycle-btn off">Off</button>
    {% elif rule.notify_mode == 'local' %}
    <button type="submit" name="mode" value="none" class="cycle-btn local">Local</button>
    {% else %}
    <button type="submit" name="mode" value="local" class="cycle-btn all">Global</button>
    {% endif %}
</form>

<!-- Venue/Promoter rule with 2-state toggle -->
<form action="/rules/{{ rule.id }}/notify-mode" method="post" class="cycle-form">
    {% if rule.notify_mode == 'none' %}
    <button type="submit" name="mode" value="all" class="cycle-btn off">Off</button>
    {% else %}
    <button type="submit" name="mode" value="none" class="cycle-btn on">On</button>
    {% endif %}
</form>
```

### Button Color Conventions

| State | Class | Background Color | Text Color | Usage |
|-------|-------|------------------|------------|-------|
| Off | `.off` | `var(--color-bg-dark)` | `var(--color-text-muted)` | Disabled/inactive state |
| On | `.on` | `#22c55e` (green) | `#000` (black) | Venues/Promoters enabled |
| Local | `.local` | `#22c55e` (green) | `#000` (black) | Artists - local events only |
| Global/All | `.all` | `#0891b2` (teal) | `#fff` (white) | Artists - all events |

**CSS Implementation:**
```css
/* Off state - gray/muted */
.cycle-btn.off {
    background: var(--color-bg-dark);
    color: var(--color-text-muted);
    border: 1px solid var(--color-border);
}

/* On state - green */
.cycle-btn.on {
    background: #22c55e;
    color: #000;
}

/* Local state - green */
.cycle-btn.local {
    background: #22c55e;
    color: #000;
}

/* All/Global state - teal */
.cycle-btn.all {
    background: #0891b2;
    color: #fff;
}
```

### AJAX Form Submissions

**Purpose:** Preserve scroll position when updating rule settings (no page reload)

**Pattern:** Rule settings forms use AJAX with manual redirect handling
```javascript
document.querySelectorAll('.cycle-form').forEach(form => {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const btn = form.querySelector('button');
        const action = form.action;
        const mode = btn.value;

        btn.disabled = true;

        try {
            const formData = new FormData();
            formData.append('mode', mode);

            const response = await fetch(action, {
                method: 'POST',
                body: formData,
                redirect: 'manual'  // Don't follow redirect
            });

            updateCycleButton(btn, mode);  // Update UI inline
        } catch (err) {
            console.error('Failed to update mode:', err);
        } finally {
            btn.disabled = false;
        }
    });
});
```

**Required Behavior:**
- Disable button during request to prevent double-clicks
- Update button appearance inline after successful response
- Do not follow redirects (use `redirect: 'manual'`)

### Mobile Layout Conventions

**Breakpoint:** 640px (max-width)

**Touch Targets:** Minimum 44px height for interactive elements

**Mobile Rule Items:**
- Single-row layout (flex-direction: row)
- Compact cycle buttons: 60px width, 32px min-height
- Small delete button: 36px square with icon only

**Mobile Button Pattern:**
```css
@media (max-width: 640px) {
    .cycle-btn {
        width: 60px;
        font-size: 0.7rem;
        padding: 0.4rem 0.25rem;
        min-height: 32px;
    }
    .delete-form {
        width: 36px;
    }
    .delete-form .btn {
        width: 36px;
        padding: 0.25rem;
        font-size: 0;  /* Hide text */
        min-height: 32px;
    }
    .delete-form .btn::before {
        content: "\2715";  /* Unicode X */
        font-size: 0.9rem;
    }
}
```

**Icon-Only Buttons:**
- Use `font-size: 0` to hide text content
- Use `::before` pseudo-element with content for icon
- Delete button uses Unicode X character (`\2715` or `"✕"`)

### Debounce Pattern for Search

**Use debounce for search inputs to avoid excessive API calls:**
```javascript
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}

document.getElementById('search-input').addEventListener('input', debounce(e => search(e.target.value), 300));
```

---

*Convention analysis: 2026-02-01*
