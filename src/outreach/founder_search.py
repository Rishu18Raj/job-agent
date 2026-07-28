"""
Finds a plausible founder-LinkedIn search result for a company. Deliberately does NOT
scrape LinkedIn itself (ToS). Instead surfaces a search query + top result link for
the human to verify manually -- name collisions and stale profiles are common enough
that this should never be auto-trusted as the outreach target.
"""
import requests
from bs4 import BeautifulSoup


def search_founder_linkedin(company_name: str, founder_name: str | None = None) -> dict:
    query = f"{company_name} founder LinkedIn"
    if founder_name:
        query = f"{founder_name} {company_name} LinkedIn"

    # NOTE: plug in whatever search API you have available (Bing Web Search API,
    # SerpAPI, Google Custom Search JSON API, etc.) -- direct scraping of Google
    # search results is fragile and against Google's ToS. Left as a stub.
    return {
        "query_used": query,
        "top_result_url": None,
        "verified": False,
        "note": "Wire up a search API here (SerpAPI / Bing / Google CSE). "
                "Result must be manually verified before outreach -- do not auto-trust.",
    }
