#!/usr/bin/env python3
"""Generate a polished PDF from validated resume claim report JSON."""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from validate_report import ReportValidationError, load_and_validate


NAVY = colors.HexColor("#16324F")
BLUE = colors.HexColor("#246B9E")
PALE_BLUE = colors.HexColor("#EAF3F8")
SLATE = colors.HexColor("#40566B")
LIGHT_GRAY = colors.HexColor("#F3F5F7")
MID_GRAY = colors.HexColor("#D7DEE5")
TEXT = colors.HexColor("#1F2933")

STATUS_COLORS = {
    "Supported": colors.HexColor("#DDF2E4"),
    "Plausible but unverified": colors.HexColor("#E8F0FA"),
    "Needs clarification": colors.HexColor("#FFF0C7"),
    "Material inconsistency": colors.HexColor("#FADDDD"),
    "Not assessable": colors.HexColor("#E8E8EA"),
}

STATUS_DISPLAY = {
    "Supported": "Matches the evidence",
    "Plausible but unverified": "Not enough evidence",
    "Needs clarification": "Needs an explanation",
    "Material inconsistency": "Important details don't match",
    "Not assessable": "Unable to check",
}

STATUS_EXPLANATIONS = {
    "Supported": "Reliable information matches the important parts of the claim. No follow-up is needed unless new information appears.",
    "Plausible but unverified": "Nothing important conflicts, but there is not enough independent proof. Ask for a document, link, or work example if confirmation matters.",
    "Needs clarification": "Part of the claim is unclear, such as the dates, personal contribution, ownership, or result. Ask the listed follow-up question.",
    "Material inconsistency": "Reliable information disagrees with an important part of the claim. A person should review the evidence and ask the candidate about it.",
    "Not assessable": "A meaningful check was not possible because the information is private, confidential, unavailable, or cannot be linked reliably to the candidate.",
}

OVERALL_DISPLAY = {
    "No material issues found": "No important problems found",
    "Clarification recommended": "Some claims need an explanation",
    "Human review recommended": "Important mismatch - human review needed",
    "Insufficient evidence": "Not enough information to review",
}

CONFIDENCE_DISPLAY = {
    "High": "Strong",
    "Medium": "Moderate",
    "Low": "Limited",
}


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def join_items(items: Iterable[str]) -> str:
    return ", ".join(esc(item) for item in items)


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=22, leading=27, textColor=NAVY, alignment=TA_LEFT, spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.5, leading=13, textColor=SLATE, spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "HeadingOne", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=14, leading=18, textColor=NAVY, spaceBefore=12, spaceAfter=7,
        ),
        "h2": ParagraphStyle(
            "HeadingTwo", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=11.5, leading=15, textColor=BLUE, spaceBefore=9, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName="Helvetica",
            fontSize=9.2, leading=13, textColor=TEXT, spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName="Helvetica",
            fontSize=7.6, leading=10, textColor=TEXT, wordWrap="CJK",
        ),
        "table_header": ParagraphStyle(
            "TableHeader", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=7.4, leading=9, textColor=colors.white, alignment=TA_LEFT,
        ),
        "callout": ParagraphStyle(
            "Callout", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=10, leading=14, textColor=NAVY, alignment=TA_CENTER,
        ),
        "footer": ParagraphStyle(
            "Footer", parent=base["BodyText"], fontName="Helvetica",
            fontSize=7.2, leading=9, textColor=SLATE, alignment=TA_CENTER,
        ),
    }


