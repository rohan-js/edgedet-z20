from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    HRFlowable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs" / "resume_project_context.md"
OUTPUT = ROOT / "output" / "pdf" / "hardware_accelerated_cnn_zynq_resume_context.pdf"

NAVY = colors.HexColor("#102A43")
BLUE = colors.HexColor("#1769AA")
CYAN = colors.HexColor("#2F80C9")
PALE_BLUE = colors.HexColor("#EAF4FC")
LIGHT_BLUE = colors.HexColor("#D9ECFA")
INK = colors.HexColor("#243B53")
MUTED = colors.HexColor("#627D98")
LIGHT_GRAY = colors.HexColor("#F4F7FA")
MID_GRAY = colors.HexColor("#D9E2EC")
CODE_BG = colors.HexColor("#F0F4F8")
WHITE = colors.white


def register_fonts() -> None:
    fonts = Path("C:/Windows/Fonts")
    candidates = {
        "Body": fonts / "arial.ttf",
        "Body-Bold": fonts / "arialbd.ttf",
        "Body-Italic": fonts / "ariali.ttf",
        "Body-BoldItalic": fonts / "arialbi.ttf",
        "Code": fonts / "consola.ttf",
        "Code-Bold": fonts / "consolab.ttf",
    }
    for name, path in candidates.items():
        if not path.exists():
            raise FileNotFoundError(f"Required font is unavailable: {path}")
        pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily(
        "Body",
        normal="Body",
        bold="Body-Bold",
        italic="Body-Italic",
        boldItalic="Body-BoldItalic",
    )
    pdfmetrics.registerFontFamily(
        "Code",
        normal="Code",
        bold="Code-Bold",
        italic="Code",
        boldItalic="Code-Bold",
    )


def normalize_text(value: str) -> str:
    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


