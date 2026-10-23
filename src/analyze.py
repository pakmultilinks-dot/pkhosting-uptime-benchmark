#!/usr/bin/env python3
"""
Analyze data/monitoring_raw.csv:
  - per-site uptime % and response-time summary (median, p95, mean, sd)
    for TTFB (primary) and total time
  - Kruskal-Wallis omnibus test across all six sites (TTFB)
  - Mann-Whitney U: PKHosting vs each competitor (TTFB), Holm correction,
    rank-biserial effect size
  - Fisher exact test on up/down counts where failures exist
Outputs: output/results.json, output/summary.txt,
         output/chart_ttfb_box.png, output/chart_ttfb_series.png
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(BASE, "output")
SITES = ["PKHosting", "WebSouls", "HostKarle", "HostBreak", "HosterPK", "Hostinger"]


def holm(pvals):
    order = np.argsort(pvals)
    adj = np.empty(len(pvals))
    running = 0.0
    for rank, idx in enumerate(order):
        val = (len(pvals) - rank) * pvals[idx]
        running = max(running, val)
        adj[idx] = min(running, 1.0)
    return adj


def main():
    df = pd.read_csv(os.path.join(BASE, "data", "monitoring_raw.csv"))
    # keep only complete rounds (6 sites each): a partial round can only come
    # from the probe machine itself failing mid-round, not from a website
    counts = df.groupby("round").size()
    df = df[df["round"].isin(counts[counts == 6].index)].copy()
    ok = df[df.up == 1]
    summary, ttfb_by_site = {}, {}
    for s in SITES:
        sub, subok = df[df.site == s], ok[ok.site == s]
        ttfb_by_site[s] = subok["ttfb_s"].values
        summary[s] = {
            "checks": int(len(sub)),
            "up": int(sub["up"].sum()),
            "uptime_pct": round(100 * sub["up"].mean(), 2),
            "ttfb_median": round(float(subok["ttfb_s"].median()), 3),
            "ttfb_p95": round(float(subok["ttfb_s"].quantile(0.95)), 3),
            "ttfb_mean": round(float(subok["ttfb_s"].mean()), 3),
            "total_median": round(float(subok["total_s"].median()), 3),
            "total_p95": round(float(subok["total_s"].quantile(0.95)), 3),
            "size_kb_median": round(float(subok["size_bytes"].median()) / 1024, 1),
            "errors": sub[sub.up == 0]["http_code"].value_counts().to_dict(),
        }

    kw = stats.kruskal(*[ttfb_by_site[s] for s in SITES])
    pk = ttfb_by_site["PKHosting"]
    raw_p, rows = [], []
    for s in SITES[1:]:
        u = stats.mannwhitneyu(pk, ttfb_by_site[s], alternative="two-sided")
        n1, n2 = len(pk), len(ttfb_by_site[s])
        rbc = 1 - (2 * u.statistic) / (n1 * n2)  # rank-biserial, + = PKHosting slower
        raw_p.append(u.pvalue)
        rows.append({"competitor": s, "u": float(u.statistic),
                     "p_raw": float(u.pvalue), "rank_biserial": round(float(rbc), 3),
                     "median_diff_s": round(float(np.median(pk) - np.median(ttfb_by_site[s])), 3)})
    for r, pa in zip(rows, holm(raw_p)):
        r["p_holm"] = float(pa)
        r["significant_0.05"] = bool(pa < 0.05)

    fisher = None
    fails = {s: summary[s]["checks"] - summary[s]["up"] for s in SITES}
    if sum(fails.values()) > 0:
        table = [[summary["PKHosting"]["up"], fails["PKHosting"]],
                 [sum(summary[s]["up"] for s in SITES[1:]),
                  sum(fails[s] for s in SITES[1:])]]
        fisher = {"table_pk_vs_rest": table,
                  "p": float(stats.fisher_exact(table)[1])}

    results = {
        "window": {"first_check_utc": str(df.timestamp_utc.min()),
                   "last_check_utc": str(df.timestamp_utc.max()),
                   "rounds": int(df["round"].nunique()),
                   "interval_s": 45, "total_checks": int(len(df))},
        "summary": summary,
        "kruskal_wallis_ttfb": {"H": round(float(kw.statistic), 3),
                                "p": float(kw.pvalue)},
        "mann_whitney_pkhosting_vs": rows,
        "fisher_uptime": fisher,
        "failures_by_site": fails,
    }
    with open(os.path.join(OUT, "results.json"), "w") as f:
        json.dump(results, f, indent=2)

    with open(os.path.join(OUT, "summary.txt"), "w") as f:
        f.write(f"Window {results['window']['first_check_utc']} .. {results['window']['last_check_utc']} UTC, "
                f"{results['window']['total_checks']} checks\n\n")
        for s in SITES:
            m = summary[s]
            f.write(f"{s:10s} uptime {m['uptime_pct']}% ({m['up']}/{m['checks']})  "
                    f"TTFB med {m['ttfb_median']}s p95 {m['ttfb_p95']}s  "
                    f"total med {m['total_median']}s  page {m['size_kb_median']} KB\n")
        f.write(f"\nKruskal-Wallis TTFB: H={results['kruskal_wallis_ttfb']['H']}, "
                f"p={results['kruskal_wallis_ttfb']['p']:.3g}\n")
        for r in rows:
            f.write(f"MWU PKHosting vs {r['competitor']:10s} p_holm={r['p_holm']:.3g} "
                    f"sig={r['significant_0.05']} rank_biserial={r['rank_biserial']} "
                    f"median_diff={r['median_diff_s']}s\n")

    # chart 1: TTFB boxplot
    fig, ax = plt.subplots(figsize=(9.5, 5))
    ax.boxplot([ttfb_by_site[s] for s in SITES], tick_labels=SITES, showfliers=True)
    ax.set_ylabel("Time to first byte (s)")
    ax.set_title("Homepage TTFB distribution per site (successful checks)")
    ax.set_ylim(0, 6.5)
    ax.annotate("one HostBreak check at 19.2s\n(off chart)", xy=(3, 6.3),
                ha="center", fontsize=8, color="#555555")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "chart_ttfb_box.png"), dpi=150)

    # chart 2: per-round median TTFB series
    piv = ok.pivot_table(index="round", columns="site", values="ttfb_s", aggfunc="median")
    fig, ax = plt.subplots(figsize=(9.5, 5))
    for s in SITES:
        lw = 2.2 if s == "PKHosting" else 1.2
        ax.plot(piv.index, piv[s], label=s, linewidth=lw)
    ax.set_xlabel("Check round (every ~45 s)")
    ax.set_ylabel("Median TTFB that round (s)")
    ax.set_title("TTFB over the monitoring window")
    ax.legend(ncol=3, fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "chart_ttfb_series.png"), dpi=150)

    print(open(os.path.join(OUT, "summary.txt")).read())


if __name__ == "__main__":
    main()
