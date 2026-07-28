"""
Given a company name, tries to find its ATS by probing public endpoints/pages
with several slug variants -- no search API required.

Confidence tiers:
- Greenhouse/Lever/Freshteam/Keka: real structural detection. Greenhouse/Lever/Freshteam
  via their job-list endpoint/page returning parseable data; Keka via its sitemap.xml
  listing real /careers/jobdetails/{id} URLs (individual Keka job pages are server-rendered
  for SEO even though the listing page itself is JS-only -- see src/sources/keka.py).
  All four are auto-matched with genuine confidence, not guessed.
- Darwinbox: never auto-scanned. The pattern {slug}.darwinbox.in/ms/candidatev2/main/careers/home
  is pre-filled as a starting guess when nothing else matches, but Darwinbox career
  sites return bot-detection errors on non-browser requests (confirmed directly) --
  always flagged needs_manual_review regardless.
- Workday: auto-scanned only if the URL you already have fits the standard
  *.wdN.myworkdayjobs.com pattern (see src/sources/workday.py); not guessed from scratch here.
"""
import re
import requests
from src.sources import freshteam as freshteam_source

GREENHOUSE_JOBS_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
LEVER_POSTINGS_API = "https://api.lever.co/v0/postings/{slug}?mode=json"
FRESHTEAM_JOBS_URL = "https://{slug}.freshteam.com/jobs"


def _slug_variants(company_name: str) -> list[str]:
    base = company_name.lower().strip()
    no_punct = re.sub(r"[^\w\s-]", "", base)          # strip &, ., etc.
    no_space = re.sub(r"\s+", "", no_punct)             # "paytm payments services" -> "paytmpaymentsservices"
    hyphenated = re.sub(r"\s+", "-", no_punct.strip())  # "paytm-payments-services"
    first_word = no_punct.split()[0] if no_punct.split() else no_space

    # dedupe while preserving order
    seen = []
    for v in [no_space, hyphenated, first_word]:
        if v and v not in seen:
            seen.append(v)
    return seen


def _try_greenhouse(slug: str) -> dict | None:
    try:
        resp = requests.get(GREENHOUSE_JOBS_API.format(slug=slug), timeout=10)
        if resp.ok:
            data = resp.json()
            if isinstance(data.get("jobs"), list) and len(data["jobs"]) > 0:
                return {"ats": "greenhouse", "token": slug, "job_count": len(data["jobs"])}
    except requests.RequestException:
        pass
    return None


def _try_lever(slug: str) -> dict | None:
    try:
        resp = requests.get(LEVER_POSTINGS_API.format(slug=slug), timeout=10)
        if resp.ok:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return {"ats": "lever", "token": slug, "job_count": len(data)}
    except requests.RequestException:
        pass
    return None


def _try_freshteam(slug: str) -> dict | None:
    try:
        resp = requests.get(FRESHTEAM_JOBS_URL.format(slug=slug), timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.ok and 'data-portal-title' in resp.text:
            jobs = freshteam_source.fetch_jobs(slug, fetch_full_jd=False)
            real_jobs = [j for j in jobs if not j["role_title"].startswith("[")]
            if real_jobs:
                return {"ats": "freshteam", "token": slug, "job_count": len(real_jobs)}
    except requests.RequestException:
        pass
    return None


def _try_keka(slug: str) -> dict | None:
    """Real detection via sitemap.xml (see src/sources/keka.py for why this works).
    A miss here means no sitemap was found/published, not necessarily "not on Keka"."""
    from src.sources.keka import _find_job_urls_via_sitemap
    job_urls = _find_job_urls_via_sitemap(slug)
    if job_urls:
        return {"ats": "keka", "token": slug, "job_count": len(job_urls)}
    return None


def _guess_darwinbox_url(slug: str) -> str:
    # Pattern confirmed (e.g. delhivery.darwinbox.in/ms/candidatev2/main/careers/home) but
    # Darwinbox career sites actively return bot-detection errors on non-browser requests --
    # this URL is pre-filled to save you typing, NOT auto-scanned. Always needs_manual_review.
    return f"https://{slug}.darwinbox.in/ms/candidatev2/main/careers/home"


def discover_ats(company_name: str) -> dict:
    """Returns a dict ready to drop into companies_tier2.yaml."""
    variants = _slug_variants(company_name)

    for slug in variants:
        for prober in (_try_greenhouse, _try_lever, _try_freshteam, _try_keka):
            result = prober(slug)
            if result:
                return {
                    "name": company_name,
                    "ats": result["ats"],
                    "token": result["token"],
                    "needs_manual_review": False,
                    "discovery_note": f"auto-matched, {result['job_count']} live postings at discovery time",
                }

    if not variants:
        # Company name reduced to nothing after stripping punctuation/whitespace
        # (e.g. name was mostly symbols) -- can't even build a slug to guess with.
        return {
            "name": company_name,
            "ats": "generic",
            "token": "REPLACE_WITH_CAREERS_URL",
            "needs_manual_review": True,
            "discovery_note": f"could not derive a usable slug from the name '{company_name}' -- "
                               "fix the name in the .txt or fill in the careers URL by hand",
        }

    # No confirmed match anywhere. If a Darwinbox URL pattern is plausible, pre-fill it
    # to save typing -- but ALWAYS flag manual review, since Darwinbox career sites
    # return bot-detection errors on non-browser requests (confirmed) and can't be
    # auto-scanned regardless of whether the guess is right. ats is deliberately NOT
    # set to "darwinbox" here -- that would make it look auto-confirmed. It's labeled
    # "generic_darwinbox_guess" so the terminal output alone tells you what's going on,
    # without needing to cross-reference discovery_note.
    darwinbox_guess = _guess_darwinbox_url(variants[0])
    return {
        "name": company_name,
        "ats": "generic_darwinbox_guess",
        "token": darwinbox_guess,
        "needs_manual_review": True,
        "discovery_note": "not found on Greenhouse/Lever/Freshteam/Keka via probing. The token above is "
                           "an UNVERIFIED pattern-based guess for a possible Darwinbox URL -- open it in a "
                           "browser; if it's real, change ats to 'darwinbox' (still manual-only, see "
                           "company_router.py) and fix the token if the URL differs. If it 404s, this "
                           "company likely uses Workday or a custom page -- replace token with the real URL.",
    }
