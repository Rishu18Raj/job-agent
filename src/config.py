import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def load_profile() -> dict:
    with open(ROOT / "config" / "profile.yaml", "r") as f:
        return yaml.safe_load(f)


def load_resume_text() -> str:
    profile = load_profile()
    resume_path = ROOT / profile["candidate"]["resume_path"]
    with open(resume_path, "r") as f:
        return f.read()


def env(key: str, required: bool = True, default=None):
    val = os.environ.get(key, default)
    if required and not val:
        raise EnvironmentError(f"Missing required env var: {key}")
    return val


AUTO_APPLY_ENABLED = os.environ.get("AUTO_APPLY_ENABLED", "false").lower() == "true"
