import json
from src.config import load_profile, load_resume_text
from src.llm_client import get_client, MODEL_NAME

# Rewritten after a real failure case: an SRE (Site Reliability Engineer) role
# scored domain_sector_fit=55, hard_skill_match=90, transferable_skill_match=95,
# achievement_signal_match=98 -- with the model's OWN rationale admitting "despite
# not being a direct banking tech development background." The old prompt already
# said "be strict" and named software engineering as an explicit non-match example,
# and the model still scored it generously across every sub-component except the
# one with a hard-reject floor. This is leniency bias, not a missing instruction --
# telling a model "be strict" once doesn't survive it wanting to find something
# nice to say about an otherwise strong resume.
#
# Fix: force an explicit category classification FIRST, then give hard numeric
# ceilings tied to that classification for EVERY sub-component, not just domain fit.
SCORING_PROMPT_TEMPLATE = """You are a skeptical, literal-minded recruiter screening a candidate \
against a job description. Your default assumption is LOW fit. Only award high scores where \
there is genuine, specific overlap between what THIS job description requires and what the \
candidate has actually done -- not because the resume is impressive in general.

CANDIDATE RESUME:
{resume}

JOB DESCRIPTION:
{jd_text}

STEP 1 -- Classify the JD's core function in a short phrase (e.g. "Software Engineering / \
Infrastructure", "Investment Banking / DCM", "Product Management", "Data Science / ML", \
"Consulting / Strategy", "Sales", "Design"). Be literal: a "Site Reliability Engineer" role \
is Software Engineering / Infrastructure even if the employer is a fintech company. The \
employer's industry does NOT change the role's function.

STEP 2 -- Score these four sub-components, 0-100 each, using the ceilings below:

1. domain_sector_fit: Does the candidate's actual sector/function (debt capital markets, IB, \
fundraising, credit, equity research) match the JD's core function from Step 1?
   - If Step 1's function is technical/engineering (software engineering, SRE, DevOps, data \
   engineering, ML engineering, QA) and the candidate has no coding/engineering background: \
   HARD CEILING of 15. Do not exceed this regardless of how strong the resume is otherwise.
   - Only score above 50 if the JD's core function is genuinely finance/business/strategy-adjacent.

2. hard_skill_match: Literal overlap between skills the JD explicitly REQUIRES and skills the \
resume demonstrates.
   - If the JD requires coding languages, cloud/infra tools (Kubernetes, AWS, CI/CD, Terraform, \
   etc.), or software engineering skills the resume does not mention: HARD CEILING of 15. \
   "The candidate has other impressive hard skills" is NOT a reason to score above this ceiling \
   -- this sub-component measures overlap with THIS JD only, not general resume strength.

3. transferable_skill_match: Overlap in skills that would genuinely, specifically help in THIS \
role (not skills that merely sound generically impressive). If Step 1's function is technical/ \
engineering and the candidate's transferable skills are all business/deal-execution skills with \
no technical component: cap at 30.

4. achievement_signal_match: Does the candidate show quantified outcomes IN A COMPARABLE DOMAIN \
to what the JD needs? A quantified finance achievement (e.g. "$50M raised") does not signal \
likely success in an unrelated engineering role -- if Step 1's function is technical/engineering \
and the candidate's achievements are all financial/deal-based: cap at 30.

Respond with ONLY a JSON object, no markdown fences, no preamble:
{{"jd_core_function": "<short phrase from Step 1>", "domain_sector_fit": <int>, \
"hard_skill_match": <int>, "transferable_skill_match": <int>, "achievement_signal_match": <int>, \
"one_line_rationale": "<short string>"}}
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
