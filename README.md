# PKHosting Uptime and Speed Benchmark

A standalone benchmark of the PKHosting homepage against five competitors
(WebSouls, HostKarle, HostBreak, HosterPK, Hostinger), using the same method
as free monitoring tools (UptimeRobot-style periodic HTTP checks). No access
to any of the sites was needed or used: only public homepages were requested.

## Method

- `src/monitor.py` requests each homepage every ~45 seconds (80 rounds by default; the run shipped here completed 45 rounds).
  following redirects, and records the full curl timing breakdown
  (DNS, connect, TLS, time to first byte, total time, page size, HTTP status).
- A check counts as UP when the final status is 2xx.
- Primary response metric: **time to first byte (TTFB)**, which reflects
  server response and is not dominated by homepage file size. Total load
  time of the HTML document is reported alongside, with page sizes, because
  the six homepages differ greatly in weight (about 44 KB to about 1 MB).
- `src/analyze.py` computes per-site uptime and timing summaries, a
  Kruskal-Wallis omnibus test across all six sites, and Mann-Whitney U
  tests of PKHosting against each competitor with Holm correction for the
  five comparisons, plus rank-biserial effect sizes.

## Important limits

- One vantage point: checks ran from a single cloud machine outside
  Pakistan through its network egress, so absolute times are slower than a
  Lahore visitor would see (TLS setup especially). All six sites were
  measured through the identical path in the same minutes, so the
  *comparison* is fair even though the absolute numbers are not local
  user experience.
- The uptime figure covers only the observation window of this run:
  45 rounds, 270 checks, about 33 minutes on 23 Oct 2026. The run was
  planned for 80 rounds and ended early when the probe machine restarted;
  the partial final round (probe-side failures during that restart) was
  removed from the dataset. It is not a 30-day uptime figure and should
  not be quoted as one.
- Only the homepage HTML document is timed, not the full page with images
  and scripts (that is what PageSpeed-style lab tests measure; the keyless
  PageSpeed API was rate-limited from this network during the run, so no
  PageSpeed numbers are claimed).

## Files

- `data/monitoring_raw.csv` - every check, raw
- `src/monitor.py`, `src/analyze.py`
- `output/results.json`, `output/summary.txt`, charts

## Run it

```bash
python3 src/monitor.py     # ~65 minutes for a full 80-round run
python3 src/analyze.py     # writes output/results.json + charts
```