def inline_markup(value: str) -> str:
    value = normalize_text(value.strip())
    placeholders: dict[str, str] = {}

    def stash(fragment: str) -> str:
        key = f"@@TOKEN{len(placeholders)}@@"
        placeholders[key] = fragment
        return key

    def code_repl(match: re.Match[str]) -> str:
        content = html.escape(match.group(1))
        return stash(f'<font name="Code" color="#174A6E">{content}</font>')

    def link_repl(match: re.Match[str]) -> str:
        label = html.escape(match.group(1))
        href = html.escape(match.group(2), quote=True)
        return stash(f'<link href="{href}" color="#1769AA"><u>{label}</u></link>')

    value = re.sub(r"`([^`]+)`", code_repl, value)
    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, value)
    value = html.escape(value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", value)
    # Links can contain inline-code placeholders. Resolve repeatedly so a
    # placeholder restored from another placeholder is also expanded.
    for _ in range(3):
        for key, fragment in placeholders.items():
            value = value.replace(key, fragment)
    return value


def clean_math(lines: list[str]) -> str:
    raw = " ".join(line.strip() for line in lines)
    if raw.startswith("y_{oc,oh,ow}"):
        return (
            "y[oc, oh, ow] = b[oc] + SUM(ic) SUM(kh) SUM(kw) "
            "x[ic, oh+kh, ow+kw] * w[oc, ic, kh, kw]"
        )
    if raw.startswith("y=\\max"):
        return "y = max(0, y)"
    if raw.startswith("H_{out}"):
        return "H[out] = H[in] - K + 1"
    if "Average latency" in raw:
        return "Average latency = total elapsed time / run count"
    if "text{FPS}" in raw:
        return "FPS = 1000 / latency in milliseconds"
    if "text{Speedup}" in raw:
        return "Speedup = CPU latency / FPGA latency"
    if "11.955" in raw:
        return "1000 / 11.955 = approximately 83.6 inferences/second"

    text = raw.replace("\\approx", " approximately ")
    text = text.replace("\\times", " x ").replace("\\sum", "SUM")
    text = re.sub(r"\\text\{([^}]*)\}", r"\1", text)
    text = re.sub(r"_\{([^}]*)\}", r"[\1]", text)
    return normalize_text(text)


class ArchitectureDiagram(Flowable):
    def __init__(self, width: float):
        super().__init__()
        self.width = width
        self.height = 150

    def draw_box(self, canvas, x, y, w, h, label, fill=WHITE, stroke=MID_GRAY, font=7.5):
        canvas.setFillColor(fill)
        canvas.setStrokeColor(stroke)
        canvas.setLineWidth(0.8)
        canvas.roundRect(x, y, w, h, 4, fill=1, stroke=1)
        canvas.setFillColor(INK)
        canvas.setFont("Body-Bold", font)
        canvas.drawCentredString(x + w / 2, y + h / 2 - 2.5, label)

    def arrow(self, canvas, x1, y1, x2, y2, label):
        canvas.setStrokeColor(BLUE)
        canvas.setFillColor(BLUE)
        canvas.setLineWidth(1.2)
        canvas.line(x1, y1, x2, y2)
        direction = 1 if x2 >= x1 else -1
        canvas.line(x2, y2, x2 - direction * 6, y2 + 3)
        canvas.line(x2, y2, x2 - direction * 6, y2 - 3)
        canvas.setFont("Body", 6.5)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString((x1 + x2) / 2, y1 + 5, label)

    def draw(self):
        c = self.canv
        gap = 34
        region_w = (self.width - gap) / 2
        region_h = 126
        y = 12
        left = 0
        right = region_w + gap

        c.setFillColor(PALE_BLUE)
        c.setStrokeColor(BLUE)
        c.roundRect(left, y, region_w, region_h, 7, fill=1, stroke=1)
        c.roundRect(right, y, region_w, region_h, 7, fill=1, stroke=1)
        c.setFont("Body-Bold", 9)
        c.setFillColor(NAVY)
        c.drawString(left + 9, y + region_h - 15, "Processing System (Arm Cortex-A9)")
        c.drawString(right + 9, y + region_h - 15, "Programmable Logic (FPGA)")

        bw = region_w - 24
        self.draw_box(c, left + 12, y + 76, bw, 23, "Bare-metal application", WHITE)
        self.draw_box(c, left + 12, y + 45, bw, 23, "HLS driver + CPU baseline", WHITE)
        self.draw_box(c, left + 12, y + 14, bw, 23, "Shared DDR memory", LIGHT_BLUE)

        self.draw_box(c, right + 12, y + 76, bw, 23, "AXI4-Lite control + cnn_top", WHITE)
        self.draw_box(c, right + 12, y + 45, bw, 23, "Local BRAM buffers", WHITE)
        self.draw_box(c, right + 12, y + 14, bw, 23, "AXI4 memory-mapped masters", LIGHT_BLUE)

        self.arrow(c, left + region_w, y + 87, right, y + 87, "GP0 control")
        self.arrow(c, right, y + 25, left + region_w, y + 25, "HP0 DDR data")


class ResumeDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and hasattr(flowable, "heading_level"):
            level = flowable.heading_level
            title = flowable.getPlainText()
            key = getattr(flowable, "bookmark_name", f"heading-{self.page}-{id(flowable)}")
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, level=level, closed=level > 0)
            if level == 0:
                self.notify("TOCEntry", (level, title, self.page, key))


