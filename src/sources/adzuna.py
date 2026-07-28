"""
Adzuna job search API. Free tier: https://developer.adzuna.com/
"""
import requests
from src.config import env


def fetch_jobs(what: str, where: str, country: str = "in", pages: int = 2) -> list[dict]:
    app_id = env("ADZUNA_APP_ID")
    app_key = env("ADZUNA_APP_KEY")
    jobs = []
    for page in range(1, pages + 1):
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": what,
            "where": where,
            "results_per_page": 50,
            "content-type": "application/json",
        }
        resp = requests.get(url, params=params, timeout=20)
        if not resp.ok:
            break
        results = resp.json().get("results", [])
        if not results:
            break
        for r in results:
            jobs.append(
                {
                    "company": (r.get("company") or {}).get("display_name", "Unknown"),
                    "role_title": r.get("title", ""),
                    "location": (r.get("location") or {}).get("display_name", ""),
                    "jd_text": r.get("description", ""),
                    "jd_link": r.get("redirect_url", ""),
                    "salary_min": r.get("salary_min"),
                    "salary_max": r.get("salary_max"),
                    "ats_type": "adzuna_aggregated",
                }
            )
    return jobs
