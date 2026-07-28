"""
Greenhouse public job board API client.
No auth needed for read access: https://boards-api.greenhouse.io/v1/boards/<token>/jobs
Company token is the slug in their board URL, e.g. boards.greenhouse.io/stripe -> "stripe"
"""
import requests
from tenacity import retry, wait_exponential, stop_after_attempt


@retry(wait=wait_exponential(multiplier=1, min=2, max=20), stop=stop_after_attempt(3))
def fetch_jobs(board_token: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    jobs = []
    for j in data.get("jobs", []):
        jobs.append(
            {
                "company": board_token,
                "role_title": j.get("title", ""),
                "location": (j.get("location") or {}).get("name", ""),
                "jd_text": j.get("content", ""),
                "jd_link": j.get("absolute_url", ""),
                "job_id": j.get("id"),
                "ats_type": "greenhouse",
                "board_token": board_token,
            }
        )
    return jobs


def submit_application(board_token: str, job_id: int, applicant: dict, resume_path: str) -> dict:
    """
    Greenhouse job-board POST endpoint for applications.
    NOTE: exact required fields vary per job (custom questions). This posts the
    standard fields; custom-question jobs will fail and should fall back to "Staged".
    Only call this when AUTO_APPLY_ENABLED=true and after manual verification.
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}/applications"
    with open(resume_path, "rb") as f:
        files = {"resume": f}
        payload = {
            "first_name": applicant["first_name"],
            "last_name": applicant["last_name"],
            "email": applicant["email"],
            "phone": applicant.get("phone", ""),
        }
        resp = requests.post(url, data=payload, files=files, timeout=30)
    return {"status_code": resp.status_code, "ok": resp.ok, "body": resp.text[:500]}
