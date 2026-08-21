"""
Resolve the configured list into named, typed instruments.

Names come from JPX's own listed-issues workbook. They are never guessed and
never taken from a model's memory — that is the whole reason this module
exists rather than a dict of hand-typed names. A code that cannot be resolved
is reported unresolved, not filled in with a plausible guess.
"""

import os
import sys

import pandas as pd

import common
import config

try:
    import tomllib
except ModuleNotFoundError:                          # pragma: no cover
    raise SystemExit("Python 3.11+ required (tomllib).")


# JPX publishes the workbook with Japanese column headers.
COL_CODE = "コード"
COL_NAME = "銘柄名"
COL_SEGMENT = "市場・商品区分"


def load_config(path=None):
    """Read universe.toml into a flat list of instruments, order preserved."""
    path = path or config.UNIVERSE_FILE
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    items = []
    for kind in ("equity", "etf"):
        for entry in raw.get(kind, []):
            code = str(entry["code"]).strip()
            if not code:
                raise ValueError(f"empty code in [{kind}] block")
            items.append({
                "code": code,
                "asset_type": "Equity" if kind == "equity" else "ETF",
                "held": bool(entry.get("held", False)),
                "fx": entry.get("fx"),
                "note": entry.get("note", ""),
            })

    seen = [i["code"] for i in items]
    dupes = {c for c in seen if seen.count(c) > 1}
    if dupes:
        raise ValueError(f"duplicate codes in {path}: {sorted(dupes)}")
    return items


def corrections(path=None):
    """
    Corporate actions the feed got wrong, as declared by a human.

    Returns {code: {"splits": [...], "bad_prints": [...]}}. These are applied
    explicitly and recorded in the run, never inferred.
    """
    path = path or config.UNIVERSE_FILE
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    out = {}
    for entry in raw.get("split", []):
        code = str(entry["code"])
        out.setdefault(code, {"splits": [], "bad_prints": []})
        out[code]["splits"].append({
            "date": str(entry["date"]), "ratio": float(entry["ratio"]),
            "note": entry.get("note", ""),
        })
    for entry in raw.get("bad_print", []):
        code = str(entry["code"])
        out.setdefault(code, {"splits": [], "bad_prints": []})
        out[code]["bad_prints"].append({
            "date": str(entry["date"]), "note": entry.get("note", ""),
        })
    return out


def concerns(path=None):
    """
    Severe events declared by hand, verified against the issuer's own
    disclosure. Returns {code: [{"type": ..., "date": ..., "note": ...}]}.

    These cannot be computed from a price feed — a restatement or an auditor
    change lives in a filing. Declaring one is a deliberate act, and the run
    records it alongside the computed triggers rather than blending them.
    """
    path = path or config.UNIVERSE_FILE
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    out = {}
    for entry in raw.get("concern", []):
        kind = str(entry["type"])
        known = set(config.HEALTH_SEVERE_TRIGGERS) | set(config.HEALTH_BROKEN_TRIGGERS)
        if kind not in known:
            raise ValueError(
                f"unknown concern type {kind!r} for {entry['code']}. "
                f"Known types: {sorted(known)}"
            )
        out.setdefault(str(entry["code"]), []).append({
            "type": kind,
            "date": str(entry.get("date", "")),
            "note": entry.get("note", ""),
        })
    return out


ASSUMPTION_FIELDS = {"reference_pe"}


def assumptions(path=None):
    """
    Declared theses that adjust scoring, from universe.toml.

    Returns {code: {field: {"value", "date", "note"}}}. Unknown fields are an
    error, not a silent no-op — a mistyped assumption that does nothing is
    worse than one that crashes.
    """
    path = path or config.UNIVERSE_FILE
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    out = {}
    for entry in raw.get("assumption", []):
        field = str(entry["field"])
        if field not in ASSUMPTION_FIELDS:
            raise ValueError(f"unknown assumption field {field!r} for "
                             f"{entry['code']}; known: {sorted(ASSUMPTION_FIELDS)}")
        out.setdefault(str(entry["code"]), {})[field] = {
            "value": float(entry["value"]),
            "date": str(entry.get("date", "")),
            "note": entry.get("note", ""),
        }
    return out


def nav_verifications(path=None):
    """
    Feed fields verified wrong by hand. {code: {...}}.

    NAV moves daily, so this is not an ongoing correction — it is proof, as
    of one moment, that the feed's navPrice cannot be trusted for this name.
    It silences the premium/discount flag rather than computing a "corrected"
    figure that would itself be stale within days.
    """
    path = path or config.UNIVERSE_FILE
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    out = {}
    for entry in raw.get("nav_verification", []):
        out[str(entry["code"])] = {
            "verified_nav": float(entry["verified_nav"]),
            "verified_at": str(entry["verified_at"]),
            "source": entry.get("source", ""),
            "note": entry.get("note", ""),
        }
    return out


