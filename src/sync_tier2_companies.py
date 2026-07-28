"""
Entry point for the daily Tier 2 company sync workflow.

Reads data/tier2_companies.txt, finds any company name not yet present in
config/companies_tier2.yaml, runs ATS auto-discovery on each, and appends the
result. Never modifies or removes existing entries -- safe to run daily and to
hand-edit the YAML in between runs.
"""
from pathlib import Path
import yaml
from src.discovery.company_ats_finder import discover_ats

ROOT = Path(__file__).resolve().parent.parent
TXT_PATH = ROOT / "data" / "tier2_companies.txt"
YAML_PATH = ROOT / "config" / "companies_tier2.yaml"

HEADER = """# Tier 2 company list. Auto-populated/updated by src/sync_tier2_companies.py from
# data/tier2_companies.txt. You can also hand-edit entries directly -- the sync
# script only ADDS companies present in the .txt but missing here; it never
# overwrites or removes an existing entry.
#
# Supported ats values and how confident auto-discovery is for each:
#   greenhouse, lever, freshteam, keka  -- real structural detection, auto-scanned
#     (Keka via sitemap.xml + server-rendered job detail pages -- see src/sources/keka.py)
#   workday   -- auto-scanned only if URL fits *.wdN.myworkdayjobs.com, else manual
#   darwinbox -- NEVER auto-scanned. Darwinbox career sites return bot-detection
#     errors on non-browser requests (confirmed directly). Always needs_manual_review.
#   generic   -- static-HTML best-effort fallback, expect a meaningful manual-review rate
#
# needs_manual_review: true means auto-discovery couldn't fully confirm the entry --
# fix "token" (and possibly "ats") by hand before this company will be scanned.

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
        print("No new Tier 2 companies to discover.")
        return

    print(f"Discovering ATS for {len(new_names)} new companies: {new_names}")
    for name in new_names:
        result = discover_ats(name)
        entry = {
            "name": result["name"],
            "ats": result["ats"],
            "token": result["token"],
            "needs_manual_review": result["needs_manual_review"],
            "discovery_note": result["discovery_note"],
        }
        existing["companies"].append(entry)
        status = "OK" if not result["needs_manual_review"] else "NEEDS REVIEW"
        line = f"  [{status}] {name} -> ats={result['ats']} token={result['token']}"
        if result["needs_manual_review"]:
            line += f"\n           reason: {result['discovery_note']}"
        print(line)

    with open(YAML_PATH, "w") as f:
        f.write(HEADER)
        yaml.safe_dump(existing, f, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    run()
