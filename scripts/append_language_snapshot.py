#!/usr/bin/env python3
"""
Reads /tmp/tokei-raw.json produced by `tokei --output json`
and appends a dated snapshot to metrics/language-history.json.
Deduplicates by date (last write wins for the same day).
"""
import json
from datetime import date
from pathlib import Path

TOKEI_RAW = Path("/tmp/tokei-raw.json")
HISTORY_FILE = Path("metrics/language-history.json")


def main() -> None:
    with open(TOKEI_RAW) as f:
        raw: dict = json.load(f)

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

    snapshot = {
        "date": str(date.today()),
        "languages": languages,
        "totals": {
            "code": total_code,
            "comments": total_comments,
            "blanks": total_blanks,
        },
    }

    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            history: list = json.load(f)
    else:
        history = []

    # Replace entry for same date if it already exists
    history = [e for e in history if e["date"] != snapshot["date"]]
    history.append(snapshot)
    history.sort(key=lambda x: x["date"])

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
        f.write("\n")

    rust_code = languages.get("Rust", {}).get("code", 0)
    python_code = languages.get("Python", {}).get("code", 0)
    rust_pct = round(100 * rust_code / total_code, 1) if total_code else 0
    python_pct = round(100 * python_code / total_code, 1) if total_code else 0
    print(
        f"Snapshot {snapshot['date']}: "
        f"{total_code} total code lines | "
        f"Rust {rust_pct}% ({rust_code}) | "
        f"Python {python_pct}% ({python_code}) | "
        f"entries in history: {len(history)}"
    )


if __name__ == "__main__":
    main()
