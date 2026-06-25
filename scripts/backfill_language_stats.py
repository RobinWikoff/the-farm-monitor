#!/usr/bin/env python3
"""
Backfills metrics/language-history.json by running tokei on one commit per week
from the full git history. Uses `git archive` to extract each commit into a temp
directory so the working tree is never disturbed.

Run via:
  workflow_dispatch with backfill=true   (CI)
  python3 scripts/backfill_language_stats.py   (locally, needs tokei on PATH)
"""
import json
import subprocess
import tarfile
import tempfile
from datetime import date
from io import BytesIO
from pathlib import Path

HISTORY_FILE = Path("metrics/language-history.json")


def get_weekly_commits() -> list[tuple[str, str]]:
    """Return (sha, date_str) for one commit per ISO week, oldest first."""
    result = subprocess.run(
        ["git", "log", "--format=%H %cd", "--date=format:%Y-%m-%d", "--reverse"],
        capture_output=True,
        text=True,
        check=True,
    )
    commits: list[tuple[str, str]] = []
    seen_weeks: set[str] = set()
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        sha, commit_date = line.split(" ", 1)
        d = date.fromisoformat(commit_date)
        iso = d.isocalendar()
        week_key = f"{iso.year}-W{iso.week:02d}"
        if week_key not in seen_weeks:
            seen_weeks.add(week_key)
            commits.append((sha, commit_date))
    return commits


def run_tokei_on_archive(sha: str) -> dict | None:
    """Extract commit into a tmpdir via git archive and run tokei on it."""
    archive_proc = subprocess.run(
        ["git", "archive", sha],
        capture_output=True,
    )
    if archive_proc.returncode != 0:
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            with tarfile.open(fileobj=BytesIO(archive_proc.stdout)) as tar:
                tar.extractall(tmpdir)
        except Exception:
            return None

        tokei_proc = subprocess.run(
            ["tokei", "--output", "json", "--exclude", "target", "--exclude", "metrics"],
            capture_output=True,
            text=True,
            cwd=tmpdir,
        )
        if tokei_proc.returncode != 0 or not tokei_proc.stdout.strip():
            return None
        try:
            return json.loads(tokei_proc.stdout)
        except json.JSONDecodeError:
            return None


def parse_snapshot(commit_date: str, raw: dict) -> dict:
    languages: dict = {}
    total_code = total_comments = total_blanks = 0
    for lang, data in raw.items():
        code = data.get("code", 0)
        comments = data.get("comments", 0)
        blanks = data.get("blanks", 0)
        if code == 0 and comments == 0:
            continue
        languages[lang] = {"code": code, "comments": comments, "blanks": blanks}
        total_code += code
        total_comments += comments
        total_blanks += blanks
    return {
        "date": commit_date,
        "languages": languages,
        "totals": {
            "code": total_code,
            "comments": total_comments,
            "blanks": total_blanks,
        },
    }


def main() -> None:
    commits = get_weekly_commits()
    print(f"Found {len(commits)} weekly commits to process.")

    history: list[dict] = []
    for sha, commit_date in commits:
        raw = run_tokei_on_archive(sha)
        if raw is None:
            print(f"  {commit_date} ({sha[:8]}) — skipped")
            continue
        snapshot = parse_snapshot(commit_date, raw)
        rust_code = snapshot["languages"].get("Rust", {}).get("code", 0)
        python_code = snapshot["languages"].get("Python", {}).get("code", 0)
        total = snapshot["totals"]["code"]
        print(
            f"  {commit_date} ({sha[:8]}) — "
            f"{total} lines | Rust {rust_code} | Python {python_code}"
        )
        history.append(snapshot)

    history.sort(key=lambda x: x["date"])
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
        f.write("\n")

    print(f"\nBackfill complete. {len(history)} entries written to {HISTORY_FILE}")


if __name__ == "__main__":
    main()
