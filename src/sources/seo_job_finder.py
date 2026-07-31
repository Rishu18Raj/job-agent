"""
Generalized job discovery via two widely-used SEO conventions (required for a
site to appear in Google's "Jobs" search feature, which is why most serious
corporate career sites -- even fully bespoke ones -- implement at least one):

1. An XML sitemap listing individual job URLs (sitemap.xml, sitemap_index.xml,
   or a jobs-specific sitemap linked from those).
2. JSON-LD JobPosting structured data embedded in each job's page <head>.

This is the SAME mechanism that makes Keka's job detail pages scrapable (see
src/sources/keka.py) -- generalized here so it can be tried against any
company's career site, not just known-ATS platforms. It will not work for
every company (some skip structured data entirely, or actively block bots),
but it's a real, non-guessy detection method, not a heuristic keyword scan.
"""
import re
import json
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from tenacity import retry, wait_exponential, stop_after_attempt

SITEMAP_PATH_CANDIDATES = [
    "/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml",
    "/careers/sitemap.xml", "/careers-sitemap.xml", "/jobs-sitemap.xml", "/sitemap-jobs.xml",
]
JOB_URL_HINTS = ["job", "career", "position", "opening", "role", "vacan"]


@retry(wait=wait_exponential(multiplier=1, min=2, max=15), stop=stop_after_attempt(3))
def _fetch(url: str) -> requests.Response:
    return requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})


def _root_domain(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def find_job_urls_via_sitemap(careers_url: str) -> list[str]:
    """Tries common sitemap paths against the site's root domain. If a sitemap
    is itself an index (points to sub-sitemaps), follows one level deep into
    any sub-sitemap whose URL looks job-related."""
    root = _root_domain(careers_url)
    job_urls = set()

    for path in SITEMAP_PATH_CANDIDATES:
        url = root + path
        try:
            resp = _fetch(url)
        except requests.RequestException:
            continue
        if not resp.ok or "<url" not in resp.text.lower():
            continue

        # sitemap index -> follow job-related sub-sitemaps one level deep
        sub_sitemaps = re.findall(r"<loc>(.*?sitemap.*?)</loc>", resp.text, re.IGNORECASE)
        job_sub_sitemaps = [s for s in sub_sitemaps if any(h in s.lower() for h in JOB_URL_HINTS)]
        if job_sub_sitemaps:
            for sub_url in job_sub_sitemaps[:3]:  # cap to avoid runaway crawling
                try:
                    sub_resp = _fetch(sub_url)
                    if sub_resp.ok:
                        job_urls.update(_extract_job_like_locs(sub_resp.text))
                except requests.RequestException:
                    continue

        job_urls.update(_extract_job_like_locs(resp.text))

        if job_urls:
            break  # first working sitemap wins, no need to try the rest

    return sorted(job_urls)


def _extract_job_like_locs(sitemap_xml: str) -> set[str]:
    all_locs = re.findall(r"<loc>(.*?)</loc>", sitemap_xml, re.IGNORECASE)
    return {loc for loc in all_locs if any(h in loc.lower() for h in JOB_URL_HINTS) and not loc.lower().endswith(".xml")}


def extract_jobposting_jsonld(job_url: str) -> dict | None:
    """Returns {'title', 'description', 'location'} if JSON-LD JobPosting schema
    is present, else None (caller should fall back to plain-text extraction)."""
    try:
        resp = _fetch(job_url)
        if not resp.ok:
            return None
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                title = item.get("title", "")
                desc_raw = item.get("description", "")
                desc = BeautifulSoup(desc_raw, "html.parser").get_text(separator=" ", strip=True)
                loc = ""
                job_location = item.get("jobLocation")
                if isinstance(job_location, dict):
                    addr = job_location.get("address", {})
                    if isinstance(addr, dict):
                        loc = addr.get("addressLocality", "") or addr.get("addressRegion", "")
                return {"title": title, "description": desc, "location": loc}
    return None
