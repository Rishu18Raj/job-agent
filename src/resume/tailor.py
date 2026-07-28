"""
Produces a tailored resume bullet-emphasis note per JD -- NOT a full resume rewrite/PDF.
Rationale: auto-generating a full new PDF resume per role risks producing something
that misrepresents experience if unreviewed. This instead outputs a short brief of
which existing bullets/framing to lead with, for you to apply to your resume before
submitting -- keeps a human check in the loop for anything actually going out the door.
"""
from src.config import load_resume_text
from src.llm_client import get_client, MODEL_NAME

PROMPT_TEMPLATE = """Given this resume and job description, suggest which 3-4 existing resume \
bullets to lead with, and whether the summary framing should lean IB/DCM, fundraising/IR, or \
strategy/generalist for this specific role. Do not invent new experience. Be concise, \
bullet points only, under 120 words total.

RESUME:
{resume}

JOB DESCRIPTION:
{jd_text}
"""


def generate_tailoring_brief(jd_text: str) -> str:
    resume = load_resume_text()
    client = get_client()
    resp = client.models.generate_content(
        model=MODEL_NAME,
        contents=PROMPT_TEMPLATE.format(resume=resume, jd_text=jd_text[:6000]),
        config={"temperature": 0.3},
    )
    return resp.text.strip()
