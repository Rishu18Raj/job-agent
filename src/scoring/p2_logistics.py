import re
from src.config import load_profile

HARD_REJECT = "HARD_REJECT"


TECHNICAL_ROLE_TITLE_SIGNALS = [
    "site reliability engineer", "sre", "software engineer", "software developer",
    "devops", "backend engineer", "frontend engineer", "full stack", "fullstack",
    "data engineer", "machine learning engineer", "ml engineer", "ai engineer",
    "qa engineer", "sdet", "platform engineer", "infrastructure engineer",
    "cloud engineer", "mobile engineer", "ios developer", "android developer",
    "systems engineer", "network engineer", "security engineer",
]


def _is_technical_role_mismatch(jd_title: str) -> bool:
    """Deterministic backstop, independent of the LLM. Added after a real failure
    case where an SRE role scored 76% overall because the LLM's P1 sub-scores were
    generously inflated (hard_skill_match: 90, transferable: 95) despite its own
    rationale admitting the role wasn't a fit -- prompt tuning alone isn't fully
    reliable against this kind of leniency bias, so this catches the obvious cases
    before any LLM call happens (also saves the API cost on jobs that were never
    going to be relevant). This only checks the JOB TITLE, not JD body text, to
    avoid false-positives on finance roles that happen to mention "engineering"
    in passing (e.g. "financial engineering" concepts, "re-engineering a process")."""
    title_lower = jd_title.lower()
    return any(signal in title_lower for signal in TECHNICAL_ROLE_TITLE_SIGNALS)


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


def _extract_years_range(jd_text: str) -> tuple[int, int | None] | None:
    """Returns (lo, hi) where hi is None if only a lower bound was stated
    (e.g. '4+ years', 'minimum 4 years', or a bare '5 years experience' with
    no explicit range). Handles both 'years'/'year' and the very common 'yrs'/'yr'
    abbreviation, plus en-dash/em-dash ranges, since JD text varies a lot and
    silently failing to match here previously meant these fell through as
    "undisclosed" and got scored favorably instead of gated -- that was the bug."""
    text = jd_text.lower()

    # 1) explicit range: "4-6 years", "4 to 6 yrs", "4–6 years", "4 — 6 yrs"
    m = re.search(r"(\d+)\s*(?:-|–|—|to)\s*(\d+)\+?\s*(?:years?|yrs?)\b", text)
    if m:
        return int(m.group(1)), int(m.group(2))

    # 2) "X+ years" / "X+ yrs"
    m = re.search(r"(\d+)\s*\+\s*(?:years?|yrs?)\b", text)
    if m:
        return int(m.group(1)), None

    # 3) "minimum/min./at least X years"
    m = re.search(r"(?:minimum|min\.?|at least)\s*(?:of\s*)?(\d+)\s*(?:years?|yrs?)\b", text)
    if m:
        return int(m.group(1)), None

    # 4) bare "X years [of] [relevant] experience" -- no range/plus/minimum wording,
    # just a flat lower-bound requirement, which is common phrasing
    m = re.search(r"(\d+)\s*(?:years?|yrs?)\s*(?:of\s*)?(?:relevant\s*)?experience\b", text)
    if m:
        return int(m.group(1)), None

    return None


def _score_experience(jd_text: str, profile: dict) -> float | str:
    scores = profile["scoring"]["p2_logistics"]["experience_years_scores"]
    rng = _extract_years_range(jd_text)
    if rng is None:
        return scores["1-3"]  # undisclosed -- don't penalize, assume neutral-favorable

    lo, hi = rng

    # Explicit hard rule: lower bound > 3 years is an automatic reject, regardless
    # of the upper bound or how it was phrased (range, "X+", "minimum X", or a
    # bare "X years experience"). This supersedes the bucket logic below --
    # buckets only apply once we know lo <= 3.
    if lo > 3:
        return HARD_REJECT

    if lo == 0 and hi is not None and hi < 1:
        return scores["3-5_or_under_1"]  # explicit "less than 1 year" phrasing
    if lo <= 1 and (hi is None or hi <= 3):
        return scores["1-3"]
    if lo == 2 and hi == 4:
        return scores["2-4"]
    # remaining lo in {0,1,2,3} not caught above (e.g. "3 years", "2-5", "1-4")
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


def _is_education_reject(jd_text: str, profile: dict) -> bool:
    """Hard-reject roles whose stated qualification is exclusively B.Tech/engineering
    or CA (Chartered Accountant), UNLESS the JD also explicitly accepts MBA -- e.g.
    'CA/MBA (Finance)' or 'Bachelor's degree, MBA preferred' should NOT be rejected,
    since MBA is explicitly listed as acceptable. Order matters: check for an MBA
    mention FIRST: if present, never reject on education grounds regardless of what
    else (CA, B.Tech) is also listed as an alternative."""
    text = jd_text.lower()
    cfg = profile["scoring"]["p2_logistics"].get("education_gate", {})

    mba_pattern = r"\bmba\b"
    if re.search(mba_pattern, text):
        return False  # MBA explicitly acceptable -- never reject on education

    exclusive_patterns = cfg.get("reject_patterns", [
        r"\bb\.?\s?tech\b",
        r"\bbachelor of technology\b",
        r"\bbachelor of engineering\b",
        r"\bchartered accountant\b",
        r"\bqualified\s+ca\b",
        r"\bca\s*\(inter\)",
        r"\bca\s+(?:mandatory|required)\b",
    ])
    return any(re.search(p, text) for p in exclusive_patterns)


def score_p2(jd_text: str, jd_title: str, jd_location: str, jd_min_lpa: float | None = None) -> dict:
    profile = load_profile()
    weights = profile["scoring"]["p2_logistics"]

    title_score = _score_title(jd_text, jd_title, profile)
    exp_score = _score_experience(jd_text, profile)
    loc_score = _score_location(jd_location, profile)
    salary_score, salary_hard_reject = _score_salary(jd_min_lpa, profile)
    education_reject = _is_education_reject(jd_text, profile)
    technical_mismatch = _is_technical_role_mismatch(jd_title)

    if HARD_REJECT in (title_score, exp_score, loc_score) or salary_hard_reject or education_reject or technical_mismatch:
        return {"p2_score": 0, "hard_reject": True, "reject_reason": _reject_reason(
            title_score, exp_score, loc_score, salary_hard_reject, education_reject, technical_mismatch
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


def _reject_reason(title_score, exp_score, loc_score, salary_hard_reject, education_reject=False, technical_mismatch=False) -> str:
    reasons = []
    if title_score == HARD_REJECT:
        reasons.append("title (Director+/CXO or 5+yr min)")
    if exp_score == HARD_REJECT:
        reasons.append("experience (lower bound > 3 years)")
    if loc_score == HARD_REJECT:
        reasons.append("location (outside target cities)")
    if salary_hard_reject:
        reasons.append("salary (<24 LPA)")
    if education_reject:
        reasons.append("education (requires B.Tech/CA without MBA as an accepted alternative)")
    if technical_mismatch:
        reasons.append("function (technical/engineering role title, e.g. SRE/SWE/DevOps -- deterministic, skipped LLM call)")
    return ", ".join(reasons)
