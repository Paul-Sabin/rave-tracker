#!/usr/bin/env python3
"""End-to-end production email delivery check.

Registers a throwaway account on the deployed app using a disposable mailbox
that this script can actually read, then proves that verification and
password-reset mail really arrives -- not just that the app claims it sent.

Why a disposable mailbox: the app's own success banner is weak evidence. A
misconfigured BREVO_API_KEY makes is_email_configured() return False and the
send path reports failure, but for password reset the response is deliberately
byte-identical whether the send worked or not (account-enumeration guard). Only
the arrival of the message proves the transport.

Usage:
    venv/Scripts/python.exe scripts/verify_production_email.py
    venv/Scripts/python.exe scripts/verify_production_email.py --base-url http://localhost:8080

Optional admin audit-log checks (skipped when unset):
    RT_ADMIN_EMAIL=... RT_ADMIN_PASSWORD=... venv/Scripts/python.exe scripts/verify_production_email.py

Exit code 0 = every check passed, 1 = at least one failed.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
import time
from typing import Optional

import requests

DEFAULT_BASE_URL = "https://ravetracker.whotrustswho.com"
MAIL_API = "https://api.mail.tm"

# Must stay in sync with routes.py:42 -- the red banner shown when a send fails.
# Compared against unescaped page text, so keep the apostrophe out of the needle.
SEND_FAILED_NEEDLE = "send the verification email just now"

# Sender the app asks Brevo to send as (config.yaml email.from_address).
SENDER_HINT = "ravetracker@whotrustswho.com"

MAIL_POLL_TIMEOUT = 180
MAIL_POLL_INTERVAL = 5

results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    results.append((ok, name, detail))
    mark = "PASS" if ok else "FAIL"
    line = f"  [{mark}] {name}"
    if detail:
        line += f" -- {detail}"
    print(line, flush=True)
    return ok


def section(title: str) -> None:
    print(f"\n=== {title} ===", flush=True)


def csrf_from(html: str) -> Optional[str]:
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else None


class Mailbox:
    """A throwaway mail.tm inbox this script can read over HTTP."""

    def __init__(self) -> None:
        domains = requests.get(f"{MAIL_API}/domains", timeout=30).json()
        domain = domains["hydra:member"][0]["domain"]
        self.address = f"rt-verify-{secrets.token_hex(6)}@{domain}"
        self.password = secrets.token_urlsafe(16)

        r = requests.post(
            f"{MAIL_API}/accounts",
            json={"address": self.address, "password": self.password},
            timeout=30,
        )
        r.raise_for_status()

        r = requests.post(
            f"{MAIL_API}/token",
            json={"address": self.address, "password": self.password},
            timeout=30,
        )
        r.raise_for_status()
        self.headers = {"Authorization": f"Bearer {r.json()['token']}"}
        self.seen: set[str] = set()

    def wait_for(self, subject_needle: str, timeout: int = MAIL_POLL_TIMEOUT) -> Optional[dict]:
        """Poll until a not-yet-seen message whose subject matches arrives."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = requests.get(f"{MAIL_API}/messages", headers=self.headers, timeout=30)
            if r.ok:
                for msg in r.json().get("hydra:member", []):
                    if msg["id"] in self.seen:
                        continue
                    if subject_needle.lower() in msg.get("subject", "").lower():
                        self.seen.add(msg["id"])
                        full = requests.get(
                            f"{MAIL_API}/messages/{msg['id']}",
                            headers=self.headers,
                            timeout=30,
                        )
                        full.raise_for_status()
                        return full.json()
            time.sleep(MAIL_POLL_INTERVAL)
        return None

    @staticmethod
    def body(msg: dict) -> str:
        return (msg.get("text") or "") + " ".join(msg.get("html") or [])


def first_link(msg: dict, path_re: str) -> Optional[str]:
    m = re.search(rf'https?://[^\s"\'<>]*{path_re}[^\s"\'<>]*', Mailbox.body(msg))
    return m.group(0) if m else None


