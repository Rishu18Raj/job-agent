"""
Best-effort scraper for career pages that aren't on a recognized ATS.

IMPORTANT LIMITATION: this does a plain HTTP GET + static HTML parse. Many modern
career pages (React/Vue/Next.js SPAs) load job listings via a client-side JS fetch
after the page loads -- a static GET will see an empty shell and find nothing.
This function does NOT pretend to succeed in that case: it returns a single
"needs manual check" row rather than silently returning zero jobs, so it shows up
in the Tier 2 sheet as something to look at rather than vanishing.

If you hit this often, the fix is either:
1. Find the underlying ATS (many "custom" pages are Greenhouse/Lever underneath --
   check Network tab in browser devtools for calls to boards-api.greenhouse.io etc)
2. Add a headless-browser rendering step (Playwright) -- not included here to keep
   the GitHub Actions runner lightweight and fast; can be added if this becomes
   the dominant case for your company list.
"""
import requests
from bs4 import BeautifulSoup

JOB_LINK_HINTS = ["job", "career", "position", "opening", "role", "vacan"]


def fetch_jobs(careers_url: str, company_name: str) -> list[dict]:
    try:
        resp = requests.get(careers_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except requests.RequestException as e:
        return [{
            "company": company_name,
            "role_title": f"[fetch failed: {e}]",
            "jd_link": careers_url,
            "ats_type": "generic",
        }]

    soup = BeautifulSoup(resp.text, "html.parser")
    candidate_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text(strip=True)
        if any(hint in href for hint in JOB_LINK_HINTS) and text:
            candidate_links.append({"title": text, "href": a["href"]})

    if not candidate_links:
        return [{
            "company": company_name,
            "role_title": "[no job links found in static HTML -- likely JS-rendered, check manually]",
            "jd_link": careers_url,
            "ats_type": "generic",
        }]

    jobs = []
    for link in candidate_links[:30]:  # cap to avoid noise from nav/footer links
        full_url = link["href"] if link["href"].startswith("http") else careers_url.rstrip("/") + "/" + link["href"].lstrip("/")
        jobs.append({
            "company": company_name,
            "role_title": link["title"],
            "location": "",
            "jd_text": link["title"],  # static scrape rarely gets full JD text without a second fetch per link
            "jd_link": full_url,
            "ats_type": "generic",
        })
    return jobs
