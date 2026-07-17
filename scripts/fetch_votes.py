#!/usr/bin/env python3
"""Fetch Rep. Andrea Salinas's (D-OR-6, bioguide S001226) full House roll-call
history from the Clerk of the House EVS XML feed and write it to CSV + JSON.

Source: https://clerk.house.gov/evs/{year}/roll{NNN}.xml

The script is incremental: previously fetched votes are cached in
data/salinas_votes.json and only new roll numbers are requested on re-runs.
Pass --full to refetch everything (e.g. to pick up vote corrections).

Only Python stdlib is used.
"""

import argparse
import concurrent.futures
import csv
import datetime
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BIOGUIDE_ID = "S001226"
MEMBER_NAME = "Andrea Salinas"
FIRST_YEAR = 2023  # sworn in Jan 3, 2023 (118th Congress)
BASE_URL = "https://clerk.house.gov/evs/{year}/roll{num:03d}.xml"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
JSON_PATH = DATA_DIR / "salinas_votes.json"
CSV_PATH = DATA_DIR / "salinas_votes.csv"
MAX_WORKERS = 12
# Stop sweeping a year after this many consecutive missing roll numbers.
MISS_LIMIT = 5

CSV_COLUMNS = [
    "year",
    "roll",
    "date",
    "time",
    "congress",
    "session",
    "bill",
    "question",
    "subject",
    "vote_type",
    "salinas_vote",
    "dem_yea",
    "dem_nay",
    "dem_present",
    "dem_nv",
    "rep_yea",
    "rep_nay",
    "rep_present",
    "rep_nv",
    "ind_yea",
    "ind_nay",
    "ind_present",
    "ind_nv",
    "total_yea",
    "total_nay",
    "total_present",
    "total_nv",
    "party_breakdown",
    "result",
    "passed",
]

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def parse_action_date(raw):
    """Clerk dates look like '3-Jan-2023' -> ISO 'YYYY-MM-DD'."""
    m = re.match(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", raw or "")
    if not m:
        return raw or ""
    day, mon, year = int(m.group(1)), MONTHS.get(m.group(2), 0), int(m.group(3))
    if not mon:
        return raw
    return f"{year:04d}-{mon:02d}-{day:02d}"


def normalize_bill(legis_num):
    """'H R 1234' -> 'H.R. 1234', 'S 5' -> 'S. 5', 'QUORUM' left as-is."""
    if not legis_num:
        return ""
    s = legis_num.strip()
    m = re.match(r"^([A-Z][A-Z .]*?)\s+(\d+)$", s)
    if not m:
        return s
    prefix = m.group(1).replace(" ", "").replace("..", ".")
    pretty = {
        "HR": "H.R.", "S": "S.", "HRES": "H.Res.", "SRES": "S.Res.",
        "HJRES": "H.J.Res.", "SJRES": "S.J.Res.",
        "HCONRES": "H.Con.Res.", "SCONRES": "S.Con.Res.",
    }.get(prefix.replace(".", ""), prefix)
    return f"{pretty} {m.group(2)}"


def fetch_url(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "rep-tracker/1.0 (voting-record research)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_roll(year, num):
    """Return parsed vote dict, or None if the roll number does not exist."""
    url = BASE_URL.format(year=year, num=num)
    for attempt in range(3):
        try:
            raw = fetch_url(url)
            return parse_vote_xml(raw, year, num)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError, ET.ParseError):
            if attempt == 2:
                raise
    return None


def parse_vote_xml(raw, year, num):
    root = ET.fromstring(raw)
    meta = root.find("vote-metadata")

    def get(tag):
        el = meta.find(tag)
        return (el.text or "").strip() if el is not None and el.text else ""

    record = {
        "year": year,
        "roll": num,
        "date": parse_action_date(get("action-date")),
        "time": (meta.findtext("action-time") or "").strip(),
        "congress": get("congress"),
        "session": get("session"),
        "bill": normalize_bill(get("legis-num")),
        "question": get("vote-question"),
        "subject": get("vote-desc"),
        "vote_type": get("vote-type"),
        "result": get("vote-result"),
    }

    # Party totals
    parties = {"Democratic": "dem", "Republican": "rep", "Independent": "ind"}
    for key in parties.values():
        for f in ("yea", "nay", "present", "nv"):
            record[f"{key}_{f}"] = 0
    totals = meta.find("vote-totals")
    if totals is not None:
        for tp in totals.findall("totals-by-party"):
            pname = (tp.findtext("party") or "").strip()
            key = parties.get(pname)
            if not key:
                continue
            record[f"{key}_yea"] = int(tp.findtext("yea-total") or 0)
            record[f"{key}_nay"] = int(tp.findtext("nay-total") or 0)
            record[f"{key}_present"] = int(tp.findtext("present-total") or 0)
            record[f"{key}_nv"] = int(tp.findtext("not-voting-total") or 0)
        tv = totals.find("totals-by-vote")
        record["total_yea"] = int(tv.findtext("yea-total") or 0) if tv is not None else 0
        record["total_nay"] = int(tv.findtext("nay-total") or 0) if tv is not None else 0
        record["total_present"] = int(tv.findtext("present-total") or 0) if tv is not None else 0
        record["total_nv"] = int(tv.findtext("not-voting-total") or 0) if tv is not None else 0
    else:
        record["total_yea"] = record["total_nay"] = 0
        record["total_present"] = record["total_nv"] = 0

    record["party_breakdown"] = (
        f"D {record['dem_yea']}-{record['dem_nay']}; "
        f"R {record['rep_yea']}-{record['rep_nay']}; "
        f"I {record['ind_yea']}-{record['ind_nay']}"
    )
    record["passed"] = "Pass" if record["result"].lower().startswith(("passed", "agreed")) else "Fail"

    # Salinas's individual vote
    record["salinas_vote"] = ""
    vote_data = root.find("vote-data")
    if vote_data is not None:
        for rv in vote_data.findall("recorded-vote"):
            leg = rv.find("legislator")
            if leg is not None and leg.get("name-id") == BIOGUIDE_ID:
                record["salinas_vote"] = (rv.findtext("vote") or "").strip()
                break

    return record


def sweep_year(year, start_roll, log=print):
    """Fetch rolls for a year starting at start_roll until MISS_LIMIT
    consecutive misses. Returns list of vote dicts."""
    votes = []
    num = start_roll
    misses = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        while misses < MISS_LIMIT:
            batch = list(range(num, num + MAX_WORKERS))
            results = list(pool.map(lambda n: (n, fetch_roll(year, n)), batch))
            for n, rec in results:
                if rec is None:
                    misses += 1
                else:
                    misses = 0
                    votes.append(rec)
            num += MAX_WORKERS
            fetched = len(votes)
            if fetched and fetched % 96 == 0:
                log(f"  {year}: {fetched} new rolls fetched (at roll {num})...")
    return votes


def load_existing():
    if JSON_PATH.exists():
        with open(JSON_PATH) as f:
            return json.load(f).get("votes", [])
    return []


def write_outputs(votes):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    votes.sort(key=lambda v: (v["year"], v["roll"]))
    payload = {
        "member": MEMBER_NAME,
        "bioguide_id": BIOGUIDE_ID,
        "district": "OR-6",
        "party": "D",
        "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "clerk.house.gov EVS XML",
        "count": len(votes),
        "votes": votes,
    }
    with open(JSON_PATH, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for v in votes:
            w.writerow({k: v.get(k, "") for k in CSV_COLUMNS})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--full", action="store_true", help="refetch all years from scratch")
    args = ap.parse_args()

    existing = [] if args.full else load_existing()
    by_year_max = {}
    for v in existing:
        by_year_max[v["year"]] = max(by_year_max.get(v["year"], 0), v["roll"])

    current_year = datetime.date.today().year
    all_votes = list(existing)
    for year in range(FIRST_YEAR, current_year + 1):
        start = by_year_max.get(year, 0) + 1
        print(f"Sweeping {year} from roll {start:03d}...")
        new = sweep_year(year, start)
        print(f"  {year}: +{len(new)} votes")
        all_votes.extend(new)

    write_outputs(all_votes)
    print(f"Wrote {len(all_votes)} votes -> {CSV_PATH.name}, {JSON_PATH.name}")


if __name__ == "__main__":
    main()
