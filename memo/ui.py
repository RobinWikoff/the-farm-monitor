from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

try:
    # Package import path (e.g. `python -m memo.ui`)
    from .generator import generate_memo_pdf
    from .schema import DATE_FORMAT, DEFAULT_LOGO_PATH, MemoData
except ImportError:  # pragma: no cover - runtime fallback for streamlit script mode
    # Direct script path (e.g. `streamlit run memo/ui.py`)
    from memo.generator import generate_memo_pdf
    from memo.schema import DATE_FORMAT, DEFAULT_LOGO_PATH, MemoData


def build_memo_data_from_form(raw: Mapping[str, Any]) -> MemoData:
    """Build validated memo data from UI form values."""
    return MemoData.from_mapping(raw)


def _suggested_filename(subject: str) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in subject.lower()).strip("-")
    safe = "-".join(part for part in safe.split("-") if part)
    if not safe:
        safe = "memo"
    return f"{safe}.pdf"


def _generate_pdf_bytes(memo: MemoData) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        generate_memo_pdf(memo, tmp_path)
        return tmp_path.read_bytes()
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def main() -> None:
    st.set_page_config(page_title="The Farm Memo Generator", page_icon="📝", layout="wide")
    st.title("The Farm Memo Generator")
    st.caption("Fill in the memo fields, then generate and download a branded PDF.")

    with st.form("memo_form", clear_on_submit=False):
        left, right = st.columns(2)

        with left:
            memo_date = st.text_input(
                "Date (DD-Mon-YYYY)",
                value=date.today().strftime(DATE_FORMAT),
                help="Example: 21-Mar-2026",
            )
            subject = st.text_input("Subject", placeholder="Weekly Project Update")
            recipient = st.text_input("Recipient", placeholder="Stakeholders")
            memo_title = st.text_input(
                "Memo Title",
                placeholder="Weekly Project Update Memo",
                help="Required.",
            )

        with right:
            organization_name = st.text_input("Organization Name", value="The Farm")
            logo_path = st.text_input(
                "Logo Path",
                value=DEFAULT_LOGO_PATH,
                help="Leave as default once logo is saved there.",
            )

        background = st.text_area("Background", height=110)
        problem_statement = st.text_area("Problem Statement", height=110)
        updates_information = st.text_area("Updates / Information", height=140)

        st.divider()
        st.markdown("**Additional Sections**")

        additional_section_1_title = st.text_input("Section 1 Title", value="Additional Section 1")
        additional_section_1 = st.text_area("Section 1 Content", height=110)

        additional_section_2_title = st.text_input("Section 2 Title", value="Additional Section 2")
        additional_section_2 = st.text_area("Section 2 Content", height=110)

        additional_section_3_title = st.text_input("Section 3 Title", value="Additional Section 3")
        additional_section_3 = st.text_area("Section 3 Content", height=110)

        submitted = st.form_submit_button("Generate PDF")

    if submitted:
        raw = {
            "date": memo_date,
            "subject": subject,
            "recipient": recipient,
            "background": background,
            "problem_statement": problem_statement,
            "updates_information": updates_information,
            "additional_section_1": additional_section_1,
            "additional_section_2": additional_section_2,
            "additional_section_3": additional_section_3,
            "additional_section_1_title": additional_section_1_title,
            "additional_section_2_title": additional_section_2_title,
            "additional_section_3_title": additional_section_3_title,
            "memo_title": memo_title,
            "organization_name": organization_name,
            "logo_path": logo_path,
        }

        try:
            memo = build_memo_data_from_form(raw)
            pdf_bytes = _generate_pdf_bytes(memo)
        except Exception as exc:
            st.error(f"Could not generate memo PDF: {exc}")
            return

        st.success("Memo PDF generated.")
        st.download_button(
            "Download Memo PDF",
            data=pdf_bytes,
            file_name=_suggested_filename(memo.memo_title),
            mime="application/pdf",
        )


if __name__ == "__main__":
    main()
