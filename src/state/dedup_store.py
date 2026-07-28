import sqlite3
from pathlib import Path
import hashlib

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "seen_jobs.db"


def _connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_jobs (
            job_hash TEXT PRIMARY KEY,
            tier TEXT,
            company TEXT,
            role TEXT,
            jd_link TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def job_hash(company: str, role: str, jd_link: str) -> str:
    raw = f"{company.strip().lower()}|{role.strip().lower()}|{jd_link.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def is_seen(company: str, role: str, jd_link: str) -> bool:
    conn = _connect()
    h = job_hash(company, role, jd_link)
    row = conn.execute("SELECT 1 FROM seen_jobs WHERE job_hash = ?", (h,)).fetchone()
    conn.close()
    return row is not None


def mark_seen(tier: str, company: str, role: str, jd_link: str):
    conn = _connect()
    h = job_hash(company, role, jd_link)
    conn.execute(
        "INSERT OR IGNORE INTO seen_jobs (job_hash, tier, company, role, jd_link) VALUES (?, ?, ?, ?, ?)",
        (h, tier, company, role, jd_link),
    )
    conn.commit()
    conn.close()
