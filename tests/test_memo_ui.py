from memo.schema import MemoData
from memo.ui import build_memo_data_from_form, _suggested_filename


def _raw_form_data(**overrides):
    data = {
        "date": "21-Mar-2026",
        "subject": "Weekly Project Update",
        "recipient": "Stakeholders",
        "background": "Background section",
        "problem_statement": "Problem section",
        "updates_information": "Updates section",
        "additional_section_1": "A1",
        "additional_section_2": "A2",
        "additional_section_3": "A3",
        "memo_title": "Weekly Project Update Memo",
        "organization_name": "The Farm",
        "logo_path": "",
    }
    data.update(overrides)
    return data


def test_build_memo_data_from_form_returns_memo_data():
    memo = build_memo_data_from_form(_raw_form_data())

    assert isinstance(memo, MemoData)
    assert memo.memo_title == "Weekly Project Update Memo"
    assert memo.logo_path == "memo/assets/the_farm_logo.png"


def test_suggested_filename_sanitizes_subject():
    filename = _suggested_filename("Weekly Project Update: Farm #1")

    assert filename == "weekly-project-update-farm-1.pdf"
