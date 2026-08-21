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
