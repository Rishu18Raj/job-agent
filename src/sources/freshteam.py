"""
Freshteam has no official public REST API, but its hosted career page at
https://{slug}.freshteam.com/jobs is plain server-rendered HTML with job data
embedded in data-portal-* attributes on each job link -- no auth needed, no JS
rendering required. This is a real, reliably working scraper (unlike Keka/Darwinbox).

For full JD text we do one extra fetch per job and pull the schema.org JobPosting
JSON-LD block that Freshteam embeds for SEO, when present.
"""
import json
import re
import requests
from bs4 import BeautifulSoup
from tenacity import retry, wait_exponential, stop_after_attempt


@retry(wait=wait_exponential(multiplier=1, min=2, max=20), stop=stop_after_attempt(3))
def _fetch(url: str) -> requests.Response:
    return requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})


def _extract_jsonld_description(job_url: str) -> str:
    try:
        resp = _fetch(job_url)
        if not resp.ok:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                desc = data.get("description", "")
                # JSON-LD descriptions are often HTML-escaped fragments; strip tags
                return BeautifulSoup(desc, "html.parser").get_text(separator=" ", strip=True)
        return ""
    except requests.RequestException:
        return ""


def fetch_jobs(company_slug: str, fetch_full_jd: bool = True) -> list[dict]:
    listing_url = f"https://{company_slug}.freshteam.com/jobs"
    try:
        resp = _fetch(listing_url)
        resp.raise_for_status()
    except requests.RequestException as e:
        return [{
            "company": company_slug,
            "role_title": f"[fetch failed: {e}]",
            "jd_link": listing_url,
            "ats_type": "freshteam",
        }]

    soup = BeautifulSoup(resp.text, "html.parser")
    job_links = soup.select("a[data-portal-title]")

    if not job_links:
        return [{
            "company": company_slug,
            "role_title": "[no jobs found -- site may have changed its markup, check manually]",
            "jd_link": listing_url,
            "ats_type": "freshteam",
        }]

    jobs = []
    for a in job_links:
        title = a.get("data-portal-title", "").strip()
        location = a.get("data-portal-location", "").strip()
        department = a.get("data-portal-department", "").strip()
        href = a.get("href", "")
        full_url = href if href.startswith("http") else f"https://{company_slug}.freshteam.com{href}"

        jd_text = title
        if fetch_full_jd:
            jd_text = _extract_jsonld_description(full_url) or title

        jobs.append({
            "company": company_slug,
            "role_title": title,
            "location": location,
            "department": department,
            "jd_text": jd_text,
            "jd_link": full_url,
            "ats_type": "freshteam",
        })
    return jobs