def make_styles():
    base = getSampleStyleSheet()
    styles = {}
    styles["title"] = ParagraphStyle(
        "Title",
        parent=base["Title"],
        fontName="Body-Bold",
        fontSize=27,
        leading=32,
        textColor=WHITE,
        alignment=TA_LEFT,
        spaceAfter=13,
    )
    styles["subtitle"] = ParagraphStyle(
        "Subtitle",
        parent=base["Normal"],
        fontName="Body",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#DCEEFF"),
        spaceAfter=12,
    )
    styles["cover_body"] = ParagraphStyle(
        "CoverBody",
        parent=base["Normal"],
        fontName="Body",
        fontSize=10.5,
        leading=16,
        textColor=INK,
        alignment=TA_LEFT,
    )
    styles["h2"] = ParagraphStyle(
        "Heading2",
        parent=base["Heading2"],
        fontName="Body-Bold",
        fontSize=16,
        leading=20,
        textColor=NAVY,
        spaceBefore=13,
        spaceAfter=7,
        keepWithNext=True,
    )
    styles["h3"] = ParagraphStyle(
        "Heading3",
        parent=base["Heading3"],
        fontName="Body-Bold",
        fontSize=11.2,
        leading=14,
        textColor=BLUE,
        spaceBefore=9,
        spaceAfter=4,
        keepWithNext=True,
    )
    styles["body"] = ParagraphStyle(
        "Body",
        parent=base["BodyText"],
        fontName="Body",
        fontSize=9.3,
        leading=13.1,
        textColor=INK,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
        allowWidows=0,
        allowOrphans=0,
    )
    styles["bullet"] = ParagraphStyle(
        "Bullet",
        parent=styles["body"],
        leftIndent=16,
        firstLineIndent=-10,
        bulletIndent=3,
        spaceAfter=3.5,
        alignment=TA_LEFT,
    )
    styles["numbered"] = ParagraphStyle(
        "Numbered",
        parent=styles["bullet"],
        leftIndent=22,
        firstLineIndent=-18,
    )
    styles["quote"] = ParagraphStyle(
        "Quote",
        parent=styles["body"],
        fontSize=9.1,
        leading=13,
        textColor=NAVY,
        leftIndent=4,
        rightIndent=4,
        spaceAfter=0,
        alignment=TA_LEFT,
    )
    styles["code"] = ParagraphStyle(
        "Code",
        parent=base["Code"],
        fontName="Code",
        fontSize=7.2,
        leading=9,
        textColor=colors.HexColor("#102A43"),
        leftIndent=6,
        rightIndent=6,
        spaceBefore=2,
        spaceAfter=2,
        wordWrap="CJK",
    )
    styles["math"] = ParagraphStyle(
        "Math",
        parent=styles["code"],
        fontSize=8.3,
        leading=11,
        alignment=TA_CENTER,
        textColor=NAVY,
    )
    styles["table_header"] = ParagraphStyle(
        "TableHeader",
        parent=styles["body"],
        fontName="Body-Bold",
        fontSize=7.5,
        leading=9.2,
        textColor=WHITE,
        alignment=TA_LEFT,
        spaceAfter=0,
    )
    styles["table_cell"] = ParagraphStyle(
        "TableCell",
        parent=styles["body"],
        fontSize=7.3,
        leading=9.3,
        alignment=TA_LEFT,
        spaceAfter=0,
    )
    return styles


