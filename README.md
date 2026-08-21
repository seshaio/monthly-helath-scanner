# Monthly Status Check

A monthly monitor over a hand-picked list of TSE equities and ETFs. Sibling
to [../TSE-screener](../TSE-screener), which *discovers* names in the top
200; this one *watches* the names already chosen.

**This is a monitoring tool, not investment advice.** Every threshold is a
configurable assumption in [config.py](config.py), fixed before any data is
fetched. Verify anything you act on against the issuer's own filings.

## The monthly run

```bash
./monthly_run.sh
```

One command. It refuses to start if the source differs from the last commit,
runs the offline tests, executes the pipeline, and verifies that no code
changed mid-run. The report lands at `output/latest/YYYY-MM-DD-report.md`;
every artifact that produced it sits beside it in the same folder.

The report is one page: a 0–10 **Market Score** from five macro lenses, a
summary, an equity table and an ETF table (different instruments, different
rubrics, same verdict words), portfolio concentration, month-over-month
changes with named causes, and a scorecard that grades old verdicts once
they are old enough to grade.

**Verdicts: BUY · KEEP · TRIM · SELL · WAIT.** Score = soundness (0–4) +
valuation (0–4) + trend (0–2). Soundness is the health ladder for an equity
and structure for a fund. Valuation alone can never reach SELL — a sound
business at an extreme price is TRIM, "reduce, not exit". A name reporting
within 5 days is WAIT, not a verdict from figures about to be superseded.

## The reviewer panel

The pipeline computes; models interpret a table they cannot edit.

```bash
.venv/bin/python -m monitor.pack          # -> output/latest/data_pack.md
# paste data_pack.md into each external model, save each JSON reply, then:
.venv/bin/python -m monitor.ingest gpt-x reply.json
.venv/bin/python -m monitor.consensus     # agreement matrix
```

Reviewers see no mechanical verdict and no prior month's call — blind on
purpose, so nobody anchors or herds. Verdicts are never averaged: where the
panel splits, the dissent is quoted by name, and that is the month's reading
list.

## Between runs

```bash
.venv/bin/python -m monitor.tripwire
```

Weekly. Silent when quiet; prints and exits 1 when a price leaves the last
run's limit band, RSI reaches an extreme, a name reports within 7 days, or a
price series breaks. A smoke alarm, not a verdict.

## Changing the universe

Edit [universe.toml](universe.toml) — the one file meant to change. Add a
ticker, mark `held`, tag ETF fx exposure. Names resolve from JPX's own
listed-issues workbook, never from a model's memory. Thresholds live in
[config.py](config.py) and are meant to hold still: a month where both the
list and the rules moved is uninterpretable.

Declared corporate actions (`[[split]]`, `[[bad_print]]`) and severe events
(`[[concern]]` — restatements, going-concern) also live in universe.toml.
Detection is automatic; correction is a deliberate human act, verified
against the issuer, recorded in the run.

## First time

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests    # 103 tests, offline, ~1s
```

## Layout

```
config.py            every threshold and judgment, set before data is seen
universe.toml        the list, corrections, declared concerns
common.py            run folders, cache, throttled fetch, JSON plumbing
integrity.py         clean-source gate + fingerprint (sibling's pattern)
monthly_run.sh       check, test, run, verify

monitor/
  universe.py        JPX name resolution; nothing is guessed
  indicators.py      RSI (Wilder), returns, vol, limit bands, break detection
  valuation.py       five anchors vs own 5y history; consensus demoted
  health.py          the ladder: INTACT → WATCH → IMPAIRED → BROKEN
  etf.py             the fund rubric: structure + underlying index
  verdict.py         one scale, five words, overrides in priority order
  macro.py           dashboard + five lenses; prose generated from the rules
  portfolio.py       correlation clusters, fx tags — counts, never weights
  earnings.py        report dates and the WAIT gate
  deltas.py          month-over-month diff; every change names its cause
  score.py           the scorecard; refuses to print a coin-flip hit rate
  pack.py            the frozen reviewer input
  ingest.py          strict validation of a reviewer's reply
  consensus.py       the agreement matrix; dissent quoted, never averaged
  report.py          renders the page
  tripwire.py        the weekly check

output/YYYY-MM-DD-run-N/   every run, never overwritten; latest -> newest
cache/                     same-day fetch cache, safe to delete
```

## Data honesty rules

Learned here and next door, enforced in code and guarded by tests:

- A feed failure must never look like a finding. Empty feeds raise.
- Missing data is unassessed, never INTACT, never cheap, never a signal.
- A 90% one-day move is a split or a bad print, not a crash; nothing is
  auto-repaired, and a suspect series is refused, not scored.
- Statements apply 45 days after period end — no hindsight in percentiles.
- Anchors that disagree are flagged, not averaged. Same for reviewers.
- A verdict resting on a hairline trigger says so out loud.
