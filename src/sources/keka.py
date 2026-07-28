"""
Keka career sites turn out to have a real, reliable scraping path -- just not the
one I assumed originally:

- The job LISTING page (https://{slug}.keka.com/careers) is client-side rendered
  (JS), so a plain GET returns an empty shell -- confirmed by direct inspection.
- Individual job DETAIL pages (https://{slug}.keka.com/careers/jobdetails/{id})
  ARE server-rendered with full content (title, experience band, location,
  employment type, full JD text) -- also confirmed by direct inspection. Keka
  does this for SEO.
- To enumerate job IDs without the JS-rendered list, this tries the site's
  sitemap.xml (a near-universal SEO convention) and extracts /careers/jobdetails/{id}
  URLs from it. This is a genuine, reasonably reliable mechanism when the sitemap
  exists -- NOT a guess -- but some Keka sites may not publish one, in which case
  this correctly falls back to "needs manual check" rather than guessing job IDs.
"""
import re
import requests
from bs4 import BeautifulSoup
from tenacity import retry, wait_exponential, stop_after_attempt

SITEMAP_CANDIDATES = ["https://{slug}.keka.com/sitemap.xml", "https://{slug}.keka.com/careers/sitemap.xml"]
JOB_DETAIL_PATTERN = re.compile(r"https?://[\w.-]+\.keka\.com/careers/jobdetails/\d+")


@retry(wait=wait_exponential(multiplier=1, min=2, max=15), stop=stop_after_attempt(3))
def _fetch(url: str) -> requests.Response:
    return requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})


def _find_job_urls_via_sitemap(slug: str) -> list[str]:
    for template in SITEMAP_CANDIDATES:
        url = template.format(slug=slug)
        try:
            resp = _fetch(url)
            if resp.ok and "<url" in resp.text.lower():
                matches = JOB_DETAIL_PATTERN.findall(resp.text)
                if matches:
                    return sorted(set(matches))
        except requests.RequestException:
            continue
    return []


def _parse_job_detail(job_url: str) -> dict | None:
    try:
        resp = _fetch(job_url)
        if not resp.ok:
            return None
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    if not title or "not available anymore" in resp.text.lower():
        return None  # expired/deleted posting

    # Full body text as JD -- Keka doesn't use predictable class names across tenants,
    # so this takes the whole page text rather than guessing selectors. Good enough
    # for LLM scoring even if it includes some nav/footer noise.
    jd_text = soup.get_text(separator=" ", strip=True)

    return {"role_title": title, "jd_text": jd_text, "jd_link": job_url}


def fetch_jobs(slug_or_url: str, company_name: str) -> list[dict]:
    # Accept either a bare slug ("jupiter") or a full careers URL for backward compat --
    # extract the slug either way.
    m = re.search(r"https?://([\w-]+)\.keka\.com", slug_or_url)
    slug = m.group(1) if m else slug_or_url

    job_urls = _find_job_urls_via_sitemap(slug)
    if not job_urls:
        return [{
            "company": company_name,
            "role_title": "[no sitemap found / no jobs in sitemap -- Keka job list is JS-rendered "
                           "and can't be scraped without one, check manually]",
            "jd_link": f"https://{slug}.keka.com/careers",
            "ats_type": "keka",
        }]

    jobs = []
    for url in job_urls:
        parsed = _parse_job_detail(url)
        if parsed:
            jobs.append({
                "company": company_name,
                "role_title": parsed["role_title"],
                "location": "",  # not reliably separable from body text across tenants
                "jd_text": parsed["jd_text"],
                "jd_link": parsed["jd_link"],
                "ats_type": "keka",
            })
    return jobs
