"""
Source integrity for a monthly run — the sibling screener's pattern.

The monthly job is "run it, change nothing". Prose does not stop an agent
that decides a quick fix is warranted, so the rule is enforced: the run
refuses to start on a dirty tree, the source is fingerprinted before and
after, and the fingerprint lands in the run folder so every report traces to
the exact code that produced it.

    python integrity.py require-clean
    python integrity.py snapshot <manifest.json>
    python integrity.py verify   <manifest.json>
"""

import hashlib
import json
import os
import subprocess
import sys

TRACKED = ("*.py", "monitor/*.py", "tests/*.py", "universe.toml",
           "requirements.txt")


def _files():
    import glob
    seen = []
    for pattern in TRACKED:
        seen.extend(sorted(glob.glob(pattern)))
    return sorted(set(seen))


def fingerprint():
    out = {}
    for path in _files():
        with open(path, "rb") as fh:
            out[path] = hashlib.sha256(fh.read()).hexdigest()
    return out


def require_clean():
    result = subprocess.run(
        ["git", "status", "--porcelain", "--"] + _files(),
        capture_output=True, text=True, check=True)
    dirty = [line for line in result.stdout.splitlines() if line.strip()]
    if dirty:
        print("REFUSING TO RUN: source differs from the last commit.")
        print("A monthly run must be reproducible from a known commit.\n")
        for line in dirty:
            print(f"  {line}")
        print("\nCommit the change deliberately, then run again.")
        return 1
    return 0


def snapshot(path):
    with open(path, "w") as fh:
        json.dump(fingerprint(), fh, indent=2, sort_keys=True)
    return 0


def verify(path):
    with open(path) as fh:
        before = json.load(fh)
    now = fingerprint()
    changed = sorted(set(before.items()) ^ set(now.items()))
    if changed:
        print("SOURCE CHANGED DURING THE RUN — report untrusted:")
        for name, _ in changed:
            print(f"  {name}")
        return 1
    return 0


def main(argv):
    if len(argv) >= 1 and argv[0] == "require-clean":
        return require_clean()
    if len(argv) == 2 and argv[0] == "snapshot":
        return snapshot(argv[1])
    if len(argv) == 2 and argv[0] == "verify":
        return verify(argv[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
