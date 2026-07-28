"""
Workday doesn't have one universal public API the way Greenhouse/Lever do -- each
tenant runs at <tenant>.wd1(.wd3/wd5 etc).myworkdayjobs.com/<site>, and most (not all)
expose a JSON endpoint at .../wday/cxs/<tenant>/<site>/jobs that accepts a POST.

This is best-effort: if a company's Workday instance doesn't follow the standard
pattern, this will return an empty list and should be checked manually.
"""
import re
import requests
from tenacity import retry, wait_exponential, stop_after_attempt


def _parse_workday_url(careers_url: str) -> dict | None:
    # e.g. https://mycompany.wd1.myworkdayjobs.com/en-US/Careers
    m = re.match(r"https?://([\w-]+)\.(wd\d)\.myworkdayjobs\.com/(?:[\w-]+/)?([\w-]+)", careers_url)
    if not m:
        return None
    tenant, wd_shard, site = m.groups()
    return {"tenant": tenant, "shard": wd_shard, "site": site}


@retry(wait=wait_exponential(multiplier=1, min=2, max=20), stop=stop_after_attempt(3))
def fetch_jobs(careers_url: str, company_name: str) -> list[dict]:
    parsed = _parse_workday_url(careers_url)
    if parsed is None:
        return [{
            "company": company_name,
            "role_title": "[Workday URL pattern not recognized -- check manually]",
            "jd_link": careers_url,
        }]

    api_url = (
        f"https://{parsed['tenant']}.{parsed['shard']}.myworkdayjobs.com"
        f"/wday/cxs/{parsed['tenant']}/{parsed['site']}/jobs"
    )
    resp = requests.post(api_url, json={"limit": 50, "offset": 0}, timeout=20)
    if not resp.ok:
        return [{
            "company": company_name,
            "role_title": f"[Workday API returned {resp.status_code} -- check manually]",
            "jd_link": careers_url,
        }]

    postings = resp.json().get("jobPostings", [])
    jobs = []
    for p in postings:
        jobs.append({
            "company": company_name,
            "role_title": p.get("title", ""),
            "location": p.get("locationsText", ""),
            "jd_text": p.get("bulletFields", []) and " ".join(p["bulletFields"]) or p.get("title", ""),
            "jd_link": careers_url.rstrip("/") + p.get("externalPath", ""),
            "ats_type": "workday",
        })
    return jobs
