from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _p(text: str) -> str:
    return escape(text).replace("\n", "<br/>")


def build_answer_pdf(question: str, answer: str, sources: list[dict], label: str) -> bytes:
    styles = getSampleStyleSheet()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm)
    body = [Paragraph("Personal Knowledge Vault", styles["Title"]), Spacer(1, 6),
            Paragraph("Question:", styles["Heading3"]), Paragraph(_p(question), styles["BodyText"]),
            Paragraph(f"Answer ({escape(label)}):", styles["Heading3"]), Paragraph(_p(answer), styles["BodyText"]),
            Paragraph("Sources:", styles["Heading3"])]
    if sources:
        for i, s in enumerate(sources, 1):
            loc = f" - {s['location']}" if s.get("location") else ""
            body.append(Paragraph(f"{i}. {_p(s['filename'] + loc)}", styles["BodyText"]))
    else:
        body.append(Paragraph("None", styles["BodyText"]))
    body += [Spacer(1, 12), Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Italic"])]
    doc.build(body)
    return buf.getvalue()
