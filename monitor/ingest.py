"""
Take reviewers' JSON verdicts back into the run folder.

    python -m monitor.ingest <model-name> <reply.json>
    python -m monitor.ingest --all <folder>

--all sweeps every *.json in the folder, using each filename (minus .json)
as the model label. Files are validated independently: one malformed reply
is reported and skipped, the rest still land — the whole point of per-file
validation is that one broken reviewer cannot block the panel.

Validation is strict and unforgiving on purpose: a reply that skips a name,
invents a ticker, or free-forms a verdict word is rejected whole. A panel is
only comparable if every member answered the same questionnaire.
"""

import json
import os
import sys

import common
from monitor import universe as universe_mod
from monitor import verdict as verdict_mod

ALLOWED_VERDICTS = {verdict_mod.BUY, verdict_mod.KEEP, verdict_mod.TRIM,
                    verdict_mod.SELL, verdict_mod.WAIT}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def validate(reviews, expected_codes):
    """Raise ValueError with every problem found, not just the first."""
    problems = []
    if not isinstance(reviews, list):
        raise ValueError("reply must be a JSON array")

    seen = {}
    for i, entry in enumerate(reviews):
        code = str(entry.get("code", "")).strip()
        if code not in expected_codes:
            problems.append(f"[{i}] unknown ticker {code!r}")
            continue
        if code in seen:
            problems.append(f"[{i}] duplicate ticker {code}")
        seen[code] = entry
        if entry.get("verdict") not in ALLOWED_VERDICTS:
            problems.append(f"[{i}] {code}: verdict {entry.get('verdict')!r} "
                            f"not in {sorted(ALLOWED_VERDICTS)}")
        if entry.get("confidence") not in ALLOWED_CONFIDENCE:
            problems.append(f"[{i}] {code}: confidence must be high/medium/low")
        if not str(entry.get("rationale", "")).strip():
            problems.append(f"[{i}] {code}: empty rationale")

    missing = expected_codes - set(seen)
    if missing:
        problems.append(f"missing tickers: {sorted(missing)}")
    if problems:
        raise ValueError("\n".join(problems))
    return seen


def ingest(model_name, reply_path, run_dir=None):
    run_dir = run_dir or common.latest_run()
    if not run_dir:
        raise SystemExit("no run to ingest into")
    expected = {item["code"] for item in universe_mod.load_config()}

    with open(reply_path) as fh:
        reviews = validate(json.load(fh), expected)

    out_dir = os.path.join(run_dir, "reviews")
    path = os.path.join(out_dir, f"{model_name}.json")
    common.save_json(path, {
        "model": model_name,
        "ingested_at": common.utc_now(),
        "reviews": reviews,
    })
    return path


def ingest_all(folder):
    """Sweep a folder; each reply stands or falls on its own."""
    files = sorted(f for f in os.listdir(folder) if f.endswith(".json"))
    if not files:
        print(f"no .json files in {folder}")
        return 1
    failures = 0
    for name in files:
        model = name[:-len(".json")]
        try:
            path = ingest(model, os.path.join(folder, name))
            print(f"✓ {model:<12} → {path}")
        except (ValueError, json.JSONDecodeError) as exc:
            failures += 1
            print(f"✗ {model:<12} REJECTED:\n    "
                  + str(exc).replace("\n", "\n    "))
    print(f"\n{len(files) - failures} of {len(files)} ingested")
    return 1 if failures else 0


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) == 2 and argv[0] == "--all":
        return ingest_all(argv[1])
    if len(argv) != 2:
        print(__doc__)
        return 2
    path = ingest(argv[0], argv[1])
    print(f"ingested → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