def paragraph(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(esc(text), style)


def bullet_paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(f"&bull;&nbsp; {esc(text)}", style)


def page_decor(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    width, height = letter
    canvas.setStrokeColor(MID_GRAY)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, height - 0.42 * inch, width - doc.rightMargin, height - 0.42 * inch)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(SLATE)
    canvas.drawString(doc.leftMargin, 0.34 * inch, "Resume Evidence Review")
    canvas.drawRightString(width - doc.rightMargin, 0.34 * inch, f"Page {doc.page}")
    canvas.restoreState()


def label_value(label: str, value: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(f"<b>{esc(label)}:</b> {esc(value)}", styles["body"])


def list_section(
    story: list[Any], heading: str, items: list[str], styles: dict[str, ParagraphStyle], empty: str
) -> None:
    story.append(Paragraph(esc(heading), styles["h2"]))
    if items:
        story.extend(bullet_paragraph(item, styles["body"]) for item in items)
    else:
        story.append(paragraph(empty, styles["body"]))


def generate_pdf(report: dict[str, Any], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(output), pagesize=letter, rightMargin=0.55 * inch, leftMargin=0.55 * inch,
        topMargin=0.58 * inch, bottomMargin=0.55 * inch,
        title="Resume Evidence Review", author="Resume Claim Verification Skill",
    )
    story: list[Any] = []

    story.append(Paragraph("Resume Evidence Review", styles["title"]))
    story.append(label_value("Candidate", report["candidate_label"], styles))
    story.append(label_value("Review date", report["review_date"], styles))
    story.append(label_value("Inputs reviewed", ", ".join(report["reviewed_inputs"]), styles))
    story.append(Spacer(1, 5))
    conclusion = Table(
        [[Paragraph(esc(OVERALL_DISPLAY[report["overall_conclusion"]]), styles["callout"]) ]],
        colWidths=[7.32 * inch],
    )
    conclusion.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.8, BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(conclusion)
    story.append(Paragraph("Summary", styles["h1"]))
    story.append(paragraph(report["summary"], styles["body"]))

    count_order = [
        "Supported", "Plausible but unverified", "Needs clarification",
        "Material inconsistency", "Not assessable",
    ]
    total_claims = len(report["claims"])
    story.append(Paragraph("Results at a glance", styles["h1"]))
    story.append(Paragraph(
        f"The report reviewed <b>{total_claims} claim{'s' if total_claims != 1 else ''}</b>. "
        "Each result below has a different meaning. A missing document is not the same as a mismatch.",
        styles["body"],
    ))
    profile_data = [[
        Paragraph("Plain result", styles["table_header"]),
        Paragraph("Share", styles["table_header"]),
        Paragraph("What this means and what to do", styles["table_header"]),
    ]]
    for status in count_order:
        count = report["counts"][status]
        profile_data.append([
            Paragraph(esc(STATUS_DISPLAY[status]), styles["small"]),
            Paragraph(
                f"<b>{report['percentages'][status]}%</b><br/>{count} of {total_claims}",
                styles["small"],
            ),
            Paragraph(esc(STATUS_EXPLANATIONS[status]), styles["small"]),
        ])
    profile_table = Table(profile_data, colWidths=[1.55 * inch, 0.85 * inch, 4.92 * inch], repeatRows=1)
    profile_style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, MID_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    for row, status in enumerate(count_order, start=1):
        profile_style.append(("BACKGROUND", (0, row), (0, row), STATUS_COLORS[status]))
        if row % 2 == 0:
            profile_style.append(("BACKGROUND", (1, row), (-1, row), LIGHT_GRAY))
    profile_table.setStyle(TableStyle(profile_style))
    story.append(profile_table)
    story.append(Spacer(1, 6))
    explanation_box = Table([[Paragraph(
        "<b>Important:</b> “Not enough evidence” does not mean the claim is false. It means the review did not find enough reliable information to confirm it. Only “Important details don't match” means reliable information directly disagrees with a claim. These percentages are not a fake-resume score.",
        styles["body"],
    )]], colWidths=[7.32 * inch])
    explanation_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF8E6")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D9A521")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(explanation_box)

    story.append(Paragraph("Claim-by-claim review", styles["h1"]))
    table_data = [[
        Paragraph("ID", styles["table_header"]),
        Paragraph("Claim", styles["table_header"]),
        Paragraph("Result", styles["table_header"]),
        Paragraph("How sure?", styles["table_header"]),
        Paragraph("Why", styles["table_header"]),
    ]]
    for claim in report["claims"]:
        table_data.append([
            paragraph(claim["id"], styles["small"]),
            paragraph(claim["claim"], styles["small"]),
            paragraph(STATUS_DISPLAY[claim["assessment"]], styles["small"]),
            paragraph(CONFIDENCE_DISPLAY[claim["confidence"]], styles["small"]),
            paragraph(claim["inference"], styles["small"]),
        ])
    claim_table = Table(
        table_data,
        colWidths=[0.38 * inch, 1.9 * inch, 1.18 * inch, 0.82 * inch, 3.04 * inch],
        repeatRows=1,
    )
    claim_style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, MID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for row, claim in enumerate(report["claims"], start=1):
        claim_style.append(("BACKGROUND", (2, row), (2, row), STATUS_COLORS[claim["assessment"]]))
        if row % 2 == 0:
            claim_style.append(("BACKGROUND", (0, row), (1, row), LIGHT_GRAY))
            claim_style.append(("BACKGROUND", (3, row), (4, row), LIGHT_GRAY))
    claim_table.setStyle(TableStyle(claim_style))
    story.append(claim_table)

    story.append(PageBreak())
    story.append(Paragraph("Why each claim received this result", styles["h1"]))
    for claim in report["claims"]:
        block: list[Any] = [
            Paragraph(f"{esc(claim['id'])} - {esc(claim['category'])}", styles["h2"]),
            label_value("Claim", claim["claim"], styles),
            label_value(
                "Result",
                f"{STATUS_DISPLAY[claim['assessment']]} ({CONFIDENCE_DISPLAY[claim['confidence']]} confidence in this result)",
                styles,
            ),
        ]
        block.append(Paragraph("What we found", styles["h2"]))
        if claim["observations"]:
            block.extend(bullet_paragraph(item, styles["body"]) for item in claim["observations"])
        else:
            block.append(paragraph("No reliable information was available to check this claim.", styles["body"]))
        for evidence in claim["evidence"]:
            source_text = f"{evidence['source']}: {evidence['finding']}"
            if evidence.get("url"):
                source_text += f" ({evidence['url']})"
            block.append(bullet_paragraph(source_text, styles["small"]))
        block.extend([
            label_value("What this suggests", claim["inference"], styles),
            label_value("What to do next", claim["next_step"], styles),
        ])
        if claim["alternative_explanations"]:
            block.append(KeepTogether([
                Paragraph("Other possible explanations", styles["h2"]),
                *(
                    bullet_paragraph(item, styles["body"])
                    for item in claim["alternative_explanations"]
                ),
            ]))
        if claim["follow_up_questions"]:
            block.append(KeepTogether([
                Paragraph("Follow-up questions", styles["h2"]),
                *(
                    Paragraph(f"{index}. {esc(item)}", styles["body"])
                    for index, item in enumerate(claim["follow_up_questions"], start=1)
                ),
            ]))
        block.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceBefore=7, spaceAfter=4))
        story.append(KeepTogether(block[:3]))
        story.extend(block[3:])

    story.append(Paragraph("Sources", styles["h1"]))
    if report["sources"]:
        for index, source in enumerate(report["sources"], start=1):
            details = source["label"]
            if source.get("url"):
                details += f" - {source['url']}"
            if source.get("accessed"):
                details += f" (accessed {source['accessed']})"
            story.append(Paragraph(f"{index}. {esc(details)}", styles["small"]))
    else:
        story.append(paragraph("No external sources were used.", styles["body"]))

    story.append(Paragraph("What this report cannot tell you", styles["h1"]))
    story.extend(bullet_paragraph(item, styles["body"]) for item in report["limitations"])

    doc.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Validated report JSON")
    parser.add_argument("output", help="Destination PDF path")
    parser.add_argument("--normalized-json", help="Optional normalized JSON output path")
    args = parser.parse_args()
    try:
        report = load_and_validate(args.input)
        output = generate_pdf(report, args.output)
        if args.normalized_json:
            import json

            normalized = Path(args.normalized_json)
            normalized.parent.mkdir(parents=True, exist_ok=True)
            normalized.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, ReportValidationError, ValueError) as exc:
        print(f"Report generation failed: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