def quote_box(content: str, styles) -> Table:
    paragraph = Paragraph(content, styles["quote"])
    table = Table([[paragraph]], colWidths=[174 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#A8CFEA")),
                ("LINEBEFORE", (0, 0), (0, -1), 3, BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def code_box(code: str, styles) -> Table:
    escaped = html.escape(normalize_text(code.rstrip()))
    paragraph = Paragraph(escaped.replace("\n", "<br/>"), styles["code"])
    table = Table([[paragraph]], colWidths=[174 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                ("BOX", (0, 0), (-1, -1), 0.4, MID_GRAY),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def parse_table(lines: list[str], start: int, styles):
    def cells(line: str) -> list[str]:
        return [part.strip() for part in line.strip().strip("|").split("|")]

    rows = [cells(lines[start])]
    i = start + 2
    while i < len(lines) and lines[i].strip().startswith("|"):
        rows.append(cells(lines[i]))
        i += 1

    column_count = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (column_count - len(row)))

    rendered = []
    for row_idx, row in enumerate(rows):
        style = styles["table_header"] if row_idx == 0 else styles["table_cell"]
        rendered.append([Paragraph(inline_markup(cell), style) for cell in row])

    total_width = 174 * mm
    max_lengths = [max(6, max(len(row[col]) for row in rows)) for col in range(column_count)]
    weights = [min(max(length, 10), 38) for length in max_lengths]
    widths = [total_width * weight / sum(weights) for weight in weights]

    table = Table(rendered, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("GRID", (0, 0), (-1, -1), 0.35, MID_GRAY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table, i


def parse_markdown(text: str, styles):
    lines = text.splitlines()
    story = []
    i = 0
    bookmark_counter = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("# "):
            i += 1
            continue

        if stripped.startswith("## Resume-specific"):
            i += 1
            continue

        if stripped.startswith("**Project period:") or stripped.startswith("**Target platform:") or stripped.startswith("**Project type:") or stripped.startswith("**Original workload:") or stripped.startswith("**Implementation tools:"):
            i += 1
            continue

        if stripped.startswith("## "):
            title = stripped[3:].strip()
            story.append(CondPageBreak(32 * mm))
            p = Paragraph(inline_markup(title), styles["h2"])
            p.heading_level = 0
            p.bookmark_name = f"section-{bookmark_counter}"
            bookmark_counter += 1
            story.extend(
                [
                    p,
                    HRFlowable(width="100%", thickness=0.8, color=CYAN, spaceAfter=6),
                ]
            )
            i += 1
            continue

        if stripped.startswith("### "):
            title = stripped[4:].strip()
            p = Paragraph(inline_markup(title), styles["h3"])
            p.heading_level = 1
            p.bookmark_name = f"section-{bookmark_counter}"
            bookmark_counter += 1
            story.append(p)
            i += 1
            continue

        if stripped.startswith("```"):
            language = stripped[3:].strip().lower()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            if language == "mermaid":
                story.append(ArchitectureDiagram(174 * mm))
                story.append(Spacer(1, 4))
            else:
                story.append(code_box("\n".join(code_lines), styles))
                story.append(Spacer(1, 4))
            continue

        if stripped == "\\[":
            math_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() != "\\]":
                math_lines.append(lines[i])
                i += 1
            i += 1
            story.append(code_box(clean_math(math_lines), styles))
            story.append(Spacer(1, 3))
            continue

        if stripped.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                content = lines[i].strip()[1:].strip()
                if content == "[!IMPORTANT]":
                    content = "<b>IMPORTANT</b>"
                elif content.startswith("- "):
                    content = "\u2022 " + inline_markup(content[2:])
                else:
                    content = inline_markup(content)
                if content:
                    quote_lines.append(content)
                i += 1
            story.append(quote_box("<br/>".join(quote_lines), styles))
            story.append(Spacer(1, 6))
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-+", lines[i + 1]):
            table, i = parse_table(lines, i, styles)
            story.append(table)
            story.append(Spacer(1, 7))
            continue

        bullet_match = re.match(r"^\s*-\s+(.+)$", line)
        if bullet_match:
            story.append(Paragraph(inline_markup(bullet_match.group(1)), styles["bullet"], bulletText="\u2022"))
            i += 1
            continue

        number_match = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
        if number_match:
            story.append(
                Paragraph(
                    inline_markup(number_match.group(2)),
                    styles["numbered"],
                    bulletText=f"{number_match.group(1)}.",
                )
            )
            i += 1
            continue

        paragraph_lines = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt:
                break
            if (
                nxt.startswith("#")
                or nxt.startswith("```")
                or nxt.startswith(">")
                or nxt == "\\["
                or re.match(r"^-\s+", nxt)
                or re.match(r"^\d+\.\s+", nxt)
                or (nxt.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-+", lines[i + 1]))
            ):
                break
            paragraph_lines.append(nxt)
            i += 1
        story.append(Paragraph(inline_markup(" ".join(paragraph_lines)), styles["body"]))

    return story


def first_page(canvas, doc):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 104 * mm, width, 104 * mm, fill=1, stroke=0)
    canvas.setFillColor(BLUE)
    canvas.rect(0, height - 107 * mm, width, 3 * mm, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("Body", 7.5)
    canvas.drawRightString(width - 18 * mm, 12 * mm, "Resume-specific project context")
    canvas.restoreState()


def later_pages(canvas, doc):
    width, height = A4
    canvas.saveState()
    canvas.setStrokeColor(MID_GRAY)
    canvas.setLineWidth(0.4)
    canvas.line(18 * mm, height - 14 * mm, width - 18 * mm, height - 14 * mm)
    canvas.setFont("Body", 7.2)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, height - 10.5 * mm, "Hardware-Accelerated CNN Inference on Xilinx Zynq SoC")
    canvas.line(18 * mm, 14 * mm, width - 18 * mm, 14 * mm)
    canvas.drawString(18 * mm, 9.5 * mm, "Resume context and interview guide")
    canvas.drawRightString(width - 18 * mm, 9.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_cover(styles):
    metadata_style = ParagraphStyle(
        "Metadata",
        parent=styles["cover_body"],
        fontSize=8.8,
        leading=12,
        textColor=INK,
    )
    return [
        Spacer(1, 10 * mm),
        Paragraph("Hardware-Accelerated CNN Inference on Xilinx Zynq SoC", styles["title"]),
        Paragraph("HW/SW Co-Design - Resume Project Context and Interview Guide", styles["subtitle"]),
        Spacer(1, 32 * mm),
        Table(
            [
                [Paragraph("PROJECT PERIOD", metadata_style), Paragraph("January 2026 - February 2026", metadata_style)],
                [Paragraph("TARGET", metadata_style), Paragraph("ZedBoard - Zynq XC7Z020", metadata_style)],
                [Paragraph("WORKLOAD", metadata_style), Paragraph("CIFAR-10 whole-image classification", metadata_style)],
                [Paragraph("TOOLS", metadata_style), Paragraph("PyTorch, Vitis HLS, Vivado, Vitis bare-metal", metadata_style)],
            ],
            colWidths=[38 * mm, 123 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
                    ("BACKGROUND", (1, 0), (1, -1), WHITE),
                    ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            ),
        ),
        Spacer(1, 13 * mm),
        quote_box(
            "A defensible, source-grounded explanation of the original Zynq CNN classifier represented by the submitted resume bullets. This guide deliberately separates that project from the later EdgeDet-Z20 detector redesign.",
            styles,
        ),
        Spacer(1, 12 * mm),
        Paragraph(
            "Use this document to understand the architecture, explain design decisions, answer interview questions, and keep measured results separate from synthesis estimates.",
            styles["cover_body"],
        ),
        PageBreak(),
    ]


def build_pdf() -> None:
    register_fonts()
    styles = make_styles()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    doc = ResumeDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=19 * mm,
        bottomMargin=18 * mm,
        title="Hardware-Accelerated CNN Inference on Xilinx Zynq SoC",
        author="EdgeDet-Z20 project documentation",
        subject="Resume project context and interview preparation",
    )

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "TOC0",
            fontName="Body",
            fontSize=9.2,
            leading=13,
            leftIndent=0,
            firstLineIndent=0,
            textColor=INK,
            spaceBefore=3,
        )
    ]

    story = build_cover(styles)
    story.extend(
        [
            Paragraph("Contents", styles["h2"]),
            HRFlowable(width="100%", thickness=1, color=CYAN, spaceAfter=10),
            toc,
            PageBreak(),
        ]
    )
    story.extend(parse_markdown(SOURCE.read_text(encoding="utf-8"), styles))

    doc.multiBuild(story, onFirstPage=first_page, onLaterPages=later_pages)
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()
