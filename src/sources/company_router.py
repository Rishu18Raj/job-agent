import yaml
from pathlib import Path
from src.sources import greenhouse, lever, workday, freshteam, keka, generic_scraper

ROOT = Path(__file__).resolve().parent.parent.parent


def load_companies() -> list[dict]:
    with open(ROOT / "config" / "companies_tier2.yaml", "r") as f:
        data = yaml.safe_load(f)
    return data.get("companies", [])


def fetch_all_jobs() -> list[dict]:
    companies = load_companies()
    all_jobs = []

    for c in companies:
        if c.get("needs_manual_review"):
            print(f"[needs manual review] {c['name']}: {c.get('discovery_note', '')} -- skipping until token/URL is fixed")
            continue

        ats = c["ats"]
        token = c["token"]
        name = c["name"]

        try:
            if ats == "greenhouse":
                jobs = greenhouse.fetch_jobs(token)
            elif ats == "lever":
                jobs = lever.fetch_jobs(token)
            elif ats == "workday":
                jobs = workday.fetch_jobs(token, name)
            elif ats == "freshteam":
                jobs = freshteam.fetch_jobs(token)  # token = company_slug here
            elif ats == "keka":
                # token = company slug (or full careers URL, both accepted) -- see
                # src/sources/keka.py for the sitemap-based detection this relies on
                jobs = keka.fetch_jobs(token, name)
            elif ats == "darwinbox":
                # No stable public API -- Darwinbox instances are heavily client-specific
                # and gated behind privileged/OAuth access. Routed through the generic
                # scraper; expect this to often flag "needs manual check" rather than
                # return real postings.
                jobs = generic_scraper.fetch_jobs(token, name)
            elif ats == "generic":
                jobs = generic_scraper.fetch_jobs(token, name)
            else:
                jobs = [{
                    "company": name,
                    "role_title": f"[unknown ats type '{ats}' in config -- fix companies_tier2.yaml]",
                    "jd_link": token,
                }]
        except Exception as e:
            jobs = [{
                "company": name,
                "role_title": f"[fetch error: {e}]",
                "jd_link": token,
            }]

        # normalize company name to the configured display name, not the ATS token
        for j in jobs:
            j["company"] = name

        all_jobs.extend(jobs)

    return all_jobs
