from datetime import date
from src.config import load_profile
from src.sources import funding_news
from src.outreach.founder_search import search_founder_linkedin
from src.sheets.sheets_client import append_row
from src.notify.email_notify import send_match_email
from src.state.dedup_store import is_seen, mark_seen


def run():
    profile = load_profile()
    tier3_cfg = profile["tier3_sources"]
    min_funding = tier3_cfg["min_funding_usd"]

    for feed in tier3_cfg["funding_feeds"]:
        entries = funding_news.fetch_funding_entries(feed["rss_url"], feed["name"])

        for e in entries:
            company = e["title"]  # refine with NER/parsing if noisy in practice
            link = e["link"]

            if is_seen(company, "funding-round", link):
                continue

            if e["amount_usd"] is not None and e["amount_usd"] < min_funding:
                mark_seen(company, "funding-round", link)
                continue

            founder_lookup = search_founder_linkedin(company)

            append_row("Tier3", {
                "Date Found": str(date.today()),
                "Company": company,
                "Funding Round": "",  # parse from title/summary if needed
                "Funding Amount": e["amount_usd"] or "unspecified",
                "Funding Source": f"{e['source']}: {link}",
                "Sector": "",
                "Careers Page Link": "",
                "Business-Side Role Listed?": "",
                "Founder Name": "",
                "Founder LinkedIn (unverified)": founder_lookup.get("top_result_url", "") or founder_lookup.get("query_used", ""),
                "Outreach Status": "Not Contacted",
                "Notes": e["summary"],
            })

            send_match_email(company, "New funding -- check for business-side roles", 100, link, tier="Tier3")
            mark_seen(company, "funding-round", link)


if __name__ == "__main__":
    run()
