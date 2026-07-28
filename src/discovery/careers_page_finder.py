"""
Best-effort careers-page discovery for Tier 1 firms, without a search API.

Guesses a domain from the company name, then probes common careers-page paths.
This is inherently weaker than the Tier 2 ATS probing -- multi-word firm names
(consulting, banks) often don't map cleanly to a domain (e.g. "McKinsey & Company"
is mckinsey.com, not mckinseyandcompany.com). Failures are flagged for manual
entry, never silently guessed and left wrong.
"""
import re
import requests

COMMON_PATHS = ["/careers", "/careers/", "/en/careers", "/company/careers", "/about/careers", "/jobs"]
COMMON_TLDS = [".com", ".in"]


def _domain_variants(company_name: str) -> list[str]:
    base = company_name.lower().strip()
    no_punct = re.sub(r"[^\w\s-]", "", base)
    no_space = re.sub(r"\s+", "", no_punct)
    first_word = no_punct.split()[0] if no_punct.split() else no_space

    seen = []
    for v in [no_space, first_word]:
        if v and v not in seen:
            seen.append(v)
    return seen


def discover_careers_page(company_name: str) -> dict:
    for domain_base in _domain_variants(company_name):
        for tld in COMMON_TLDS:
            domain = f"https://www.{domain_base}{tld}"
            for path in COMMON_PATHS:
                url = domain + path
                try:
                    resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
                    if resp.ok and any(kw in resp.text.lower() for kw in ["career", "job", "opening", "position"]):
                        return {
                            "name": company_name,
                            "board_type": "custom",
                            "careers_url": resp.url,  # follow redirects to final URL
                            "needs_manual_review": False,
                            "discovery_note": f"auto-matched via {domain_base}{tld}{path}",
                        }
                except requests.RequestException:
                    continue

    return {
        "name": company_name,
        "board_type": "custom",
        "careers_url": "REPLACE_WITH_CAREERS_URL",
        "needs_manual_review": True,
        "discovery_note": "domain/path guessing failed -- find the careers URL manually and paste it in",
    }
