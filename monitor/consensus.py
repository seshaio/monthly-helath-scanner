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
import config
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


def price_disputes(panel):
    """
    Where reviewers contradicted the pack's price.

    Reported before any verdict, because a disputed price is not a difference
    of opinion — if it is right, every number derived from that price is
    wrong and the name's verdict is void rather than debatable. The mechanical
    column has no view here and is skipped.
    """
    out = {}
    for model, reviews in panel.items():
        if model == "mechanical":
            continue
        for code, review in reviews.items():
            check = review.get("price_check")
            if check == "differs":
                out.setdefault(code, []).append({
                    "model": model,
                    "observed": review.get("price_observed"),
                    "rationale": review.get("rationale", ""),
                })
    return {code: sorted(v, key=lambda d: d["model"])
            for code, v in sorted(out.items())}


def unchecked_prices(panel):
    """Reviewers that could not verify a price at all, counted per name."""
    out = {}
    for model, reviews in panel.items():
        if model == "mechanical":
            continue
        for code, review in reviews.items():
            if review.get("price_check") == "unchecked":
                out.setdefault(code, []).append(model)
    return {code: sorted(v) for code, v in sorted(out.items())}


def render(agreement, panel_names, disputes=None, unchecked=None):
    out = [f"# Panel consensus — {len(panel_names)} reviewers "
           f"({', '.join(panel_names)})", ""]
    unanimous = {c: a for c, a in agreement.items() if a["unanimous"]}
    split = {c: a for c, a in agreement.items() if not a["unanimous"]}
    out.append(f"Unanimous on {len(unanimous)} of {len(agreement)} names.")
    out.append("")

    if disputes:
        out.append("## ⚠ Disputed prices — read before anything else")
        out.append("")
        out.append("A reviewer says the pack's price is wrong. If it is, every "
                   "figure derived from it is wrong too and the verdict below "
                   "is void, not merely contested. Check these against the "
                   "exchange before reading on.")
        out.append("")
        for code, claims in disputes.items():
            out.append(f"### {code}")
            for claim in claims:
                observed = claim["observed"]
                shown = f"{observed:,.1f}" if isinstance(observed, (int, float)) else "unstated"
                out.append(f"- *{claim['model']}* reads it at **{shown}** — "
                           f"{claim['rationale']}")
            out.append("")

    if unchecked:
        names = ", ".join(f"{code} ({len(models)})"
                          for code, models in unchecked.items())
        out.append(f"*Prices unverified by at least one reviewer: {names}. "
                   f"Unverified is not confirmed.*")
        out.append("")

    # Agreements first: the settled ground, one line each — read it, accept
    # it, move on. The reading list comes after.
    if unanimous:
        out.append("## Agreements — accept and move on")
        out.append("")
        by_verdict = {}
        for code, entry in unanimous.items():
            verdict = next(iter(entry["votes"].values()))
            by_verdict.setdefault(verdict, []).append(code)
        for verdict in ("BUY", "KEEP", "TRIM", "SELL", "WAIT"):
            if verdict in by_verdict:
                out.append(f"- **{verdict}:** "
                           + ", ".join(sorted(by_verdict[verdict])))
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


def write_up_path(run_dir):
    """
    Where a run's panel write-up is filed: output/consensus/<run>.md.

    The write-up is the one artifact here meant to be read months later and
    against its neighbours — which run said what about 8001 — so it lives in
    one folder rather than buried one per run directory. The name carries the
    run, so nothing is ever overwritten. consensus.json stays with the run:
    it is state for this run, not a document.
    """
    folder = os.path.join(os.path.abspath(config.OUTPUT_DIR), "consensus")
    os.makedirs(folder, exist_ok=True)
    run_name = os.path.basename(os.path.realpath(run_dir))
    return os.path.join(folder, f"{run_name}.md")


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
    disputes = price_disputes(panel)
    unchecked = unchecked_prices(panel)
    text = render(agreement, sorted(panel), disputes=disputes,
                  unchecked=unchecked)
    path = write_up_path(run_dir)
    with open(path, "w") as fh:
        fh.write(text)
    common.save_json(os.path.join(run_dir, "consensus.json"), {
        "agreement": agreement,
        "price_disputes": disputes,
        "price_unchecked": unchecked,
    })
    print(text)
    print(f"→ {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
