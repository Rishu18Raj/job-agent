# Job Agent

Personal job-matching pipeline. Three tiers, three cadences, one Google Sheet as the tracker.

## Architecture

| Tier | Sources | Cadence | Scoring | Output |
|---|---|---|---|---|
| 1 — Bulge bracket / Big 4 / Consulting | Company career pages (auto-discovered) | Daily | Light keyword relevance only | Sheet1, reference only (you apply via referral) |
| 2 — Series B+ ATS boards | Greenhouse, Lever (auto-discovered), Workday, generic | Every 6 hours | Full P1 (skills, LLM) + P2 (logistics, rules) | Sheet2 + email if match ≥ 75%, auto-apply on Greenhouse/Lever, staged for Darwinbox/Wellforce |
| 3 — Seed/Series A discovery | Inc42 + YourStory funding RSS | Daily | Company-fit (funding size/stage/location), not job-fit | Sheet3 + email, founder LinkedIn surfaced for manual verification |

## Company list workflow (Tier 1 & Tier 2)

You maintain two plain-text files, one company name per line:
- `data/tier2_companies.txt`
- `data/tier1_companies.txt`

Two scheduled workflows run daily, each diffing the `.txt` against the corresponding
YAML (`config/companies_tier2.yaml` / `config/companies_tier1.yaml`), and for any
company present in the `.txt` but missing from the YAML, auto-discover its ATS
(Tier 2) or careers page (Tier 1):

- **Tier 2** (`src/discovery/company_ats_finder.py`): probes Greenhouse/Lever public
  APIs against several slug variants of the company name. No search API needed.
  Workday/Darwinbox are never auto-guessed (too unreliable) -- always flagged
  `needs_manual_review: true`.
- **Tier 1** (`src/discovery/careers_page_finder.py`): guesses a domain from the
  company name and probes common careers-page paths. Weaker than Tier 2 -- expect
  a higher `needs_manual_review` rate for multi-word firm names.

Entries flagged `needs_manual_review: true` are **skipped by the scan pipelines**
until you fix them by hand (correct `token`/`careers_url`) -- they never silently
scan a wrong or placeholder URL.

The sync workflows also trigger immediately on a push that touches either `.txt`
file, so you don't have to wait for the next scheduled run after adding companies.

## Repo layout

```
data/tier1_companies.txt    # Tier 1 firm names, one per line -- edit this to add firms
data/tier2_companies.txt    # Tier 2 company names, one per line -- edit this to add companies
config/companies_tier1.yaml # auto-populated from the .txt above
config/companies_tier2.yaml # auto-populated from the .txt above
config/profile.yaml         # your resume data, scoring weights, thresholds
src/discovery/               company_ats_finder.py = Tier 2 ATS auto-detection
                              careers_page_finder.py = Tier 1 careers-page auto-detection
src/sources/                 scrapers/API clients per ATS type
src/scoring/                 p1_skills.py = Gemini call for skills/sector score
                              p2_logistics.py = rule-based scoring, exact thresholds from our spec
src/sheets/                  Google Sheets API client (writes rows)
src/notify/                  Email sender (Gmail SMTP)
src/state/                   SQLite dedup store, prevents re-notifying on the same JD
src/resume/                  Resume tailoring (LLM-based) for Tier 2 auto-apply
src/outreach/                 Founder LinkedIn discovery via search, Tier 3
src/tier1_pipeline.py        Entry point, run by tier1-daily.yml
src/tier2_pipeline.py        Entry point, run by tier2-6hourly.yml
src/tier3_pipeline.py        Entry point, run by tier3-daily.yml
src/sync_tier1_companies.py  Entry point, run by sync-tier1-companies.yml
src/sync_tier2_companies.py  Entry point, run by sync-tier2-companies.yml
```

## One-time setup (do these before the first run)

### 1. Google Sheet
- Create a new Google Sheet with 3 tabs named exactly: `Tier1`, `Tier2`, `Tier3`.
- Add header rows matching the schemas in `config/profile.yaml` → `sheet_schemas` (or just let the first pipeline run write them).
- Copy the Sheet ID from its URL (`docs.google.com/spreadsheets/d/<THIS_PART>/edit`).

### 2. Google Cloud service account (lets the pipeline write to the Sheet headlessly)
1. Go to console.cloud.google.com → new project (or reuse one).
2. Enable the **Google Sheets API**.
3. IAM & Admin → Service Accounts → Create → download the JSON key.
4. Open your Google Sheet → Share → paste the service account's email (looks like `xxx@xxx.iam.gserviceaccount.com`) → give it Editor access.
5. Store the JSON key contents as a GitHub Actions secret: `GOOGLE_SERVICE_ACCOUNT_JSON`.

### 3. Gmail sending
- Simplest path: a Gmail **App Password** (Google Account → Security → 2-Step Verification → App Passwords), used over SMTP. No OAuth flow needed.
- Store as secrets: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`.

### 4. Gemini via Vertex AI (for P1 scoring + resume tailoring)
- Uses the **same service account** created in step 2 -- just add it the "Vertex AI User" (`roles/aiplatform.user`) IAM role in Cloud Console → IAM & Admin → IAM.
- Enable the Vertex AI API on that project if prompted.
- Store as secrets: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` (e.g. `us-central1`).

### 5. Company lists
- Paste your actual company names into `data/tier2_companies.txt` and `data/tier1_companies.txt`
  (one per line -- see the templates already in each file).
- On first push, the sync workflows will run and auto-discover ATS/careers URLs for
  each. Check `config/companies_tier2.yaml` / `config/companies_tier1.yaml` afterward
  for any `needs_manual_review: true` entries and fix those by hand.

### 5. GitHub repo secrets
Add these under Settings → Secrets and variables → Actions:
- `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` (Gemini via Vertex AI, same service account as Sheets -- needs the "Vertex AI User" / `roles/aiplatform.user` IAM role)
- `SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `NOTIFY_TO`

## Running locally (for testing before you trust the scheduled runs)

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in the same values as the GitHub secrets
python -m src.tier2_pipeline
```

## Known limitations / things to verify before trusting unattended auto-apply

- Greenhouse/Lever form-POST auto-apply is implemented but **untested against live listings** — first several runs should leave `AUTO_APPLY_ENABLED=false` in `.env` so everything lands in the sheet as "Staged" instead of actually submitting. Flip it on once you've manually verified a few staged applications look correct.
- Darwinbox and Wellfound do not have reliable unauthenticated apply endpoints — those always land as "Staged," by design, not a bug.
- Founder LinkedIn discovery is a Google search heuristic, not a verified match — always shown as "unverified" in the sheet.