def run(base_url: str) -> int:
    base_url = base_url.rstrip("/")
    display_name = "Prod Email Check"
    password = secrets.token_urlsafe(16)

    section("Setup")
    r = requests.get(f"{base_url}/health", timeout=30)
    check(
        r.ok and r.json().get("status") == "healthy",
        "app is healthy",
        r.text.strip()[:80],
    )

    mb = Mailbox()
    print(f"  disposable inbox: {mb.address}", flush=True)

    s = requests.Session()

    section("1-2. Register and check the send banner")
    page = s.get(f"{base_url}/register", timeout=30)
    token = csrf_from(page.text)
    if not check(bool(token), "register page served a CSRF token"):
        return 1

    r = s.post(
        f"{base_url}/register",
        data={
            "csrf_token": token,
            "email": mb.address,
            "password": password,
            "display_name": display_name,
            "consent": "on",
        },
        allow_redirects=False,
        timeout=60,
    )
    location = r.headers.get("location", "")
    check(
        r.status_code == 303,
        "registration accepted",
        f"HTTP {r.status_code} -> {location or 'no redirect'}",
    )
    # ?send_failed=1 is the machine-readable form of the red banner.
    app_reported_failure = "send_failed=1" in location
    check(
        not app_reported_failure,
        "no send-failure redirect",
        location or "(none)",
    )

    if location:
        verify_page = s.get(f"{base_url}{location}", timeout=30)
        check(
            SEND_FAILED_NEEDLE not in verify_page.text,
            "no red send-failure banner on /verify-email",
        )

    section("3. Verification email arrives")
    msg = mb.wait_for("verify your email")
    if not check(
        msg is not None,
        "verification email received",
        f"subject: {msg['subject']}" if msg else f"nothing within {MAIL_POLL_TIMEOUT}s",
    ):
        if app_reported_failure:
            # The app knows the send failed. Each cause emits a distinct log
            # line, and nothing reachable from outside tells them apart --
            # is_email_configured() is only surfaced on /settings, which itself
            # requires a verified email. So read the log line.
            print(
                "\n  Diagnosis: the app itself reported the send failed.\n"
                "  Exactly one of these lines will be in the web service's Railway log,\n"
                "  and which one it is fully determines the fix:\n"
                "\n"
                "    'Failed to send verification to ...'\n"
                "        -> EMAIL_USE_API is NOT reaching this service, so the code took\n"
                "           the SMTP fallback, which Railway blocks. Fix the env var.\n"
                "    'Email not configured, skipping verification send'\n"
                "        -> SMTP fallback with no SMTP credentials either. Same fix.\n"
                "    'Brevo API key not configured'\n"
                "        -> EMAIL_USE_API arrived but BREVO_API_KEY did not.\n"
                "    'Brevo API error 401' + 'unrecognised IP address'\n"
                "        -> The key is fine. Brevo's authorised-IPs guard is blocking the\n"
                "           sending host. Allow the IP named in the log message at\n"
                "           https://app.brevo.com/security/authorised_ips -- and note that\n"
                "           Railway egress IPs can change, so consider turning the guard\n"
                "           off unless you have a static outbound IP.\n"
                "    'Brevo API error 401' (any other message)\n"
                "        -> Wrong credential: key came from the SMTP tab rather than\n"
                "           the API Keys tab.\n"
                "    'Brevo API error 400'\n"
                f"        -> Brevo rejected the payload, most likely {SENDER_HINT}\n"
                "           is not a verified sender on the account.\n"
                "\n"
                "  Note the first two mean the variables never landed on this service;\n"
                "  the last three mean they did and Brevo itself is refusing.",
                flush=True,
            )
        else:
            print(
                "\n  Diagnosis: the app reported a successful send but no mail arrived.\n"
                "  Brevo accepted the request and then dropped it -- check Brevo's own\n"
                "  transactional log, and the spam folder.",
                flush=True,
            )
        print(f"\n  Note: {mb.address} is left registered but unverified.", flush=True)
        return summarise()

    sender = (msg.get("from") or {}).get("address", "")
    check(bool(sender), "sender address present", sender)

    section("4. Verify link works and login succeeds")
    link = first_link(msg, r"/verify/")
    if not check(bool(link), "verification link found in email"):
        return summarise()

    # Assert on the redirect target, not the final page: this session is still
    # logged in from registration, so /login?verified=1 immediately bounces to
    # the dashboard and the confirmation text never renders.
    r = s.get(link, allow_redirects=False, timeout=30)
    destination = r.headers.get("location", "")
    check(
        "verified=1" in destination or "verified=already" in destination,
        "verification link marks the account verified",
        f"HTTP {r.status_code} -> {destination or '(no redirect)'}",
    )

    login_page = s.get(f"{base_url}/login", timeout=30)
    token = csrf_from(login_page.text)
    r = s.post(
        f"{base_url}/login",
        data={"csrf_token": token, "email": mb.address, "password": password},
        allow_redirects=False,
        timeout=30,
    )
    # A bounce to /verify-email is also a 303 away from /login, so exclude it
    # explicitly -- otherwise an unverified account would pass this check.
    destination = r.headers.get("location", "")
    logged_in = (
        r.status_code == 303
        and "login" not in destination
        and "verify-email" not in destination
    )
    check(
        logged_in,
        "login succeeds with no database intervention",
        f"HTTP {r.status_code} -> {destination or '(no redirect)'}",
    )

    section("6. Password reset email arrives")
    fp = s.get(f"{base_url}/forgot-password", timeout=30)
    token = csrf_from(fp.text)
    r = s.post(
        f"{base_url}/forgot-password",
        data={"csrf_token": token, "email": mb.address},
        timeout=60,
    )
    check(
        "we've sent a reset link" in r.text.lower() or "if an account exists" in r.text.lower(),
        "generic reset response shown (enumeration guard intact)",
    )

    # This is the load-bearing assertion for reset: the response above is
    # identical whether or not the send worked, so only arrival proves it.
    reset_msg = mb.wait_for("reset")
    check(
        reset_msg is not None,
        "password reset email received",
        f"subject: {reset_msg['subject']}" if reset_msg else f"nothing within {MAIL_POLL_TIMEOUT}s",
    )
    if reset_msg:
        check(bool(first_link(reset_msg, r"/reset-password/")), "reset link found in email")

    section("5. Admin audit log")
    admin_email = os.environ.get("RT_ADMIN_EMAIL")
    admin_password = os.environ.get("RT_ADMIN_PASSWORD")
    if not (admin_email and admin_password):
        print(
            "  SKIPPED -- set RT_ADMIN_EMAIL and RT_ADMIN_PASSWORD to include these checks.",
            flush=True,
        )
    else:
        a = requests.Session()
        page = a.get(f"{base_url}/login", timeout=30)
        r = a.post(
            f"{base_url}/login",
            data={
                "csrf_token": csrf_from(page.text),
                "email": admin_email,
                "password": admin_password,
            },
            allow_redirects=False,
            timeout=30,
        )
        destination = r.headers.get("location", "")
        admin_in = r.status_code == 303 and "login" not in destination
        check(
            admin_in,
            "admin login succeeded",
            f"HTTP {r.status_code} -> {destination or '(no redirect)'}",
        )

        log = a.get(
            f"{base_url}/admin/audit-log",
            params={"user_search": mb.address},
            timeout=30,
        )
        # Landing on /login also returns 200, so status alone proves nothing --
        # require a marker that only the real audit log page renders.
        on_audit_page = log.ok and "Admin: Audit Log" in log.text
        detail = f"HTTP {log.status_code}"
        if not on_audit_page:
            detail += " -- not the audit log page; admin login likely failed"
        if check(on_audit_page, "admin audit log reachable", detail):
            # Read event types from the table's badge cells only. Scanning the
            # whole body would also match the filter dropdown, which lists every
            # event type in the database regardless of the user_search filter --
            # that makes absence checks fire on unrelated historical events.
            badges = set(
                re.findall(r'<span class="badge event-badge">\s*([^<\s]+)\s*</span>', log.text)
            )
            print(f"  events for this account: {', '.join(sorted(badges)) or '(none)'}", flush=True)

            check("auth.verification_sent" in badges, "auth.verification_sent row present")
            check(
                "auth.verification_send_failed" not in badges,
                "no auth.verification_send_failed row",
            )
            check("password.reset_requested" in badges, "password.reset_requested row present")
            check(
                "password.reset_send_failed" not in badges,
                "no password.reset_send_failed row",
            )

    section("7. Cleanup")
    settings = s.get(f"{base_url}/settings", timeout=30)
    token = csrf_from(settings.text)
    if token:
        r = s.post(
            f"{base_url}/settings/delete-account",
            data={"csrf_token": token, "password": password},
            allow_redirects=False,
            timeout=30,
        )
        check(
            r.status_code in (200, 303),
            "throwaway account deleted via the app's own flow",
            f"HTTP {r.status_code}",
        )
    else:
        check(False, "could not load settings page for cleanup")

    return summarise()


def summarise() -> int:
    passed = sum(1 for ok, _, _ in results if ok)
    failed = [name for ok, name, _ in results if not ok]

    print(f"\n{'=' * 60}")
    print(f"RESULT: {passed}/{len(results)} checks passed")
    if failed:
        print("\nFailed:")
        for name in failed:
            print(f"  - {name}")
    print(f"{'=' * 60}", flush=True)
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    print(f"Target: {args.base_url}", flush=True)
    try:
        return run(args.base_url)
    except requests.RequestException as exc:
        print(f"\nNetwork error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
