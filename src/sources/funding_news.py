import feedparser
import re

FUNDING_KEYWORDS = ["raises", "raised", "funding", "seed round", "series a", "pre-series a"]
AMOUNT_PATTERN = re.compile(r"\$\s?([\d.]+)\s?(million|mn|m)\b", re.IGNORECASE)


def fetch_funding_entries(feed_url: str, source_name: str) -> list[dict]:
    parsed = feedparser.parse(feed_url)
    entries = []
    for e in parsed.entries:
        title = e.get("title", "")
        summary = e.get("summary", "")
        combined = f"{title} {summary}".lower()

        if not any(k in combined for k in FUNDING_KEYWORDS):
            continue

        amount_match = AMOUNT_PATTERN.search(f"{title} {summary}")
        amount_usd = None
        if amount_match:
            amount_usd = float(amount_match.group(1)) * 1_000_000

        entries.append(
            {
                "source": source_name,
                "title": title,
                "link": e.get("link", ""),
                "summary": summary[:500],
                "published": e.get("published", ""),
                "amount_usd": amount_usd,
            }
        )
    return entries
