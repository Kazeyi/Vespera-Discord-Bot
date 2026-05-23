"""
rate_guard.py — Vespera API Rate Guard
=======================================
SQLite-backed protection layer for all slash commands.

Features:
- Per-minute rate limiting with strike tracking
- Daily usage quotas per user per command
- Strike-based auto-ban: 5 strikes in 15 min → 24-hour ban
- Privacy-safe audit log (metadata only: timestamp, user_id, command)
- Automatic pruning: usage_log > 30 days deleted at startup; strike_log > 24h pruned
- Owner/whitelist bypass via BOT_OWNER_ID in .env
- Decorator factory: @rate_guard(command="subtitle", rpm=8, daily=250)
"""

import os
import time
import sqlite3
import asyncio
import functools
import logging
from datetime import datetime, timezone
from typing import Optional

import discord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_DB_FILE = os.path.abspath("rate_guard.db")
_OWNER_ID: Optional[str] = os.getenv("BOT_OWNER_ID")

# Strike window: 15 minutes (900 seconds)
_STRIKE_WINDOW_SECS = 900
# How many strikes in that window trigger a ban
_STRIKE_THRESHOLD = 5
# Ban duration in seconds (24 hours)
_BAN_DURATION_SECS = 86_400
# Retention: delete usage_log rows older than this many days
_LOG_RETENTION_DAYS = 30
_LOG_RETENTION_SECS = _LOG_RETENTION_DAYS * 86_400
# Retention: delete strike_log rows older than 48 hours (well past the 15-min window)
_STRIKE_RETENTION_SECS = 48 * 3600
# Retention: delete usage_quota rows older than 35 days (5 days grace after log window)
_QUOTA_RETENTION_DAYS = 35
_QUOTA_RETENTION_SECS = _QUOTA_RETENTION_DAYS * 86_400


