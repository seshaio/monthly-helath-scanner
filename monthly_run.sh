#!/bin/zsh
# The monthly run: check, test, execute, verify. One command, no arguments.
#
# The run-only rule is enforced, not requested: this script refuses to start
# if the source differs from the last commit, and fails the run if code
# changes while it is in progress — so a report can never be built half from
# old code and half from new.
set -e
cd "$(dirname "$0")"

PY=.venv/bin/python
[ -x "$PY" ] || { echo "no .venv — python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }

echo "== 1/5 source must match the last commit =="
$PY integrity.py require-clean

echo "== 2/5 offline guard tests =="
$PY -m unittest discover -s tests -q

echo "== 3/5 fingerprint =="
FP=$(mktemp)
$PY integrity.py snapshot "$FP"

echo "== 4/5 the run =="
$PY -m monitor.report > /dev/null
$PY -m monitor.pack > /dev/null

echo "== 5/5 verify nothing changed mid-run =="
$PY integrity.py verify "$FP"
cp "$FP" output/latest/source_fingerprint.json
rm -f "$FP"

echo
echo "report:    output/latest/$(ls output/latest | grep report.md)"
echo "data pack: output/latest/data_pack.md  (paste into external reviewers,"
echo "           then: $PY -m monitor.ingest <model> <reply.json>"
echo "           and:  $PY -m monitor.consensus)"
echo
echo "weekly between runs:  $PY -m monitor.tripwire"
