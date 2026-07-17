# rep-tracker — Andrea Salinas voting-record audit

Full House roll-call history for **Rep. Andrea Salinas (D-OR-6, bioguide `S001226`)**,
pulled straight from the Clerk of the House's official EVS XML feed and served as a
mobile-first interactive dashboard on GitHub Pages.

> **Why not the ProPublica Congress API?** It was retired (no new keys, endpoints shut
> down), so this project scripts directly against
> `https://clerk.house.gov/evs/{year}/roll{NNN}.xml` — the primary source ProPublica
> itself ingested. No API key required.

## What's here

| Path | What it is |
|---|---|
| `scripts/fetch_votes.py` | Incremental fetcher/parser (stdlib only, no deps) |
| `data/salinas_votes.csv` | Flat export — roll, date, bill, subject, her vote, party breakdown, pass/fail |
| `data/salinas_votes.json` | Same data plus metadata, consumed by the dashboard |
| `docs/index.html` | Self-contained dashboard (no build step, no external libs) |
| `.github/workflows/update-and-deploy.yml` | Twice-daily refresh + Pages deploy |

## CSV columns

`year, roll, date, time, congress, session, bill, question, subject, vote_type,
salinas_vote, dem_yea, dem_nay, dem_present, dem_nv, rep_yea, rep_nay, rep_present,
rep_nv, ind_yea, ind_nay, ind_present, ind_nv, total_yea, total_nay, total_present,
total_nv, party_breakdown, result, passed`

Notes on the raw values:

- The House records votes as **Yea/Nay** on yea-and-nay votes and **Aye/No** on
  recorded votes; `salinas_vote` keeps the Clerk's original wording (the dashboard
  normalizes them).
- Speaker elections record the candidate's surname (e.g. `Jeffries`) as the vote.
- `party_breakdown` is a compact `D yea-nay; R yea-nay; I yea-nay` summary; the
  per-party integer columns carry the full detail.

## The dashboard

Interactive, mobile-optimized, Tableau-style: every chart, stat, and list re-renders
against the same filter slice (year, her vote, party alignment, free-text search).

- KPI tiles: roll calls, participation, party unity, breaks with party
- Roll calls per month · her vote split · party-unity trend · outcome win-rate
- A dedicated list of every vote where she broke with the Democratic majority
- Full searchable record with party breakdowns, plus CSV/JSON download
- Light/dark theme aware; every chart has a screen-reader-friendly data-table twin

## Running locally

```bash
python3 scripts/fetch_votes.py          # incremental — only fetches new roll calls
python3 scripts/fetch_votes.py --full   # refetch everything (picks up corrections)

# preview the dashboard
python3 -m http.server -d . 8000
# then open http://localhost:8000/docs/ … the page loads ../data via the workflow
# layout; for a faithful preview: cd into a scratch dir mirroring the deploy layout,
# or just run:  (cd docs && ln -sfn ../data data) && python3 -m http.server 8000
```

## One-time GitHub setup

1. **Settings → Pages → Build and deployment → Source: “GitHub Actions.”**
2. That's it — the workflow deploys on every push to `main` and refreshes data twice
   a day (06:17 & 18:17 UTC). You can also trigger it manually from the Actions tab.

## Definitions

- **Party unity** — share of her Yea/Nay votes matching the majority position of
  voting House Democrats on that roll call. Quorum calls, Present, Not Voting, and
  Speaker elections are excluded.
- **Pass/fail** — the Clerk's `vote-result`, bucketed: anything starting with
  “Passed/Agreed to” counts as Pass.

Data is unofficial and provided for research; verify against
[clerk.house.gov/Votes](https://clerk.house.gov/Votes) before citing.
