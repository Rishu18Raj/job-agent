"""
Tier 1 firm scanner -- rebuilt to return real individual job listings via the
sitemap + JSON-LD JobPosting technique (src/sources/seo_job_finder.py), instead
of a page-level "these keywords appear somewhere on this page" check.

Falls back to a generic link-scrape (title text only, no full JD) if no sitemap
is found. Only falls back to "check manually" if NEITHER approach finds anything
-- which now actually means the site is JS-rendered/bot-blocked, not just "we
didn't bother parsing it."

Per-role relevance filtering (not just page-level) means a firm with 200 open
roles, only 3 of which are finance/strategy-relevant, now surfaces those 3 --
not a single vague "this page mentions banking somewhere" row.
"""
import requests
from bs4 import BeautifulSoup
from src.sources import seo_job_finder

RELEVANT_KEYWORDS = [
    "investment banking", "debt capital markets", "corporate finance", "strategy",
    "chief of staff", "corporate development", "consulting", "financial advisory",
    "m&a", "fundraising", "private equity", "credit", "capital markets",
    "associate", "analyst", "manager",  # seniority-adjacent, combined with sector words below is what matters
]
CORE_FINANCE_KEYWORDS = [
    "investment banking", "debt capital markets", "corporate finance", "corporate development",
    "financial advisory", "m&a", "fundraising", "private equity", "capital markets",
    "consulting", "strategy",
]


def _is_relevant(title: str, snippet: str = "") -> bool:
    text = f"{title} {snippet}".lower()
    return any(kw in text for kw in CORE_FINANCE_KEYWORDS)


def _scan_via_sitemap(firm_name: str, careers_url: str) -> list[dict]:
    job_urls = seo_job_finder.find_job_urls_via_sitemap(careers_url)
    if not job_urls:
        return []

    results = []
    for url in job_urls[:100]:  # cap per firm per run to keep runtime sane
        parsed = seo_job_finder.extract_jobposting_jsonld(url)
        if not parsed or not parsed["title"]:
            continue
        if not _is_relevant(parsed["title"], parsed["description"]):
            continue
        results.append({
            "company": firm_name,
            "role_title": parsed["title"],
            "function": ", ".join(kw for kw in CORE_FINANCE_KEYWORDS if kw in f"{parsed['title']} {parsed['description']}".lower())[:200],
            "location": parsed["location"],
            "jd_link": url,
        })
    return results


def _scan_via_generic_links(firm_name: str, careers_url: str) -> list[dict]:
    try:
        resp = requests.get(careers_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        if not title or not _is_relevant(title):
            continue
        href = a["href"]
        full_url = href if href.startswith("http") else careers_url.rstrip("/") + "/" + href.lstrip("/")
        results.append({
            "company": firm_name,
            "role_title": title,
            "function": ", ".join(kw for kw in CORE_FINANCE_KEYWORDS if kw in title.lower()),
            "location": "",
            "jd_link": full_url,
        })
    return results[:50]


def scan_firm(firm_name: str, careers_url: str) -> list[dict]:
    results = _scan_via_sitemap(firm_name, careers_url)
    if results:
        return results

    results = _scan_via_generic_links(firm_name, careers_url)
    if results:
        return results

    return [{
        "company": firm_name,
        "role_title": "[no sitemap/job-schema found and no relevant links in static HTML -- "
                       "site is likely JS-rendered or bot-blocked, check manually]",
        "function": "",
        "location": "",
        "jd_link": careers_url,
    }]
