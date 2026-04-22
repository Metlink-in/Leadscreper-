from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.lead import Lead


def _ensure_export_dir(export_dir: str) -> Path:
    path = Path(export_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_csv(leads: List[Lead], export_dir: str, filename: str) -> str:
    path = _ensure_export_dir(export_dir) / filename
    fieldnames = [
        "id",
        "name",
        "category",
        "industry",
        "source",
        "source_url",
        "website",
        "email",
        "phone",
        "location",
        "description",
        "ai_score",
        "ai_summary",
        "outreach_angle",
        "contact_priority",
        "lead_quality",
        "platform",
        "post_url",
        "followers",
        "scraped_at",
        "keywords_matched",
    ]
    with path.open("w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads:
            data = lead.model_dump()
            data["scraped_at"] = data["scraped_at"].isoformat()
            data["keywords_matched"] = ", ".join(data["keywords_matched"])
            writer.writerow(data)
    return str(path)


def generate_json(leads: List[Lead], export_dir: str, filename: str) -> str:
    path = _ensure_export_dir(export_dir) / filename
    with path.open("w", encoding="utf-8") as jsonfile:
        json.dump([lead.model_dump() for lead in leads], jsonfile, default=str, indent=2)
    return str(path)


def generate_pdf(leads: List[Lead], export_dir: str, filename: str) -> str:
    path = _ensure_export_dir(export_dir) / filename
    document = SimpleDocTemplate(str(path), pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = {
        "default": ParagraphStyle(name="default", fontName="Helvetica", fontSize=9, leading=11, textColor=colors.white),
        "title": ParagraphStyle(name="title", fontName="Helvetica-Bold", fontSize=14, leading=16, textColor=colors.white),
    }
    headers = ["Name", "Email", "Phone", "Website", "Score", "Quality", "Priority", "Followers"]
    data = [headers]
    for lead in leads:
        data.append([
            lead.name[:30],
            lead.email or "—",
            lead.phone or "—",
            lead.website or "—",
            str(lead.ai_score or "—"),
            lead.lead_quality or "—",
            lead.contact_priority or "—",
            lead.followers or "—",
        ])
    table = Table(data, repeatRows=1, hAlign="LEFT", colWidths=[1.8 * inch, 0.8 * inch, 1.4 * inch, 1.4 * inch, 0.6 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#00ff88")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#1a1a1a")),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#333333")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story = [Paragraph("Lead Export", styles["title"]), Spacer(1, 12), table, Spacer(1, 12)]
    for lead in leads[:10]:
        story.append(Paragraph(f"<b>{lead.name}</b> — {lead.industry}", styles["default"]))
        story.append(Paragraph(f"Location: {lead.location} | Score: {lead.ai_score or 'N/A'}", styles["default"]))
        story.append(Paragraph(f"Summary: {lead.ai_summary or 'N/A'}", styles["default"]))
        story.append(Spacer(1, 6))
    document.build(story)
    return str(path)
