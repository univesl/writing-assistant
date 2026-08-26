from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak,
)


ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "docs" / "API-v2.md"
output = ROOT / "docs" / "API-v2.pdf"

pdfmetrics.registerFont(TTFont("Chinese", r"C:\Windows\Fonts\simsun.ttc"))
pdfmetrics.registerFont(TTFont("ChineseBold", r"C:\Windows\Fonts\simsunb.ttf"))

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("TitleCN", parent=styles["Title"], fontName="ChineseBold", fontSize=21, leading=28, alignment=TA_CENTER, textColor=colors.HexColor("#17365D"), spaceAfter=10))
styles.add(ParagraphStyle("H1CN", parent=styles["Heading1"], fontName="ChineseBold", fontSize=15, leading=21, textColor=colors.HexColor("#17365D"), spaceBefore=12, spaceAfter=7))
styles.add(ParagraphStyle("H2CN", parent=styles["Heading2"], fontName="ChineseBold", fontSize=12, leading=18, textColor=colors.HexColor("#2F5597"), spaceBefore=9, spaceAfter=5))
styles.add(ParagraphStyle("BodyCN", parent=styles["BodyText"], fontName="Chinese", fontSize=9.2, leading=15, spaceAfter=4))
styles.add(ParagraphStyle("CodeCN", parent=styles["Code"], fontName="Chinese", fontSize=7.2, leading=10, backColor=colors.HexColor("#F3F6FA"), borderColor=colors.HexColor("#D9E2F3"), borderWidth=0.5, borderPadding=5, spaceBefore=4, spaceAfter=6))
styles.add(ParagraphStyle("SmallCN", parent=styles["BodyText"], fontName="Chinese", fontSize=8, leading=12, textColor=colors.HexColor("#666666")))


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text):
    text = esc(text)
    text = re.sub(r"`([^`]+)`", r"<font name='ChineseBold'>\1</font>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text


def add_table(rows, story):
    if len(rows) < 2:
        return
    data = [[Paragraph(inline(cell.strip()), styles["BodyCN"]) for cell in row] for row in rows[1:]]
    header = [Paragraph(f"<b>{inline(cell.strip())}</b>", styles["BodyCN"]) for cell in rows[0]]
    data.insert(0, header)
    table = Table(data, repeatRows=1, hAlign="LEFT", colWidths=None)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAF7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17365D")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7C9D6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([table, Spacer(1, 5)])


def build():
    lines = source.read_text(encoding="utf-8").splitlines()
    story = []
    table_rows = []
    code = False
    code_lines = []
    for line in lines:
        if line.startswith("```"):
            if code:
                story.append(Paragraph("<br/>".join(esc(x) for x in code_lines), styles["CodeCN"]))
                code_lines = []
            code = not code
            continue
        if code:
            code_lines.append(line)
            continue
        if line.startswith("|"):
            if set(line.replace("|", "").replace("-", "").replace(":", "").strip()) == set():
                continue
            table_rows.append([x.strip() for x in line.strip("|").split("|")])
            continue
        if table_rows:
            add_table(table_rows, story)
            table_rows = []
        if not line.strip():
            story.append(Spacer(1, 3))
        elif line.startswith("# "):
            story.append(Paragraph(inline(line[2:]), styles["TitleCN"]))
            story.append(Paragraph("版本 2.0 · 2026-08-24", styles["SmallCN"]))
        elif line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), styles["H1CN"]))
        elif line.startswith("### "):
            story.append(Paragraph(inline(line[4:]), styles["H2CN"]))
        elif line.startswith("- "):
            story.append(Paragraph("• " + inline(line[2:]), styles["BodyCN"]))
        else:
            story.append(Paragraph(inline(line), styles["BodyCN"]))
    if table_rows:
        add_table(table_rows, story)

    doc = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=15 * mm, bottomMargin=15 * mm, title="公文字段提取与文件内容审查 API")
    doc.build(story)


if __name__ == "__main__":
    build()
