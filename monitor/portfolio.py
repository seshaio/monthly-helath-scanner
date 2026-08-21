"""
The portfolio layer: what sixteen per-name verdicts cannot see.

Holdings are known; weights are not. So concentration is evidenced by
realised correlation from price history, which needs no position sizes —
names that move together are one bet however many lines they occupy.

FX exposure is read from the fx tags in universe.toml plus cluster overlap.
No weights means no beta: the report says HOW MANY names carry the exposure,
never how large it is.
"""

import sys

import pandas as pd

import config


def correlation_matrix(rows):
    """Pairwise correlation of daily returns over the trailing year."""
    series = {r["code"]: r["_close"] for r in rows
              if r.get("_close") is not None and len(r.get("_close", [])) > 0
              and not r.get("data_suspect")}
    if len(series) < 2:
        return pd.DataFrame()
    frame = pd.DataFrame(series).tail(config.CORRELATION_WINDOW_DAYS + 1)
    returns = frame.pct_change().dropna(how="all")
    return returns.corr(min_periods=config.MIN_TRADING_DAYS // 2)


def find_clusters(corr):
    """
    Connected components over pairs correlated past the threshold.

    Union-find rather than anything statistical: the question is "which names
    are effectively one position", and a chain of strong pairwise links is
    exactly that even if the ends correlate less with each other.
    """
    if corr.empty:
        return []
    codes = list(corr.columns)
    parent = {c: c for c in codes}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    for i, a in enumerate(codes):
        for b in codes[i + 1:]:
            rho = corr.loc[a, b]
            if pd.notna(rho) and rho >= config.CLUSTER_CORRELATION_THRESHOLD:
                parent[find(a)] = find(b)

    groups = {}
    for c in codes:
        groups.setdefault(find(c), []).append(c)

    clusters = []
    for members in groups.values():
        if len(members) < config.CLUSTER_MIN_MEMBERS:
            continue
        pairs = [corr.loc[a, b] for i, a in enumerate(members)
                 for b in members[i + 1:] if pd.notna(corr.loc[a, b])]
        clusters.append({
            "members": sorted(members),
            "mean_pairwise_rho": float(pd.Series(pairs).mean()) if pairs else None,
        })
    return sorted(clusters, key=lambda c: -len(c["members"]))


def top_pairs(corr, n=5):
    if corr.empty:
        return []
    pairs = [(a, b, float(corr.loc[a, b]))
             for i, a in enumerate(corr.columns) for b in corr.columns[i + 1:]
             if pd.notna(corr.loc[a, b])]
    return sorted(pairs, key=lambda p: -p[2])[:n]


def fx_exposure(rows):
    """Names carrying non-yen exposure, by declared tag. Counts, not weights."""
    tagged = {}
    for r in rows:
        fx = r.get("fx")
        if fx and fx != "jpy":
            tagged.setdefault(fx, []).append(r["code"])
    return tagged


def build(rows):
    corr = correlation_matrix(rows)
    return {
        "clusters": find_clusters(corr),
        "top_pairs": top_pairs(corr),
        "fx": fx_exposure(rows),
        "names_correlated": len(corr.columns) if not corr.empty else 0,
    }


def main(argv=None):
    from monitor import indicators
    out = build(indicators.build(keep_series=True))
    for cluster in out["clusters"]:
        print(f"cluster: {', '.join(cluster['members'])}  "
              f"mean ρ {cluster['mean_pairwise_rho']:.2f}")
    print("\ntop pairs:")
    for a, b, rho in out["top_pairs"]:
        print(f"  {a} / {b}  ρ {rho:.2f}")
    print(f"\nfx: {out['fx']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
