import json
from src.config import load_profile, load_resume_text
from src.llm_client import get_client, MODEL_NAME

SCORING_PROMPT_TEMPLATE = """You are scoring how well a candidate's resume matches a job description, \
across four sub-components. Score each 0-100.

CANDIDATE RESUME:
{resume}

JOB DESCRIPTION:
{jd_text}

Score these four sub-components:
1. domain_sector_fit (0-100): How well does the candidate's sector/functional background \
(e.g. debt capital markets, IB, fundraising, credit, equity research) match what this JD's \
core function actually is? Be strict -- a candidate in DCM/fundraising scoring high on a \
pure equity trading or software engineering role would be wrong.
2. hard_skill_match (0-100): Overlap in explicit hard skills -- valuation, financial modeling, \
due diligence, deal structuring, compliance/reporting systems, etc.
3. transferable_skill_match (0-100): Overlap in transferable skills -- cross-border deal execution, \
stakeholder management, pitch/deck prep, dashboarding, project ownership.
4. achievement_signal_match (0-100): Does the JD's language suggest they want someone who has \
driven measurable outcomes (dollar amounts raised, % reductions, deals closed), and does the \
candidate's resume demonstrate that kind of quantified impact?

Respond with ONLY a JSON object, no markdown fences, no preamble:
{{"domain_sector_fit": <int>, "hard_skill_match": <int>, "transferable_skill_match": <int>, \
"achievement_signal_match": <int>, "one_line_rationale": "<short string>"}}
"""


def score_p1(jd_text: str) -> dict:
    profile = load_profile()
    resume = load_resume_text()
    weights = profile["scoring"]["p1_skills"]

    client = get_client()
    prompt = SCORING_PROMPT_TEMPLATE.format(resume=resume, jd_text=jd_text[:6000])

    resp = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config={"response_mime_type": "application/json", "temperature": 0.2},
    )
    raw = resp.text.strip()
    try:
        sub_scores = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        sub_scores = json.loads(cleaned)

    domain_fit = sub_scores["domain_sector_fit"]
    if domain_fit < weights["hard_reject_floor"]["domain_sector_fit_min"]:
        return {
            "p1_score": 0,
            "hard_reject": True,
            "reject_reason": f"domain_sector_fit {domain_fit} below floor",
            "sub_scores": sub_scores,
        }

    p1 = (
        domain_fit * weights["domain_sector_fit"]
        + sub_scores["hard_skill_match"] * weights["hard_skill_match"]
        + sub_scores["transferable_skill_match"] * weights["transferable_skill_match"]
        + sub_scores["achievement_signal_match"] * weights["achievement_signal_match"]
    )

    return {
        "p1_score": round(p1, 1),
        "hard_reject": False,
        "sub_scores": sub_scores,
    }
