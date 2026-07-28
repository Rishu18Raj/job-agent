import smtplib
from email.mime.text import MIMEText
from src.config import env


def send_match_email(company: str, role: str, match_pct: float, jd_link: str,
                      outreach_contact: str | None = None, tier: str = "Tier2"):
    subject = f"[{tier} {match_pct:.0f}%] {role} @ {company}"

    body_lines = [
        f"Company: {company}",
        f"Role: {role}",
        f"Match: {match_pct:.0f}%",
        f"JD: {jd_link}",
    ]
    if outreach_contact:
        body_lines.append(f"Suggested outreach contact (unverified, confirm before messaging): {outreach_contact}")
    body = "\n".join(body_lines)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = env("GMAIL_ADDRESS")
    msg["To"] = env("NOTIFY_TO", required=False, default=env("GMAIL_ADDRESS"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(env("GMAIL_ADDRESS"), env("GMAIL_APP_PASSWORD"))
        server.send_message(msg)
