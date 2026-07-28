"""
Tier 1 firms mostly don't run Greenhouse/Lever -- their career pages are bespoke.
This does a lightweight fetch + text scan for finance/strategy keywords rather than
structured parsing. It is intentionally shallow: Tier 1's job is to produce a
reference list for warm-referral outreach, not to score/auto-apply.
"""
import requests
from bs4 import BeautifulSoup

RELEVANT_KEYWORDS = [
    "investment banking", "debt capital markets", "corporate finance", "strategy",
    "chief of staff", "corporate development", "consulting", "financial advisory",
    "m&a", "fundraising", "private equity", "credit",
]


def scan_firm(firm_name: str, careers_url: str) -> list[dict]:
    try:
        resp = requests.get(careers_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except requests.RequestException as e:
        return [{"company": firm_name, "role_title": f"[fetch failed: {e}]", "jd_link": careers_url}]

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(separator=" ", strip=True).lower()

    hits = [kw for kw in RELEVANT_KEYWORDS if kw in text]
    if not hits:
        return []

    # Most bespoke career sites need JS rendering to list individual roles, which this
    # lightweight scraper does not do. This returns a "check manually" flag rather than
    # fabricating individual role listings from a static-HTML scan.
    return [
        {
            "company": firm_name,
            "role_title": "[keywords matched -- review page manually for open roles]",
            "function": ", ".join(hits[:5]),
            "jd_link": careers_url,
        }
    ]