# ---------------------------------------------------------------------------
# Database helpers (all synchronous — call via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_FILE, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_db() -> None:
    """Create all rate_guard tables if they don't exist."""
    conn = _get_conn()
    try:
        c = conn.cursor()

        # Append-only audit log — privacy-safe (no content)
        c.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       TEXT    NOT NULL,
                command       TEXT    NOT NULL,
                timestamp_unix REAL   NOT NULL
            )
        """)

        # Daily quota counters
        c.execute("""
            CREATE TABLE IF NOT EXISTS usage_quota (
                user_id  TEXT NOT NULL,
                command  TEXT NOT NULL,
                date_utc TEXT NOT NULL,
                count    INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, command, date_utc)
            )
        """)

        # Per-minute violation events (strikes)
        c.execute("""
            CREATE TABLE IF NOT EXISTS strike_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       TEXT NOT NULL,
                command       TEXT NOT NULL,
                timestamp_unix REAL NOT NULL
            )
        """)

        # Active bans
        c.execute("""
            CREATE TABLE IF NOT EXISTS ban_list (
                user_id          TEXT PRIMARY KEY,
                banned_until_unix REAL NOT NULL,
                reason           TEXT NOT NULL,
                strike_count     INTEGER DEFAULT 0,
                banned_at_unix   REAL NOT NULL
            )
        """)

        # Whitelist (permanent bypass for trusted users)
        c.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                user_id TEXT PRIMARY KEY,
                added_at_unix REAL NOT NULL
            )
        """)

        # Index for fast time-window queries
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_strike_user_time
            ON strike_log (user_id, timestamp_unix)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_log_time
            ON usage_log (timestamp_unix)
        """)

        conn.commit()
        logger.info("✅ rate_guard.db initialized")

        # Prune stale records on every startup
        _prune_old_records(conn)
    finally:
        conn.close()


def _prune_old_records(conn: sqlite3.Connection) -> None:
    """
    Delete stale rows to keep rate_guard.db small.
    Called at startup and exposed for periodic scheduled calls.

    Retention policy:
      - usage_log:   30 days
      - strike_log:  48 hours (well outside the 15-min abuse window)
      - usage_quota: 35 days  (5-day grace window after log retention)
    """
    cutoff_log    = time.time() - _LOG_RETENTION_SECS
    cutoff_strike = time.time() - _STRIKE_RETENTION_SECS
    cutoff_quota  = time.time() - _QUOTA_RETENTION_SECS

    # Convert quota cutoff to date string for the date_utc column
    from datetime import datetime, timezone as _tz
    cutoff_quota_date = datetime.fromtimestamp(cutoff_quota, tz=_tz.utc).strftime("%Y-%m-%d")

    deleted_log    = conn.execute("DELETE FROM usage_log   WHERE timestamp_unix < ?",  (cutoff_log,)).rowcount
    deleted_strike = conn.execute("DELETE FROM strike_log  WHERE timestamp_unix < ?",  (cutoff_strike,)).rowcount
    deleted_quota  = conn.execute("DELETE FROM usage_quota WHERE date_utc < ?",         (cutoff_quota_date,)).rowcount
    conn.commit()

    if deleted_log + deleted_strike + deleted_quota > 0:
        logger.info(
            f"🧹 rate_guard.db pruned: "
            f"{deleted_log} log rows, {deleted_strike} strike rows, {deleted_quota} quota rows removed"
        )


# ---------------------------------------------------------------------------
# Core check logic (synchronous — runs in thread)
# ---------------------------------------------------------------------------

class _CheckResult:
    """Outcome of a rate-guard check."""
    __slots__ = ("allowed", "reason", "retry_after")

    def __init__(self, allowed: bool, reason: str = "", retry_after: int = 0):
        self.allowed = allowed
        self.reason = reason
        self.retry_after = retry_after


def _is_banned(conn: sqlite3.Connection, user_id: str) -> Optional[float]:
    """Return ban expiry timestamp if user is banned, else None."""
    now = time.time()
    row = conn.execute(
        "SELECT banned_until_unix FROM ban_list WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    if row is None:
        return None
    if row[0] <= now:
        # Expired — clean up
        conn.execute("DELETE FROM ban_list WHERE user_id = ?", (user_id,))
        conn.commit()
        return None
    return row[0]


def _is_whitelisted(conn: sqlite3.Connection, user_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM whitelist WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row is not None


def _count_recent_calls(conn: sqlite3.Connection, user_id: str, command: str, window_secs: int) -> int:
    """Count usage_log rows for user+command in the last `window_secs` seconds."""
    cutoff = time.time() - window_secs
    row = conn.execute(
        """SELECT COUNT(*) FROM usage_log
           WHERE user_id = ? AND command = ? AND timestamp_unix > ?""",
        (user_id, command, cutoff)
    ).fetchone()
    return row[0] if row else 0


def _get_daily_count(conn: sqlite3.Connection, user_id: str, command: str) -> int:
    date_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT count FROM usage_quota WHERE user_id = ? AND command = ? AND date_utc = ?",
        (user_id, command, date_utc)
    ).fetchone()
    return row[0] if row else 0


def _increment_daily_count(conn: sqlite3.Connection, user_id: str, command: str) -> None:
    date_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn.execute(
        """INSERT INTO usage_quota (user_id, command, date_utc, count)
           VALUES (?, ?, ?, 1)
           ON CONFLICT(user_id, command, date_utc) DO UPDATE SET count = count + 1""",
        (user_id, command, date_utc)
    )


def _log_call(conn: sqlite3.Connection, user_id: str, command: str) -> None:
    conn.execute(
        "INSERT INTO usage_log (user_id, command, timestamp_unix) VALUES (?, ?, ?)",
        (user_id, command, time.time())
    )


def _add_strike(conn: sqlite3.Connection, user_id: str, command: str) -> int:
    """Add a strike and return total strikes in the last 15-minute window."""
    now = time.time()
    conn.execute(
        "INSERT INTO strike_log (user_id, command, timestamp_unix) VALUES (?, ?, ?)",
        (user_id, command, now)
    )
    cutoff = now - _STRIKE_WINDOW_SECS
    row = conn.execute(
        "SELECT COUNT(*) FROM strike_log WHERE user_id = ? AND timestamp_unix > ?",
        (user_id, cutoff)
    ).fetchone()
    return row[0] if row else 1


def _apply_auto_ban(conn: sqlite3.Connection, user_id: str, strike_count: int) -> None:
    banned_until = time.time() + _BAN_DURATION_SECS
    conn.execute(
        """INSERT INTO ban_list (user_id, banned_until_unix, reason, strike_count, banned_at_unix)
           VALUES (?, ?, 'auto-ban: repeated rate-limit violations', ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET
               banned_until_unix = excluded.banned_until_unix,
               reason = excluded.reason,
               strike_count = excluded.strike_count,
               banned_at_unix = excluded.banned_at_unix""",
        (user_id, banned_until, strike_count, time.time())
    )


def _perform_check(user_id: str, command: str, rpm: int, daily: int) -> _CheckResult:
    """
    Full synchronous check. Run via asyncio.to_thread().

    Order:
    1. Ban check
    2. RPM check  → strike on violation → auto-ban if strike threshold hit
    3. Daily quota check
    4. Log the call + increment quota
    """
    conn = _get_conn()
    try:
        # 1. Ban check
        ban_expiry = _is_banned(conn, user_id)
        if ban_expiry is not None:
            secs_left = int(ban_expiry - time.time())
            hours = secs_left // 3600
            mins = (secs_left % 3600) // 60
            return _CheckResult(
                allowed=False,
                reason=(
                    f"🚫 You are temporarily banned from using Vespera for **{hours}h {mins}m** "
                    f"due to repeated rapid-fire requests.\n"
                    f"The ban lifts automatically. Please be patient."
                )
            )

        # 2. RPM check (60-second window)
        recent = _count_recent_calls(conn, user_id, command, window_secs=60)
        if recent >= rpm:
            # Add a strike
            strikes = _add_strike(conn, user_id, command)
            conn.commit()

            if strikes >= _STRIKE_THRESHOLD:
                _apply_auto_ban(conn, user_id, strikes)
                conn.commit()
                return _CheckResult(
                    allowed=False,
                    reason=(
                        f"🚫 You've been automatically banned for **24 hours** "
                        f"after repeatedly hitting the rate limit.\n"
                        f"This is a safety measure to protect the bot's API budget."
                    )
                )

            remaining_strikes = _STRIKE_THRESHOLD - strikes
            return _CheckResult(
                allowed=False,
                reason=(
                    f"⏱️ You're going too fast! `/{command}` allows **{rpm} uses/minute**.\n"
                    f"Please wait a moment before trying again.\n"
                    f"-# ⚠️ Strike {strikes}/{_STRIKE_THRESHOLD} — "
                    f"{remaining_strikes} more in 15 min triggers a 24h auto-ban."
                ),
                retry_after=60
            )

        # 3. Daily quota check (0 = unlimited)
        if daily > 0:
            used = _get_daily_count(conn, user_id, command)
            if used >= daily:
                return _CheckResult(
                    allowed=False,
                    reason=(
                        f"📊 You've reached your daily limit of **{daily} uses** for `/{command}`.\n"
                        f"Vespera's API budget is finite — your limit resets at midnight UTC.\n"
                        f"Thank you for understanding! 🌙"
                    )
                )

        # 4. Approved — log call and increment quota
        _log_call(conn, user_id, command)
        if daily > 0:
            _increment_daily_count(conn, user_id, command)
        conn.commit()

        return _CheckResult(allowed=True)

    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Initialise DB at import time (non-blocking, sync is fine here)
_init_db()


def rate_guard(command: str, rpm: int, daily: int = 0):
    """
    Decorator factory for discord app_commands methods.

    Usage:
        @dnd_session.command(name="do", ...)
        @rate_guard(command="dnd_session_do", rpm=10, daily=100)
        async def do_action(self, interaction, ...):
            ...

    Args:
        command: Logical command name used in DB (snake_case, unique per command)
        rpm:     Maximum calls per minute per user
        daily:   Maximum calls per UTC day per user (0 = unlimited)
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract interaction — first positional arg after self for Cog methods,
            # or first positional for standalone commands
            interaction: Optional[discord.Interaction] = None
            for arg in args:
                if isinstance(arg, discord.Interaction):
                    interaction = arg
                    break

            if interaction is None:
                # Fallback: just run the command (shouldn't happen)
                return await func(*args, **kwargs)

            user_id = str(interaction.user.id)

            # --- Owner bypass ---
            if _OWNER_ID and user_id == _OWNER_ID:
                return await func(*args, **kwargs)

            # --- Whitelist bypass (checked in-thread) ---
            def _wl_check():
                conn = _get_conn()
                try:
                    return _is_whitelisted(conn, user_id)
                finally:
                    conn.close()

            if await asyncio.to_thread(_wl_check):
                return await func(*args, **kwargs)

            # --- Full check ---
            result: _CheckResult = await asyncio.to_thread(
                _perform_check, user_id, command, rpm, daily
            )

            if not result.allowed:
                try:
                    await interaction.response.send_message(
                        result.reason, ephemeral=True
                    )
                except discord.errors.InteractionResponded:
                    try:
                        await interaction.followup.send(result.reason, ephemeral=True)
                    except Exception:
                        pass
                except Exception:
                    pass
                return  # Do NOT run the original command

            return await func(*args, **kwargs)

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Admin utility functions (called by cogs/guard.py)
# ---------------------------------------------------------------------------

def admin_get_stats() -> dict:
    """Return a snapshot of today's usage for the /guard stats command."""
    conn = _get_conn()
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now = time.time()

        # Total calls today
        total_today = conn.execute(
            "SELECT COUNT(*) FROM usage_log WHERE timestamp_unix > ?",
            (now - 86400,)
        ).fetchone()[0]

        # Top 5 users by volume today
        top_users = conn.execute(
            """SELECT user_id, COUNT(*) as calls
               FROM usage_log
               WHERE timestamp_unix > ?
               GROUP BY user_id
               ORDER BY calls DESC
               LIMIT 5""",
            (now - 86400,)
        ).fetchall()

        # Active bans
        active_bans = conn.execute(
            "SELECT user_id, banned_until_unix, reason, strike_count FROM ban_list WHERE banned_until_unix > ?",
            (now,)
        ).fetchall()

        # Recent strikes (last hour)
        recent_strikes = conn.execute(
            """SELECT user_id, COUNT(*) as strikes
               FROM strike_log
               WHERE timestamp_unix > ?
               GROUP BY user_id
               ORDER BY strikes DESC
               LIMIT 5""",
            (now - 3600,)
        ).fetchall()

        return {
            "total_today": total_today,
            "top_users": top_users,
            "active_bans": active_bans,
            "recent_strikes": recent_strikes,
        }
    finally:
        conn.close()


def admin_ban(user_id: str, hours: int = 24, reason: str = "manual ban by owner") -> None:
    conn = _get_conn()
    try:
        banned_until = time.time() + (hours * 3600)
        conn.execute(
            """INSERT INTO ban_list (user_id, banned_until_unix, reason, strike_count, banned_at_unix)
               VALUES (?, ?, ?, 0, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   banned_until_unix = excluded.banned_until_unix,
                   reason = excluded.reason,
                   banned_at_unix = excluded.banned_at_unix""",
            (user_id, banned_until, reason, time.time())
        )
        conn.commit()
    finally:
        conn.close()


def admin_unban(user_id: str) -> bool:
    """Returns True if a ban was removed."""
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM ban_list WHERE user_id = ?", (user_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def admin_whitelist(user_id: str) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO whitelist (user_id, added_at_unix) VALUES (?, ?)",
            (user_id, time.time())
        )
        conn.commit()
    finally:
        conn.close()


def admin_un_whitelist(user_id: str) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM whitelist WHERE user_id = ?", (user_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def admin_clear_strikes(user_id: str) -> None:
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM strike_log WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
