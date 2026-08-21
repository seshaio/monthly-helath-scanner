"""
The agreement matrix: where reviewers agree, accept; where they disagree,
that is the month's reading list.

Verdicts are never averaged. The mean of KEEP and SELL is not a verdict, it
is the destruction of the one signal a panel adds — a specific, articulate
dissent. The mechanical verdict sits in the matrix as one more column, with
no special weight.
"""

import os
import sys

import common
from monitor import universe as universe_mod


def load_panel(run_dir):
    """{model_name: {code: review}} for every ingested reply, plus mechanical."""
    panel = {}
    reviews_dir = os.path.join(run_dir, "reviews")
    if os.path.isdir(reviews_dir):
        for name in sorted(os.listdir(reviews_dir)):
            if name.endswith(".json"):
                blob = common.load_json(os.path.join(reviews_dir, name))
                panel[blob["model"]] = blob["reviews"]

    verdicts_path = os.path.join(run_dir, "verdicts.json")
    if os.path.exists(verdicts_path):
        saved = common.load_json(verdicts_path)
        panel["mechanical"] = {
            code: {"verdict": rec.get("verdict"), "rationale": "threshold output"}
            for code, rec in saved.items()
            # An unscored name ("—") is an absence, not a vote — putting it
            # in the matrix made every incomplete row read as a disagreement.
            if not code.startswith("_") and rec.get("verdict")
            and rec["verdict"] != "—"}
    return panel


def matrix(panel):
    """Per-code verdict spread across the panel."""
    codes = sorted({code for reviews in panel.values() for code in reviews})
    out = {}
    for code in codes:
        votes = {model: reviews[code]["verdict"]
                 for model, reviews in panel.items() if code in reviews}
        distinct = set(votes.values())
        out[code] = {
            "votes": votes,
            "unanimous": len(distinct) == 1,
            "spread": sorted(distinct),
            "dissents": [
                {"model": model, "verdict": v,
                 "rationale": panel[model][code].get("rationale", "")}
                for model, v in votes.items()
                if sum(1 for x in votes.values() if x == v) == 1
                and len(votes) > 2],
        }
    return out


def render(agreement, panel_names):
    out = [f"# Panel consensus — {len(panel_names)} reviewers "
           f"({', '.join(panel_names)})", ""]
    split = {c: a for c, a in agreement.items() if not a["unanimous"]}
    out.append(f"Unanimous on {len(agreement) - len(split)} of "
               f"{len(agreement)} names.")
    out.append("")
    if split:
        out.append("## Disagreements — this month's reading list")
        out.append("")
        for code, entry in split.items():
            votes = ", ".join(f"{m}: {v}" for m, v in entry["votes"].items())
            out.append(f"### {code} — {votes}")
            for dissent in entry["dissents"]:
                out.append(f"> *{dissent['model']}* ({dissent['verdict']}): "
                           f"{dissent['rationale']}")
            out.append("")
    return "\n".join(out) + "\n"


def main(argv=None):
    run_dir = common.latest_run()
    if not run_dir:
        raise SystemExit("no run")
    panel = load_panel(run_dir)
    if len(panel) < 2:
        print(f"only {len(panel)} reviewer(s) ingested — a panel of one is "
              f"just an opinion. Paste data_pack.md into more models and "
              f"ingest their replies.")
        return 1
    agreement = matrix(panel)
    text = render(agreement, sorted(panel))
    path = os.path.join(run_dir, "consensus.md")
    with open(path, "w") as fh:
        fh.write(text)
    common.save_json(os.path.join(run_dir, "consensus.json"), agreement)
    print(text)
    print(f"→ {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
