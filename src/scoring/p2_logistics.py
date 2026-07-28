import re
from src.config import load_profile

HARD_REJECT = "HARD_REJECT"


def _score_title(jd_text: str, jd_title: str, profile: dict) -> float | str:
    cfg = profile["candidate"]["seniority_titles_match"]
    scores = profile["scoring"]["p2_logistics"]["seniority_title_scores"]
    text = f"{jd_title} {jd_text}".lower()

    # "Chief of Staff" / "Founder's Office" style titles are explicitly in-scope (Tier 3
    # stretch roles) -- don't let the substring "chief" trigger a reject for them.
    is_chief_of_staff = "chief of staff" in text or "founder's office" in text or "founders office" in text

    reject_hit = False
    for t in cfg["reject_titles"]:
        tl = t.lower()
        if tl == "vp":
            # word-boundary match only, so "AVP" (which contains the substring "vp")
            # doesn't get caught by a bare VP reject rule.
            if re.search(r"\bvp\b|\bvice president\b", text):
                reject_hit = True
        elif tl == "chief":
            if "chief" in text and not is_chief_of_staff:
                reject_hit = True
        else:
            if tl in text:
                reject_hit = True

    if reject_hit:
        return HARD_REJECT

    if any(t.lower() in text for t in cfg["exact"]):
        return scores["exact_band"]
    if any(t.lower() in text for t in cfg["adjacent"]):
        return scores["adjacent_band"]
    if any(t.lower() in text for t in cfg["entry_only"]):
        return scores["entry_or_stretch"]

    return scores["entry_or_stretch"]  # unclear title, treat as stretch rather than reject


def _extract_years_range(jd_text: str) -> tuple[int, int] | None:
    patterns = [
        r"(\d+)\s*[-to]{1,3}\s*(\d+)\s*years?",
        r"(\d+)\+\s*years?",
    ]
    for p in patterns:
        m = re.search(p, jd_text.lower())
        if m:
            groups = m.groups()
            if len(groups) == 2 and groups[1]:
                return int(groups[0]), int(groups[1])
            elif len(groups) >= 1:
                lo = int(groups[0])
                return lo, lo + 10  # "X+ years" treated as open-ended
    return None


def _score_experience(jd_text: str, profile: dict) -> float | str:
    scores = profile["scoring"]["p2_logistics"]["experience_years_scores"]
    rng = _extract_years_range(jd_text)
    if rng is None:
        return scores["1-3"]  # undisclosed -- don't penalize, assume neutral-favorable

    lo, hi = rng
    if lo >= 5:
        return HARD_REJECT
    if lo <= 1 and hi <= 3:
        return scores["1-3"]
    if lo == 2 and hi == 4:
        return scores["2-4"]
    if (lo <= 1) or (3 <= lo <= 5 and hi <= 5):
        return scores["3-5_or_under_1"]
    if hi >= 5:
        return HARD_REJECT
    return scores["3-5_or_under_1"]


def _score_location(jd_location: str, profile: dict) -> float | str:
    scores = profile["scoring"]["p2_logistics"]["location_scores"]
    loc = jd_location.lower()

    if "remote" in loc:
        return scores["Remote"]
    if "bengaluru" in loc or "bangalore" in loc:
        return scores["Bengaluru"]
    if "mumbai" in loc:
        return scores["Mumbai"]
    if "gurugram" in loc or "gurgaon" in loc:
        return scores["Gurugram"]
    if any(intl in loc for intl in ["singapore", "dubai", "uk", "usa", "london", "new york", "hong kong"]):
        return scores["International"]
    if any(city in loc for city in ["delhi", "pune", "hyderabad", "chennai", "noida", "kolkata"]):
        return scores["other_india_metro"]

    return HARD_REJECT


def _score_salary(jd_min_lpa: float | None, profile: dict) -> tuple[float | None, bool]:
    """Returns (score_or_None_if_undisclosed, is_hard_reject)"""
    scores = profile["scoring"]["p2_logistics"]["salary_scores_lpa"]
    if jd_min_lpa is None:
        return None, False
    if jd_min_lpa < 24:
        return scores["below_24"], True
    if 24 <= jd_min_lpa <= 30:
        return scores["24_to_30"], False
    return scores["above_30"], False


def score_p2(jd_text: str, jd_title: str, jd_location: str, jd_min_lpa: float | None = None) -> dict:
    profile = load_profile()
    weights = profile["scoring"]["p2_logistics"]

    title_score = _score_title(jd_text, jd_title, profile)
    exp_score = _score_experience(jd_text, profile)
    loc_score = _score_location(jd_location, profile)
    salary_score, salary_hard_reject = _score_salary(jd_min_lpa, profile)

    if HARD_REJECT in (title_score, exp_score, loc_score) or salary_hard_reject:
        return {"p2_score": 0, "hard_reject": True, "reject_reason": _reject_reason(
            title_score, exp_score, loc_score, salary_hard_reject
        )}

    if salary_score is None:
        # undisclosed -- reweight remaining 3 proportionally to sum to 100%
        total_w = weights["seniority_title"] + weights["experience_years"] + weights["location"]
        p2 = (
            title_score * (weights["seniority_title"] / total_w)
            + exp_score * (weights["experience_years"] / total_w)
            + loc_score * (weights["location"] / total_w)
        )
    else:
        p2 = (
            title_score * weights["seniority_title"]
            + exp_score * weights["experience_years"]
            + loc_score * weights["location"]
            + salary_score * weights["salary"]
        )

    return {
        "p2_score": round(p2, 1),
        "hard_reject": False,
        "sub_scores": {
            "title": title_score,
            "experience": exp_score,
            "location": loc_score,
            "salary": salary_score,
        },
    }


def _reject_reason(title_score, exp_score, loc_score, salary_hard_reject) -> str:
    reasons = []
    if title_score == HARD_REJECT:
        reasons.append("title (Director+/CXO or 5+yr min)")
    if exp_score == HARD_REJECT:
        reasons.append("experience (5+ yrs required)")
    if loc_score == HARD_REJECT:
        reasons.append("location (outside target cities)")
    if salary_hard_reject:
        reasons.append("salary (<24 LPA)")
    return ", ".join(reasons)
