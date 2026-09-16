#!/usr/bin/env python3
"""Watch macOS Messages for delivery codes and push them to the display.

The phone forwards SMS to the Mac (Settings -> Messages -> Text Message
Forwarding). This reads the resulting SQLite store, decides what counts
as a displayable code, and PATCHes it to the API the ESP32 polls.

Standard library only, so it runs under launchd with no virtualenv.

  python3 otp_watcher.py

Configuration comes from the environment or a .env beside this file:

  DOORDROP_API   API base URL
  OTP_TOKEN      bearer token, must match the server's
  POLL_SECONDS   default 5
  CODE_TTL_SEC   how long a code stays on screen, default 300
  DELIVERY_ONLY  "0" to accept any sender, default on
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from extract import extract

MESSAGES_DB = Path.home() / "Library/Messages/chat.db"


def _env(key: str, default: str = "") -> str:
    env_file = Path(__file__).parent / ".env"
    if env_file.exists() and not os.environ.get(key):
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{key}="):
                os.environ[key] = line.split("=", 1)[1].strip()
    return os.environ.get(key, default)


API_BASE = _env("DOORDROP_API", "http://localhost:3000")
OTP_TOKEN = _env("OTP_TOKEN", "")
POLL_SECONDS = int(_env("POLL_SECONDS", "5"))
CODE_TTL_SEC = int(_env("CODE_TTL_SEC", "300"))
DELIVERY_ONLY = _env("DELIVERY_ONLY", "1") != "0"


def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def push(code: str, label: str) -> None:
    """Send a code to the display, with the expiry the firmware enforces."""
    if not OTP_TOKEN:
        log("OTP_TOKEN unset, refusing to push")
        return

    payload = json.dumps(
        {"otp": code, "label": label, "expires_at": int(time.time()) + CODE_TTL_SEC}
    ).encode()

    request = urllib.request.Request(
        f"{API_BASE}/api/otp/latest",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OTP_TOKEN}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            log(f"pushed {label} -> HTTP {response.status}")
    except urllib.error.HTTPError as err:
        log(f"push rejected: HTTP {err.code}")
    except OSError as err:
        log(f"push failed: {err}")


def _snapshot() -> Path:
    """Copy the store before reading it — Messages.app holds a lock."""
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    destination = Path(path)
    shutil.copy2(MESSAGES_DB, destination)
    return destination


def _query(sql: str, args: tuple = ()) -> list[tuple]:
    snapshot = _snapshot()
    try:
        connection = sqlite3.connect(f"file:{snapshot}?mode=ro&immutable=1", uri=True)
        try:
            return connection.execute(sql, args).fetchall()
        finally:
            connection.close()
    finally:
        snapshot.unlink(missing_ok=True)


def messages_after(rowid: int) -> list[tuple[int, str, str]]:
    return _query(
        """
        SELECT m.ROWID, m.text, h.id
          FROM message m
          JOIN handle h ON m.handle_id = h.ROWID
         WHERE m.ROWID > ?
           AND m.is_from_me = 0
           AND m.text IS NOT NULL
         ORDER BY m.ROWID ASC
        """,
        (rowid,),
    )


def latest_rowid() -> int:
    rows = _query("SELECT MAX(ROWID) FROM message")
    return (rows[0][0] if rows else 0) or 0


def main() -> int:
    if not MESSAGES_DB.exists():
        log(f"no Messages store at {MESSAGES_DB}")
        log("enable iPhone -> Settings -> Messages -> Text Message Forwarding")
        return 1

    if not OTP_TOKEN:
        log("OTP_TOKEN unset; codes will be detected but not pushed")

    # Start from the current tail. Replaying the backlog on every restart
    # would put a code from last Tuesday on the door.
    cursor = latest_rowid()
    log(f"watching from ROWID {cursor}, every {POLL_SECONDS}s -> {API_BASE}")
    log(f"delivery_only={DELIVERY_ONLY} ttl={CODE_TTL_SEC}s")

    last_pushed = ""

    while True:
        try:
            for rowid, text, handle in messages_after(cursor):
                cursor = max(cursor, rowid)
                result = extract(text, handle, delivery_only=DELIVERY_ONLY)

                if not result.displayable:
                    # Log the decision, never the message. This runs on a
                    # machine that sees every SMS the phone receives.
                    log(f"skip ({result.reason})")
                    continue

                if result.code == last_pushed:
                    continue

                log(f"code from {result.label}")
                push(result.code, result.label)
                last_pushed = result.code

        except sqlite3.Error as err:
            log(f"database error: {err}")
        except Exception as err:  # keep the loop alive; it runs unattended
            log(f"unexpected: {type(err).__name__}: {err}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
