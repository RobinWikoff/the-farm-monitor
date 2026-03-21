from pathlib import Path

from pypdf import PdfReader

from memo.generator import generate_memo_pdf
from memo.schema import MemoData


def _memo_data(**overrides):
    data = {
        "date": "2026-03-21",
        "subject": "Project Update",
        "recipient": "Stakeholders",
        "background": "Background paragraph.",
        "problem_statement": "Problem details.",
        "updates_information": "Update details.",
        "additional_section_1": "Additional section one.",
        "additional_section_2": "Additional section two.",
        "additional_section_3": "Additional section three.",
        "memo_title": "The Farm Memo",
        "organization_name": "The Farm",
        "logo_path": "",
    }
    data.update(overrides)
    return MemoData(**data)


def test_generate_memo_pdf_creates_non_empty_file(tmp_path: Path):
    output = tmp_path / "memo.pdf"

    generate_memo_pdf(_memo_data(), output)

    assert output.exists()
    assert output.stat().st_size > 0


def test_generate_memo_pdf_includes_header_footer_text(tmp_path: Path):
    output = tmp_path / "memo.pdf"

    generate_memo_pdf(_memo_data(), output)

    reader = PdfReader(str(output))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)

    assert "The Farm" in text
    assert "The Farm Memo" in text
    assert "Page 1 of 1" in text


def test_generate_memo_pdf_multi_page_has_pagination(tmp_path: Path):
    output = tmp_path / "memo_multi.pdf"
    long_updates = "\n".join(
        [f"Line {i} lorem ipsum content for pagination." for i in range(1, 420)]
    )

    generate_memo_pdf(_memo_data(updates_information=long_updates), output)

    reader = PdfReader(str(output))
    assert len(reader.pages) >= 2

    page1_text = reader.pages[0].extract_text() or ""
    page2_text = reader.pages[1].extract_text() or ""

    assert "Page 1 of" in page1_text
    assert "Page 2 of" in page2_text
