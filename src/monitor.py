#!/usr/bin/env python3
"""
Homepage uptime + response-time prober for PKHosting and five competitors.

Same technique as free monitoring tools (UptimeRobot-style): an HTTP check of
each homepage every INTERVAL seconds, following redirects, recording the full
curl timing breakdown. Every result is appended to data/monitoring_raw.csv
immediately, so an interrupted run still leaves usable data.

A check counts as UP when the final HTTP status is 2xx (after redirects).
Primary response metric: time to first byte (time_starttransfer).
"""
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

SITES = [
    ("PKHosting", "https://pkhosting.com"),
    ("WebSouls", "https://www.websouls.com"),
    ("HostKarle", "https://www.hostkarle.com"),
    ("HostBreak", "https://www.hostbreak.com"),
    ("HosterPK", "https://hosterpk.com"),
    ("Hostinger", "https://www.hostinger.com"),
]
INTERVAL = 45          # seconds between rounds
ROUNDS = 80            # ~60 minutes of monitoring
TIMEOUT = 20

BASE = os.path.join(os.path.dirname(__file__), "..")
CSV_PATH = os.path.join(BASE, "data", "monitoring_raw.csv")
FIELDS = ["timestamp_utc", "round", "site", "url", "final_url", "http_code",
          "redirects", "dns_s", "connect_s", "tls_s", "ttfb_s", "total_s",
          "size_bytes", "up"]
W_FORMAT = json.dumps({
    "code": "%{http_code}", "redir": "%{num_redirects}",
    "dns": "%{time_namelookup}", "conn": "%{time_connect}",
    "tls": "%{time_appconnect}", "ttfb": "%{time_starttransfer}",
    "total": "%{time_total}", "size": "%{size_download}",
    "final": "%{url_effective}"})


def probe(name, url):
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cmd = ["curl", "-s", "-L", "--max-time", str(TIMEOUT),
           "-A", "Mozilla/5.0 (X11; Linux x86_64) uptime-benchmark-probe",
           "-o", "/dev/null", "-w", W_FORMAT, url]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT + 10)
        d = json.loads(out.stdout)
        code = int(d["code"])
        return [ts, "", name, url, d["final"], code, int(d["redir"]),
                float(d["dns"]), float(d["conn"]), float(d["tls"]),
                float(d["ttfb"]), float(d["total"]), int(float(d["size"])),
                1 if 200 <= code < 300 else 0]
    except Exception as e:  # network failure = down check
        return [ts, "", name, url, "", 0, 0, 0, 0, 0, 0, 0, 0, 0]


def main():
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    new_file = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(FIELDS)
        for rnd in range(1, ROUNDS + 1):
            start = time.time()
            for name, url in SITES:
                row = probe(name, url)
                row[1] = rnd
                w.writerow(row)
                f.flush()
                print(f"round {rnd}: {name} code={row[5]} ttfb={row[10]:.3f} total={row[11]:.3f}", flush=True)
            wait = INTERVAL - (time.time() - start)
            if wait > 0 and rnd < ROUNDS:
                time.sleep(wait)
    print("MONITORING COMPLETE")


if __name__ == "__main__":
    sys.exit(main())