def _jpx_table():
    """Fetch and cache JPX's listed-issues workbook as {code: (name, segment)}."""
    cached = common.cache_get("jpx_listed", ttl_hours=24 * 7)
    if cached:
        return cached

    def fetch():
        frame = pd.read_excel(config.JPX_LISTED_ISSUES_URL, dtype=str)
        missing = {COL_CODE, COL_NAME} - set(frame.columns)
        if missing:
            raise common.DataFeedError(
                f"JPX workbook is missing expected columns {missing}. "
                f"The published format may have changed."
            )
        return frame

    frame = common.with_retry(fetch)
    if frame.empty:
        raise common.DataFeedError("JPX workbook downloaded empty")

    table = {
        str(row[COL_CODE]).strip(): {
            "name": str(row[COL_NAME]).strip(),
            "segment": str(row.get(COL_SEGMENT, "")).strip(),
        }
        for _, row in frame.iterrows()
        if pd.notna(row[COL_CODE])
    }
    common.cache_put("jpx_listed", table)
    return table


def _sibling_names():
    """
    Fall back to the sibling screener's cache for a display name.

    Read-only, and optional: the sibling may not be present. It covers Prime
    equities only, so no ETF will be found here.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                        config.SIBLING_INFO_CACHE)
    if not os.path.exists(path):
        return {}
    try:
        blob = common.load_json(path)
    except Exception:                                # noqa: BLE001 - optional
        return {}
    out = {}
    for symbol, entry in blob.items():
        data = entry.get("data", entry) if isinstance(entry, dict) else {}
        name = data.get("longName") or data.get("shortName")
        if name:
            out[symbol.removesuffix(".T")] = name
    return out


def _english_names(codes):
    """
    English display names from the price feed, cached.

    The sibling cache covers Prime equities only, so every ETF arrives here
    without one. This is still a lookup against a data source, not a name
    typed from memory — and a failure just leaves the JPX name in place.
    """
    cached = common.cache_get("names_en", ttl_hours=24 * 30) or {}
    missing = [c for c in codes if c not in cached]
    if not missing:
        return cached

    import yfinance as yf
    throttle = common.Throttle(config.REQUEST_DELAY_SECONDS)
    for code in missing:
        throttle.wait()
        try:
            info = yf.Ticker(common.yahoo_symbol(code)).info
            cached[code] = info.get("longName") or info.get("shortName") or None
        except Exception:                            # noqa: BLE001 - optional
            cached[code] = None
    common.cache_put("names_en", cached)
    return cached


def resolve(items=None):
    """Attach name and segment to each instrument. Unresolved stays unresolved."""
    items = items if items is not None else load_config()
    jpx = _jpx_table()
    sibling = _sibling_names()

    for item in items:
        code = item["code"]
        hit = jpx.get(code)
        if hit:
            item["name"] = hit["name"]
            item["segment"] = hit["segment"]
            item["name_source"] = "jpx"
        elif code in sibling:
            item["name"] = sibling[code]
            item["segment"] = ""
            item["name_source"] = "sibling-cache"
        else:
            item["name"] = None
            item["segment"] = ""
            item["name_source"] = "unresolved"

        # JPX names are Japanese, which is authoritative but not readable in an
        # English report. An English name is display sugar only: it never
        # replaces the JPX name and its absence is never an error.
        item["name_en"] = sibling.get(code)

    unnamed = [i["code"] for i in items if not i.get("name_en")]
    if unnamed:
        found = _english_names(unnamed)
        for item in items:
            if not item.get("name_en"):
                item["name_en"] = found.get(item["code"])
    return items


def display_name(item):
    """English where we have it, JPX's own name where we do not."""
    return item.get("name_en") or item.get("name") or "(unresolved)"


def main(argv=None):
    items = resolve()
    width = max(len(display_name(i)) for i in items)
    print(f"{'CODE':<6} {'TYPE':<7} {'HELD':<5} {'NAME':<{width}}  SOURCE")
    for i in items:
        print(f"{i['code']:<6} {i['asset_type']:<7} "
              f"{'yes' if i['held'] else 'no':<5} "
              f"{display_name(i):<{width}}  {i['name_source']}")

    unresolved = [i["code"] for i in items if i["name_source"] == "unresolved"]
    print(f"\n{len(items)} instruments · {len(unresolved)} unresolved")
    if unresolved:
        print(f"unresolved: {', '.join(unresolved)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
