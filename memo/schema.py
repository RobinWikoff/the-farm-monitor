from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import yaml


_REQUIRED_FIELDS = (
    "date",
    "subject",
    "recipient",
    "background",
    "problem_statement",
    "updates_information",
    "additional_section_1",
    "additional_section_2",
    "additional_section_3",
)

DATE_FORMAT = "%d-%b-%Y"
DEFAULT_LOGO_PATH = "memo/assets/the_farm_logo.png"


@dataclass(slots=True)
class MemoData:
    date: str
    subject: str
    recipient: str
    background: str
    problem_statement: str
    updates_information: str
    additional_section_1: str
    additional_section_2: str
    additional_section_3: str
    memo_title: str = ""
    organization_name: str = "The Farm"
    logo_path: str = DEFAULT_LOGO_PATH

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "MemoData":
        missing = [field for field in _REQUIRED_FIELDS if field not in data]
        if missing:
            raise ValueError(f"Missing required memo fields: {', '.join(missing)}")

        blank = [field for field in _REQUIRED_FIELDS if str(data.get(field, "")).strip() == ""]
        if blank:
            raise ValueError(f"Blank required memo fields: {', '.join(blank)}")

        memo_title = str(data.get("memo_title", "")).strip() or str(data["subject"]).strip()
        org_name = str(data.get("organization_name", "The Farm")).strip() or "The Farm"
        raw_date = str(data["date"]).strip()
        try:
            parsed_date = datetime.strptime(raw_date, DATE_FORMAT)
        except ValueError as exc:
            raise ValueError("Date must be in DD-Mon-YYYY format (example: 21-Mar-2026).") from exc
        normalized_date = parsed_date.strftime(DATE_FORMAT)
        logo_path = str(data.get("logo_path", "")).strip() or DEFAULT_LOGO_PATH

        return cls(
            date=normalized_date,
            subject=str(data["subject"]).strip(),
            recipient=str(data["recipient"]).strip(),
            background=str(data["background"]).strip(),
            problem_statement=str(data["problem_statement"]).strip(),
            updates_information=str(data["updates_information"]).strip(),
            additional_section_1=str(data["additional_section_1"]).strip(),
            additional_section_2=str(data["additional_section_2"]).strip(),
            additional_section_3=str(data["additional_section_3"]).strip(),
            memo_title=memo_title,
            organization_name=org_name,
            logo_path=logo_path,
        )


def load_memo_data(input_path: str | Path) -> MemoData:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in {".yaml", ".yml"}:
        raw = yaml.safe_load(text)
    elif suffix == ".json":
        raw = json.loads(text)
    else:
        raise ValueError("Unsupported input format. Use .yaml, .yml, or .json")

    if not isinstance(raw, Mapping):
        raise ValueError("Memo input must be a mapping/object at the top level")

    return MemoData.from_mapping(raw)
