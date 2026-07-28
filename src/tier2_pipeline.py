from datetime import date
from src.config import load_profile, AUTO_APPLY_ENABLED
from src.sources import company_router
from src.scoring.p1_skills import score_p1
from src.scoring.p2_logistics import score_p2
from src.sheets.sheets_client import append_row, add_note_to_cell
from src.notify.email_notify import send_match_email
from src.resume.tailor import generate_tailoring_brief
from src.state.dedup_store import is_seen, mark_seen


def collect_jobs(profile: dict) -> list[dict]:
    jobs = company_router.fetch_all_jobs()
    # Filter out the "[...check manually / fetch error...]" placeholder rows before
    # scoring -- they have no real jd_text and would waste an LLM call for nothing.
    real_jobs = [j for j in jobs if not j["role_title"].startswith("[")]
    flagged = [j for j in jobs if j["role_title"].startswith("[")]

    for f in flagged:
        print(f"[needs manual check] {f['company']}: {f['role_title']} -> {f.get('jd_link', '')}")

    return real_jobs


def _salary_lpa(job: dict) -> float | None:
    # Adzuna gives annual INR salary_min/max in some listings; Greenhouse/Lever rarely disclose.
    if job.get("salary_min"):
        return job["salary_min"] / 100000  # INR -> LPA
    return None


def run():
    profile = load_profile()
    thresholds = profile["scoring"]["action_thresholds"]
    jobs = collect_jobs(profile)

    for job in jobs:
        company = job["company"]
        role = job["role_title"]
        jd_link = job["jd_link"]

        if is_seen(company, role, jd_link):
            continue

        p2 = score_p2(job["jd_text"], role, job.get("location", ""), _salary_lpa(job))
        if p2["hard_reject"]:
            mark_seen("Tier2", company, role, jd_link)
            continue

        p1 = score_p1(job["jd_text"])
        if p1["hard_reject"]:
            mark_seen("Tier2", company, role, jd_link)
            continue

        composite = profile["scoring"]["composite"]
        overall = p1["p1_score"] * composite["p1_weight"] + p2["p2_score"] * composite["p2_weight"]

        if overall < thresholds["log_only_min"]:
            mark_seen("Tier2", company, role, jd_link)
            continue

        auto_apply_status = "Below auto-apply threshold" if overall < thresholds["surface_and_notify_min"] else "Staged"
        tailored_resume_note = ""
        if overall >= thresholds["surface_and_notify_min"]:
            tailored_resume_note = generate_tailoring_brief(job["jd_text"])
            if AUTO_APPLY_ENABLED and job.get("ats_type") in ("greenhouse", "lever"):
                auto_apply_status = "Staged (auto-apply wiring present but verify before enabling live submit)"

        row_number = append_row("Tier2", {
            "Date Found": str(date.today()),
            "Company": company,
            "Role Title": role,
            "Overall Match %": round(overall, 1),
            "P1 Score": p1["p1_score"],
            "P2 Score": p2["p2_score"],
            "Location": job.get("location", ""),
            "Salary (if disclosed)": _salary_lpa(job) or "",
            "JD Link": jd_link,
            "ATS Type": job.get("ats_type", ""),
            "Auto-Apply Status": auto_apply_status,
            "Tailored Resume Link": tailored_resume_note,
            "Status": "New",
        })

        # P1 sub-score breakdown goes in a cell note per our schema decision, not its own column
        add_note_to_cell("Tier2", row_number, "P1 Score", str(p1["sub_scores"]))

        if overall >= thresholds["surface_and_notify_min"]:
            send_match_email(company, role, overall, jd_link, tier="Tier2")

        mark_seen("Tier2", company, role, jd_link)


if __name__ == "__main__":
    run()
