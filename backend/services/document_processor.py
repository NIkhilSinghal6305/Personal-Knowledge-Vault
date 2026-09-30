import re
from pathlib import Path

from .chunker import chunk_text  # noqa: F401  (re-exported)


class DocumentError(Exception):
    """Raised with a user-friendly message when a document cannot be processed."""


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_pdf_text(path: Path) -> list[tuple[str | None, str]]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise DocumentError("This PDF is password-protected.")
        return [(f"Page {i}", page.extract_text() or "") for i, page in enumerate(reader.pages, 1)]
    except DocumentError:
        raise
    except Exception:
        raise DocumentError("This PDF appears to be corrupted or unreadable.")


def extract_docx_text(path: Path) -> list[tuple[str | None, str]]:
    try:
        from docx import Document

        doc = Document(str(path))
        paragraphs = list(doc.paragraphs)
    except Exception:
        raise DocumentError("This DOCX file appears to be corrupted.")
    sections, heading, buf = [], None, []

    def flush():
        if buf:
            sections.append((f"Section: {heading}" if heading else None, "\n".join(buf)))
            buf.clear()

    for p in paragraphs:
        text = p.text.strip()
        if not text:
            continue
        if p.style is not None and (p.style.name or "").lower().startswith("heading"):
            flush()
            heading = text
        buf.append(text)
    flush()
    return sections


def extract_txt_text(path: Path) -> list[tuple[str | None, str]]:
    try:
        return [(None, Path(path).read_text(encoding="utf-8", errors="replace"))]
    except OSError:
        raise DocumentError("The text file could not be read.")


def extract(path: Path, file_type: str) -> list[tuple[str | None, str]]:
    extractors = {"pdf": extract_pdf_text, "docx": extract_docx_text, "txt": extract_txt_text}
    if file_type not in extractors:
        raise DocumentError("Unsupported file type. Use PDF, DOCX or TXT.")
    sections = [(loc, clean_text(t)) for loc, t in extractors[file_type](Path(path))]
    sections = [(loc, t) for loc, t in sections if t]
    if not sections:
        raise DocumentError("This document is empty or has no extractable text (scanned PDFs need OCR).")
    return sections
