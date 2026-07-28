"""
Entry point for the daily Tier 1 company sync workflow.

Reads data/tier1_companies.txt, finds any company name not yet present in
config/companies_tier1.yaml, runs careers-page auto-discovery on each, and
appends the result. Never modifies or removes existing entries.
"""
from pathlib import Path
import yaml
from src.discovery.careers_page_finder import discover_careers_page

ROOT = Path(__file__).resolve().parent.parent
TXT_PATH = ROOT / "data" / "tier1_companies.txt"
YAML_PATH = ROOT / "config" / "companies_tier1.yaml"

HEADER = """# Tier 1 firm list. Auto-populated/updated by src/sync_tier1_companies.py from
# data/tier1_companies.txt. You can also hand-edit entries directly -- the sync
# script only ADDS companies present in the .txt but missing here; it never
# overwrites or removes an existing entry.
#
# needs_manual_review: true means domain/path guessing couldn't confirm a careers
# page -- paste the correct careers_url by hand before this firm will be scanned.
# This happens more often for Tier 1 than Tier 2, since multi-word firm names
# don't map predictably to a domain (no search API is used here).

"""


def read_company_names(path: Path) -> list[str]:
    names = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                names.append(line)
    return names


def load_existing(path: Path) -> dict:
    if not path.exists():
        return {"companies": []}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {"companies": []}


def run():
    wanted_names = read_company_names(TXT_PATH)
    existing = load_existing(YAML_PATH)
    existing_names = {c["name"] for c in existing["companies"]}

    new_names = [n for n in wanted_names if n not in existing_names]

    if not new_names:
        print("No new Tier 1 firms to discover.")
        return

    print(f"Discovering careers pages for {len(new_names)} new firms: {new_names}")
    for name in new_names:
        result = discover_careers_page(name)
        entry = {
            "name": result["name"],
            "board_type": result["board_type"],
            "careers_url": result["careers_url"],
            "needs_manual_review": result["needs_manual_review"],
            "discovery_note": result["discovery_note"],
        }
        existing["companies"].append(entry)
        status = "OK" if not result["needs_manual_review"] else "NEEDS REVIEW"
        print(f"  [{status}] {name} -> {result['careers_url']}")

    with open(YAML_PATH, "w") as f:
        f.write(HEADER)
        yaml.safe_dump(existing, f, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    run()
