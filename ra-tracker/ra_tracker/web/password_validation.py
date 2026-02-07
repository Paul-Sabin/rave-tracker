"""Password validation following NIST SP 800-63B guidelines."""

from pathlib import Path
from typing import Tuple

# Load common passwords once at module import
_COMMON_PASSWORDS: set = set()


def _load_common_passwords():
    """Load common passwords list from data file."""
    global _COMMON_PASSWORDS
    password_file = Path(__file__).parent.parent / "data" / "common_passwords.txt"
    if password_file.exists():
        with open(password_file, "r", encoding="utf-8") as f:
            _COMMON_PASSWORDS = {line.strip().lower() for line in f if line.strip()}


_load_common_passwords()


def validate_password(password: str) -> Tuple[bool, str]:
    """Validate password against NIST guidelines.

    Rules (per CONTEXT.md):
    - Minimum 8 characters
    - Not in top 1000 common passwords
    - NO complexity requirements (no forced uppercase/numbers/symbols)

    Args:
        password: The password to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid, error_message is empty string
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"

    if password.lower() in _COMMON_PASSWORDS:
        return False, "This password is too common. Please choose a different one."

    return True, ""
