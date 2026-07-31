"""
Ashby public job board API: https://api.ashbyhq.com/posting-api/job-board/<slug>
No auth needed for read access. Slug is the path segment in jobs.ashbyhq.com/<slug>
-- e.g. https://jobs.ashbyhq.com/smallest -> slug = "smallest".

Response schema (per Ashby's own public-job-posting-api docs): a top-level "jobs"
array, each with title, location, department, team, isRemote, workplaceType,
descriptionHtml/descriptionPlain, jobUrl, applyUrl, and (if includeCompensation=true)
a compensation block with a human-readable salary summary.

No public unauthenticated apply endpoint exists (Ashby's actual application API
requires a partner API key) -- Ashby jobs always land as "Staged" in Tier 2,
same as Lever.
"""
import requests
from tenacity import retry, wait_exponential, stop_after_attempt

ASHBY_JOB_BOARD_API = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"


@retry(wait=wait_exponential(multiplier=1, min=2, max=20), stop=stop_after_attempt(3))
def fetch_jobs(board_slug: str) -> list[dict]:
    url = ASHBY_JOB_BOARD_API.format(slug=board_slug)
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for j in data.get("jobs", []):
        location = j.get("location", "")
        if j.get("isRemote"):
            location = location or "Remote"

        salary_text = ""
        compensation = j.get("compensation") or {}
        if compensation:
            salary_text = (
                compensation.get("scrapeableCompensationSalarySummary")
                or compensation.get("compensationTierSummary", "")
            )

        jobs.append({
            "company": board_slug,
            "role_title": j.get("title", ""),
            "location": location,
            "department": j.get("department", ""),
            "jd_text": j.get("descriptionPlain", "") or j.get("descriptionHtml", ""),
            "jd_link": j.get("jobUrl", ""),
            "apply_url": j.get("applyUrl", ""),
            "salary_text": salary_text,  # free-text, not parsed to LPA -- see note in tier2_pipeline._salary_lpa
            "ats_type": "ashby",
            "board_token": board_slug,
        })
    return jobs
