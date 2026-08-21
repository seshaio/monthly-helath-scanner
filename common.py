"""
Plumbing: run folders, caching, polite fetching, JSON that survives pandas.

Kept deliberately small. Anything that encodes a judgement belongs in
config.py, and anything that computes a finding belongs in monitor/.
"""

import json
import math
import os
import random
import re
import threading
import time
from datetime import datetime, timezone

import config


class DataFeedError(RuntimeError):
    """
    The upstream feed failed.

    Deliberately distinct from a name failing a test. A throttled or empty
    feed must stop the run — it must never be allowed to look like a finding.
    A missing price is not a cheap stock.
    """


# --------------------------------------------------------------------------
# Polite fetching
# --------------------------------------------------------------------------

class Throttle:
    """Spaces out request starts across threads. Holding the lock across the
    sleep is intentional — serialising the starts is the entire point."""

    def __init__(self, delay):
        self.delay = delay
        self._lock = threading.Lock()
        self._next_at = 0.0

    def wait(self):
        if self.delay <= 0:
            return
        with self._lock:
            now = time.monotonic()
            if now < self._next_at:
                time.sleep(self._next_at - now)
                now = time.monotonic()
            self._next_at = now + self.delay


def with_retry(fn, *, retries=None, backoff=None):
    """Call fn, retrying with exponential backoff and jitter."""
    retries = config.MAX_RETRIES if retries is None else retries
    backoff = config.RETRY_BACKOFF_SECONDS if backoff is None else backoff
    last = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as exc:                    # noqa: BLE001 - re-raised
            last = exc
            if attempt == retries:
                break
            time.sleep(backoff * (2 ** attempt) * (0.5 + random.random()))
    raise last


# --------------------------------------------------------------------------
# Tickers
# --------------------------------------------------------------------------

def yahoo_symbol(code):
    """TSE code -> Yahoo symbol. '7203' -> '7203.T'."""
    return f"{code}.T"


# --------------------------------------------------------------------------
# Run folders — same convention as the sibling screener
# --------------------------------------------------------------------------

def run_dir(date=None, create=True):
    """
    Allocate output/YYYY-MM-DD-run-N/ and point output/latest at it.

    The counter increments within a day so nothing is ever overwritten.
    Comparing two runs is the only way to see what a threshold change did.
    """
    date = date or datetime.now().strftime("%Y-%m-%d")
    base = os.path.abspath(config.OUTPUT_DIR)
    if not create:
        existing = sorted(_runs_for(base, date))
        return existing[-1] if existing else None

    os.makedirs(base, exist_ok=True)
    n = len(_runs_for(base, date)) + 1
    path = os.path.join(base, f"{date}-run-{n}")
    os.makedirs(path, exist_ok=True)

    link = os.path.join(base, "latest")
    tmp = link + ".tmp"
    if os.path.islink(tmp) or os.path.exists(tmp):
        os.remove(tmp)
    os.symlink(path, tmp)
    os.replace(tmp, link)
    return path


def _runs_for(base, date):
    if not os.path.isdir(base):
        return []
    pat = re.compile(rf"^{re.escape(date)}-run-(\d+)$")
    return [os.path.join(base, d) for d in os.listdir(base) if pat.match(d)]


def latest_run():
    """Path of the most recent run, or None. Follows output/latest."""
    link = os.path.join(os.path.abspath(config.OUTPUT_DIR), "latest")
    return os.path.realpath(link) if os.path.islink(link) else None


def previous_run(before):
    """The run immediately preceding `before`, for month-over-month diffing."""
    base = os.path.abspath(config.OUTPUT_DIR)
    if not os.path.isdir(base):
        return None
    runs = sorted(
        os.path.join(base, d) for d in os.listdir(base)
        if re.match(r"^\d{4}-\d{2}-\d{2}-run-\d+$", d)
    )
    before = os.path.realpath(before)
    earlier = [r for r in runs if os.path.realpath(r) < before]
    return earlier[-1] if earlier else None


# --------------------------------------------------------------------------
# JSON
# --------------------------------------------------------------------------

def _plain(obj):
    """
    Make numpy/pandas scalars and NaN JSON-safe.

    NaN becomes null rather than the bare `NaN` token json.dump would emit,
    which is not valid JSON and which every downstream reader chokes on.
    """
    if obj is None:
        return None
    if isinstance(obj, float):
        return None if math.isnan(obj) or math.isinf(obj) else obj
    if hasattr(obj, "item"):                # numpy scalar
        return _plain(obj.item())
    if hasattr(obj, "isoformat"):           # datetime / Timestamp
        return obj.isoformat()
    if isinstance(obj, dict):
        # Keys beginning with _ carry working state (raw pandas series) that
        # must never reach a run file.
        return {str(k): _plain(v) for k, v in obj.items()
                if not str(k).startswith("_")}
    if isinstance(obj, (list, tuple, set)):
        return [_plain(v) for v in obj]
    return obj


def save_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(_plain(data), fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


def load_json(path):
    with open(path) as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------

def cache_get(name, ttl_hours=None):
    """Return cached payload if fresh, else None. Safe to delete the folder."""
    ttl = config.CACHE_TTL_HOURS if ttl_hours is None else ttl_hours
    path = os.path.join(config.CACHE_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None
    try:
        blob = load_json(path)
        stamped = datetime.fromisoformat(blob["fetched_at"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
    age = (datetime.now(timezone.utc) - stamped).total_seconds() / 3600
    return blob["data"] if age < ttl else None


def cache_put(name, data):
    save_json(
        os.path.join(config.CACHE_DIR, f"{name}.json"),
        {"fetched_at": datetime.now(timezone.utc).isoformat(), "data": data},
    )


def utc_now():
    return datetime.now(timezone.utc).isoformat()
