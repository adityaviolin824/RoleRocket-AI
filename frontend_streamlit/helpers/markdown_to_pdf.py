import io
import re
from html.parser import HTMLParser

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from markdown import markdown
import pandas as pd


class HTMLStripper(HTMLParser):
    """
    Convert HTML to plain text while preserving:
    - Paragraph breaks
    - List bullets
    - Headings as their own lines
    """

    def __init__(self):
        super().__init__()
        self.chunks = []

    def _newline(self):
        if not self.chunks:
            return
        if not self.chunks[-1].endswith("\n"):
            self.chunks.append("\n")

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._newline()
        elif tag == "li":
            self._newline()
            self.chunks.append("• ")
        elif tag == "br":
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.chunks.append("\n")

    def handle_data(self, data):
        # Skip pure whitespace chunks
        if data.strip():
            self.chunks.append(data)

    def get_text(self):
        return "".join(self.chunks)


def strip_html(html: str) -> str:
    stripper = HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


def _wrap_line(text, font_name, font_size, max_width):
    """
    Word-wrap a single logical line into multiple physical lines
    based on available width.
    """
    words = text.split()
    if not words:
        return [""]

    lines = []
    current = words[0]

    for word in words[1:]:
        candidate = current + " " + word
        w = pdfmetrics.stringWidth(candidate, font_name, font_size)
        if w <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


def markdown_to_pdf_bytes(md_text: str, title: str = "RoleRocket Report") -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_left = 72
    margin_right = 72
    margin_bottom = 72

    base_font = "Times-Roman"
    bold_font = "Times-Bold"
    header_font = bold_font

    content_font_size = 11
    line_height = 15  

    usable_width = width - margin_left - margin_right

    def draw_header():
        p.setFont(header_font, 12)
        header_title = title if len(title) <= 50 else title[:47] + "..."
        p.drawString(margin_left, height - 40, header_title)

        p.setFont(base_font, 9)
        timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
        p.drawRightString(width - margin_left, height - 40, timestamp)

    draw_header()
    p.setFont(bold_font, 24)
    p.drawCentredString(width / 2, height - 120, title)
    p.line(margin_left, height - 160, width - margin_left, height - 160)
    p.showPage()

    draw_header()
    p.setFont(base_font, content_font_size)
    y = height - 100

    html_content = markdown(md_text, output_format="html5")
    plain_text = strip_html(html_content)

    logical_lines = plain_text.split("\n")

    for raw_line in logical_lines:
        line = raw_line.rstrip()

        if not line.strip():
            y -= line_height
            if y < margin_bottom + line_height:
                p.showPage()
                draw_header()
                p.setFont(base_font, content_font_size)
                y = height - 80
            continue

        is_bullet_or_heading = (
            re.match(r"^\d+\.", line)  # numbered list
            or line.lstrip().startswith(("•", "-", "*"))
            or line.startswith("Why ")
            or line.startswith("Gaps")
        )

        font_name = bold_font if is_bullet_or_heading else base_font
        p.setFont(font_name, content_font_size)

        wrapped_lines = _wrap_line(line, font_name, content_font_size, usable_width)

        for wline in wrapped_lines:
            if y < margin_bottom + line_height:
                p.showPage()
                draw_header()
                p.setFont(font_name, content_font_size)
                y = height - 80

            p.drawString(margin_left, y, wline)
            y -= line_height

        p.setFont(base_font, content_font_size)

    p.save()
    buffer.seek(0)
    return buffer.getvalue()
