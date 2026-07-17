#!/usr/bin/env python3
"""Score every roll call in data/salinas_votes.json on a traditional 5x5 risk
matrix for exposure of liberal-democratic institutions.

  impact (1-5)      how democracy-relevant the measure is, from the keyword
                    rubric in config/risk_rubric.json (editable)
  likelihood (1-5)  how far the measure actually advanced toward taking effect,
                    derived from the vote's question, result, and margin
  risk_score        impact x likelihood (1-25)
  risk_band         Low (<=4) / Moderate (5-9) / High (10-16) / Critical (>=17)

The matrix scores *salience and exposure*, not the direction of the member's
vote - her vote is carried alongside so readers can see whether she voted to
advance or block each measure. Hand-curated corrections live in
config/risk_overrides.json and always win over the rubric.

Reads  data/salinas_votes.json  (produced by fetch_votes.py)
Writes data/salinas_votes_scored.json and data/salinas_votes_scored.csv
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"
IN_JSON = DATA_DIR / "salinas_votes.json"
OUT_JSON = DATA_DIR / "salinas_votes_scored.json"
OUT_CSV = DATA_DIR / "salinas_votes_scored.csv"

RISK_COLUMNS = ["risk_domain", "risk_impact", "risk_likelihood", "risk_score", "risk_band", "risk_keywords"]

# columns mirror fetch_votes.CSV_COLUMNS + risk fields; derive from data keys
BASE_COLUMNS = [
    "year", "roll", "date", "time", "congress", "session", "bill", "question",
    "subject", "vote_type", "salinas_vote",
    "dem_yea", "dem_nay", "dem_present", "dem_nv",
    "rep_yea", "rep_nay", "rep_present", "rep_nv",
    "ind_yea", "ind_nay", "ind_present", "ind_nv",
    "total_yea", "total_nay", "total_present", "total_nv",
    "party_breakdown", "result", "passed",
]

# question fragments marking how far a successful vote moves the measure
ENACTMENT_PROXIMATE = (
    "objections of the president",        # veto override
    "motion to concur in the senate",     # last chamber action before president
    "concurring in the senate amendment",
)
FINAL_PASSAGE = (
    "on passage",
    "suspend the rules and pass",
)
SELF_EXECUTING = (
    "on agreeing to the resolution",      # simple H.Res. takes effect on adoption
    "suspend the rules and agree to the resolution",
    "on adopting",
)


def band(score):
    if score <= 4:
        return "Low"
    if score <= 9:
        return "Moderate"
    if score <= 16:
        return "High"
    return "Critical"


def score_impact(vote, rubric):
    hay = " ".join([vote.get("bill", ""), vote.get("question", ""), vote.get("subject", "")]).lower()
    best_impact = rubric.get("default_impact", 1)
    best_domain = rubric.get("default_domain", "Routine policy")
    matched = []
    for dom in rubric["domains"]:
        hits = [kw for kw in dom["keywords"] if kw in hay]
        if hits:
            matched.extend(hits)
            if dom["impact"] > best_impact or (best_domain == rubric.get("default_domain") and dom["impact"] >= best_impact):
                best_impact = dom["impact"]
                best_domain = dom["name"]
    return best_impact, best_domain, sorted(set(matched))


def score_likelihood(vote):
    if vote.get("passed") != "Pass":
        return 1
    q = (vote.get("question") or "").lower()
    bill = vote.get("bill", "")
    if "providing for consideration" in (vote.get("subject") or "").lower():
        return 2  # a special rule only tees the measure up - procedural stage
    if any(p in q for p in ENACTMENT_PROXIMATE):
        return 5
    if bill.startswith(("H.Res.",)) and any(p in q for p in SELF_EXECUTING):
        return 5  # simple House resolution: adoption IS enactment
    if any(p in q for p in FINAL_PASSAGE) or any(p in q for p in SELF_EXECUTING):
        yn = vote.get("total_yea", 0) + vote.get("total_nay", 0)
        veto_proof = yn > 0 and vote.get("total_yea", 0) * 3 >= yn * 2
        return 4 if veto_proof else 3  # House passage; Senate + president still ahead
    return 2  # procedural or amendment win


def main():
    with open(IN_JSON) as f:
        payload = json.load(f)
    with open(CONFIG_DIR / "risk_rubric.json") as f:
        rubric = json.load(f)
    with open(CONFIG_DIR / "risk_overrides.json") as f:
        overrides = json.load(f).get("votes", {})

    for v in payload["votes"]:
        impact, domain, keywords = score_impact(v, rubric)
        likelihood = score_likelihood(v)
        note = ""
        ov = overrides.get(f"{v['year']}-{v['roll']}")
        if ov:
            impact = int(ov.get("impact", impact))
            likelihood = int(ov.get("likelihood", likelihood))
            domain = ov.get("domain", domain)
            note = ov.get("note", "")
        score = impact * likelihood
        v["risk_domain"] = domain
        v["risk_impact"] = impact
        v["risk_likelihood"] = likelihood
        v["risk_score"] = score
        v["risk_band"] = band(score)
        v["risk_keywords"] = "; ".join(keywords)
        if note:
            v["risk_note"] = note

    payload["risk_method"] = (
        "impact = keyword rubric (config/risk_rubric.json), likelihood = legislative "
        "advancement from vote outcome; score = impact x likelihood; overrides from "
        "config/risk_overrides.json. Heuristic - see README."
    )
    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    cols = BASE_COLUMNS + RISK_COLUMNS
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for v in payload["votes"]:
            w.writerow({k: v.get(k, "") for k in cols})

    from collections import Counter
    bands = Counter(v["risk_band"] for v in payload["votes"])
    print(f"Scored {len(payload['votes'])} votes -> {OUT_CSV.name}, {OUT_JSON.name}")
    print("  bands:", dict(sorted(bands.items(), key=lambda kv: ["Low", "Moderate", "High", "Critical"].index(kv[0]))))


if __name__ == "__main__":
    main()
