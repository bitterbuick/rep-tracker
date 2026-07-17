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
| `scripts/score_risk.py` | Democracy-risk scorer (5×5 risk matrix, see below) |
| `config/risk_rubric.json` | Editable keyword rubric → impact scores |
| `config/risk_overrides.json` | Hand-curated per-vote score overrides |
| `data/salinas_votes.csv` | Flat export — roll, date, bill, subject, her vote, party breakdown, pass/fail |
| `data/salinas_votes.json` | Same data plus metadata |
| `data/salinas_votes_scored.csv/.json` | Above + risk columns, consumed by the dashboard |
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

## Hosting

The dashboard is served by GitHub Pages from the **`gh-pages` branch**, which the
workflow rebuilds and force-pushes on every deploy (branch publishing works with
the default workflow token; the Pages “GitHub Actions” source does not, because
`GITHUB_TOKEN` may not create the Pages site). If Pages ever needs re-enabling:
**Settings → Pages → Source: “Deploy from a branch” → `gh-pages` / (root)**.
Data refreshes twice a day (06:17 & 18:17 UTC); the workflow can also be run
manually from the Actions tab.

## Democracy-risk matrix

Each roll call is placed on a traditional 5×5 risk matrix scoring **exposure of
liberal-democratic institutions** — deliberately a transparent heuristic, not a
black-box judgment:

- **Impact (1–5)** — how democracy-relevant the measure is, from the keyword
  rubric in `config/risk_rubric.json` matched against the bill/question/subject:
  elections & voting rights (5), checks & balances / executive power (5),
  judiciary & rule of law (4), civil liberties & surveillance (4), civil rights
  (4), transparency & ethics (3), immigration enforcement (3), domestic use of
  force (3); everything else defaults to routine (1). The highest matching
  domain wins.
- **Likelihood / advancement (1–5)** — how far the vote actually moved the
  measure toward taking effect: failed (1); procedural or amendment win, incl.
  “providing for consideration” rules (2); House passage, Senate + president
  still ahead (3, or 4 with a veto-proof margin); veto override, concurrence
  sending a bill to the president, or a self-executing House resolution —
  impeachment articles, contempt findings, committee-creating rules (5).
- **Score = impact × likelihood**, banded **Low ≤ 4 · Moderate 5–9 ·
  High 10–16 · Critical ≥ 17**.

Three honest caveats, also shown in the dashboard footer:

1. The matrix scores **salience, not direction** — it flags that a vote touched
   democratic machinery, not which way. Her vote is displayed beside every
   flagged measure so readers judge direction themselves.
2. Keyword matching over the Clerk's terse vote descriptions **will miss
   measures whose titles hide their substance** (and occasionally over-flag).
   That is what `config/risk_overrides.json` is for: pin any vote's impact,
   likelihood, domain, or add a note, keyed `"<year>-<roll>"`. Overrides always
   win.
3. “Risk to liberal democracy” is an analytical lens, not a neutral fact. The
   rubric is in version control precisely so every scoring decision is
   inspectable, editable, and attributable.

Re-score after editing the rubric or overrides (no network needed):

```bash
python3 scripts/score_risk.py
```

## Definitions

- **Party unity** — share of her Yea/Nay votes matching the majority position of
  voting House Democrats on that roll call. Quorum calls, Present, Not Voting, and
  Speaker elections are excluded.
- **Pass/fail** — the Clerk's `vote-result`, bucketed: anything starting with
  “Passed/Agreed to” counts as Pass.

Data is unofficial and provided for research; verify against
[clerk.house.gov/Votes](https://clerk.house.gov/Votes) before citing.
