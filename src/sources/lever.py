"""
Lever public postings API: https://api.lever.co/v0/postings/<company>?mode=json
"""
import requests
from tenacity import retry, wait_exponential, stop_after_attempt


@retry(wait=wait_exponential(multiplier=1, min=2, max=20), stop=stop_after_attempt(3))
def fetch_jobs(company_token: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{company_token}?mode=json"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    postings = resp.json()
    jobs = []
    for p in postings:
        jobs.append(
            {
                "company": company_token,
                "role_title": p.get("text", ""),
                "location": (p.get("categories") or {}).get("location", ""),
                "jd_text": p.get("descriptionPlain", "") or p.get("description", ""),
                "jd_link": p.get("hostedUrl", ""),
                "job_id": p.get("id"),
                "ats_type": "lever",
                "board_token": company_token,
            }
        )
    return jobs


def submit_application(company_token: str, job_id: str, applicant: dict, resume_path: str) -> dict:
    """
    Lever's public apply endpoint requires a per-posting apply token that must
    first be fetched from the postings page itself -- it is NOT a stable, documented
    API and breaks easily. Treat this as best-effort; verify manually before trusting it.
    """
    posting_url = f"https://api.lever.co/v0/postings/{company_token}/{job_id}?mode=json"
    resp = requests.get(posting_url, timeout=20)
    if not resp.ok:
        return {"ok": False, "reason": "could not fetch posting for apply token"}
    apply_url = resp.json().get("applyUrl")
    return {"ok": False, "reason": "manual submission required", "apply_url": apply_url}
