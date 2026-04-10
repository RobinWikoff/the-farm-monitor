from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from .schema import MemoData


def build_memo_story(memo: MemoData):
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "MemoTitle",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=18,
        spaceAfter=12,
    )
    section_header_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading3"],
        fontName="Times-Bold",
        fontSize=12,
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=10.5,
        leading=14,
        spaceAfter=8,
    )

    story = [Paragraph(memo.memo_title, title_style), Spacer(1, 0.08 * inch)]

    meta_table = Table(
        [
            ["Date", memo.date],
            ["Subject", memo.subject],
            ["Recipient", memo.recipient],
        ],
        colWidths=[1.4 * inch, 5.5 * inch],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Times-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Times-Roman"),
                ("FONTSIZE", (0, 0), (-1, -1), 10.5),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([meta_table, Spacer(1, 0.15 * inch)])

    sections = [
        ("Background", memo.background),
        ("Problem Statement", memo.problem_statement),
        ("Updates / Information", memo.updates_information),
        (memo.additional_section_1_title, memo.additional_section_1),
        (memo.additional_section_2_title, memo.additional_section_2),
        (memo.additional_section_3_title, memo.additional_section_3),
    ]

    for heading, content in sections:
        # Only show section heading and content if there is text entered
        if content and str(content).strip():
            story.append(Paragraph(heading, section_header_style))
            for block in str(content).split("\n\n"):
                if block.strip():
                    story.append(Paragraph(block.replace("\n", "<br/>"), body_style))

    return story
