from datetime import date
from pathlib import Path
import yaml
from src.sources import tier1_firms
from src.sheets.sheets_client import append_row
from src.state.dedup_store import is_seen, mark_seen

ROOT = Path(__file__).resolve().parent.parent


def load_tier1_firms() -> list[dict]:
    with open(ROOT / "config" / "companies_tier1.yaml", "r") as f:
        data = yaml.safe_load(f)
    return data.get("companies", [])


def run():
    firms = load_tier1_firms()

    for firm in firms:
        if firm.get("needs_manual_review"):
            print(f"[needs manual review] {firm['name']}: {firm.get('discovery_note', '')} -- skipping scan until careers_url is fixed")
            continue

        results = tier1_firms.scan_firm(firm["name"], firm["careers_url"])
        for r in results:
            jd_link = r.get("jd_link", "")
            role = r.get("role_title", "")
            if is_seen(firm["name"], role, jd_link):
                continue

            append_row("Tier1", {
                "Date Found": str(date.today()),
                "Firm": firm["name"],
                "Role Title": role,
                "Function": r.get("function", ""),
                "Location": r.get("location", ""),
                "JD Link": jd_link,
                "Referral Contact?": "",
                "Status": "New",
                "Notes": "",
            })
            mark_seen("Tier1", firm["name"], role, jd_link)


if __name__ == "__main__":
    run()
