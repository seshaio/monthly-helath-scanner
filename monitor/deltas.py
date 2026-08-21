"""
Month-over-month deltas: what changed, and why.

A monthly review's entire value is the difference from last month. Every run
saves verdicts.json; this module diffs the current run against the previous
one and, for any verdict that moved, names which component moved it — health,
valuation, trend, or structure. A verdict change with no cause on record is a
bug, not a finding.
"""

import os

import common


def load_previous(current_run_dir):
    """The most recent earlier run that saved verdicts. None on the first."""
    prev = common.previous_run(current_run_dir)
    while prev:
        path = os.path.join(prev, "verdicts.json")
        if os.path.exists(path):
            return common.load_json(path), os.path.basename(prev)
        prev = common.previous_run(prev)
    return None, None


COMPONENTS = ("health_status", "valuation_score", "structural_score",
              "trend_score")


def compare(current, previous):
    """
    {code: delta} for every code in the current run.

    A delta is None for a name with no prior record; otherwise it says
    whether the verdict moved and which components moved with it.
    """
    out = {}
    for code, now in current.items():
        before = (previous or {}).get(code)
        if before is None:
            out[code] = {"new": True}
            continue
        causes = [
            {"component": key, "from": before.get(key), "to": now.get(key)}
            for key in COMPONENTS
            if before.get(key) != now.get(key)
            and not (before.get(key) is None and now.get(key) is None)
        ]
        out[code] = {
            "new": False,
            "verdict_changed": before.get("verdict") != now.get("verdict"),
            "previous_verdict": before.get("verdict"),
            "previous_score": before.get("score"),
            "score_change": (now.get("score") - before.get("score")
                             if now.get("score") is not None
                             and before.get("score") is not None else None),
            "causes": causes,
        }
    return out
