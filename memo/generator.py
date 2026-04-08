from __future__ import annotations

import logging
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate

from .schema import MemoData
from .template import build_memo_story


logger = logging.getLogger(__name__)


class NumberedCanvas(canvas.Canvas):
    def __init__(
        self,
        *args,
        memo_title: str,
        organization_name: str,
        logo_path: str = "",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict] = []
        self.memo_title = memo_title
        self.organization_name = organization_name
        self.logo_path = logo_path

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_header()
            self._draw_footer(self._pageNumber, page_count)
            super().showPage()
        super().save()

    def _draw_header(self):
        width, height = LETTER
        header_line_y = height - 0.86 * inch
        header_top_y = height - 0.18 * inch
        text_x = 0.75 * inch

        self.setStrokeColorRGB(0.75, 0.75, 0.75)
        self.line(0.7 * inch, header_line_y, width - 0.7 * inch, header_line_y)

        if self.logo_path and Path(self.logo_path).exists():
            try:
                img_width_px, img_height_px = ImageReader(self.logo_path).getSize()
                if img_width_px > 0 and img_height_px > 0:
                    aspect_ratio = img_width_px / img_height_px
                    max_logo_height = (header_top_y - header_line_y) - (0.04 * inch)
                    max_logo_width = 2.8 * inch

                    logo_height = max_logo_height
                    logo_width = logo_height * aspect_ratio
                    if logo_width > max_logo_width:
                        logo_width = max_logo_width
                        logo_height = logo_width / aspect_ratio

                    self.drawImage(
                        self.logo_path,
                        0.72 * inch,
                        header_line_y + 0.02 * inch,
                        width=logo_width,
                        height=logo_height,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                    text_x = 0.72 * inch + logo_width + 0.06 * inch
            except Exception as exc:
                logger.warning(
                    "Logo rendering failed for '%s'; generating PDF without logo. Error: %s",
                    self.logo_path,
                    exc,
                )

        self.setFont("Times-Bold", 11)
        self.drawString(text_x, header_line_y + 0.52 * inch, self.organization_name)

    def _draw_footer(self, page_number: int, page_count: int):
        width, _ = LETTER
        y = 0.55 * inch

        self.setStrokeColorRGB(0.75, 0.75, 0.75)
        self.line(0.7 * inch, 0.78 * inch, width - 0.7 * inch, 0.78 * inch)

        self.setFont("Times-Roman", 9)
        self.drawString(0.75 * inch, y, self.memo_title)

        center_x = width / 2
        self.drawCentredString(center_x, y, self.organization_name)

        self.drawRightString(width - 0.75 * inch, y, f"Page {page_number} of {page_count}")


def generate_memo_pdf(memo: MemoData, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=1.05 * inch,
        bottomMargin=0.95 * inch,
        title=memo.memo_title,
        author=memo.organization_name,
    )

    story = build_memo_story(memo)
    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(
            *args,
            memo_title=memo.memo_title,
            organization_name=memo.organization_name,
            logo_path=memo.logo_path,
            **kwargs,
        ),
    )

    return output
