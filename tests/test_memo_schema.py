from pathlib import Path

import pytest

from memo.schema import MemoData, load_memo_data


def _valid_mapping():
    return {
        "date": "2026-03-21",
        "subject": "Status Update",
        "recipient": "Stakeholders",
        "background": "Background text",
        "problem_statement": "Problem statement text",
        "updates_information": "Update details",
        "additional_section_1": "Section one",
        "additional_section_2": "Section two",
        "additional_section_3": "Section three",
    }


def test_memo_data_from_mapping_accepts_valid_input():
    memo = MemoData.from_mapping(_valid_mapping())

    assert memo.subject == "Status Update"
    assert memo.memo_title == "Status Update"
    assert memo.organization_name == "The Farm"


def test_memo_data_from_mapping_rejects_missing_required_field():
    raw = _valid_mapping()
    raw.pop("recipient")

    with pytest.raises(ValueError, match="Missing required memo fields"):
        MemoData.from_mapping(raw)


def test_memo_data_from_mapping_rejects_blank_required_field():
    raw = _valid_mapping()
    raw["problem_statement"] = "   "

    with pytest.raises(ValueError, match="Blank required memo fields"):
        MemoData.from_mapping(raw)


def test_load_memo_data_yaml(tmp_path: Path):
    file_path = tmp_path / "memo.yaml"
    file_path.write_text(
        "\n".join(
            [
                "date: '2026-03-21'",
                "subject: 'Weekly Update'",
                "recipient: 'Leadership Team'",
                "background: 'Background'",
                "problem_statement: 'Problem'",
                "updates_information: 'Updates'",
                "additional_section_1: 'A1'",
                "additional_section_2: 'A2'",
                "additional_section_3: 'A3'",
            ]
        ),
        encoding="utf-8",
    )

    memo = load_memo_data(file_path)

    assert memo.subject == "Weekly Update"
    assert memo.recipient == "Leadership Team"
