"""
Document processing service.
Handles text extraction from PDF, DOCX, and TXT files,
text cleaning, and chunking for embedding.
"""
import re
import os
from typing import List, Tuple
from PyPDF2 import PdfReader
from docx import Document as DocxDocument


class DocumentProcessor:
    """Extracts and processes text from uploaded documents."""

    SUPPORTED_TYPES = {"pdf", "txt", "docx"}
    CHUNK_SIZE = 500  # characters per chunk
    CHUNK_OVERLAP = 50  # overlap between chunks

    @staticmethod
    def validate_file_type(filename: str) -> str:
        """Validate and return the file extension."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in DocumentProcessor.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported file type: .{ext}. Supported: {DocumentProcessor.SUPPORTED_TYPES}")
        return ext

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """Extract text from a PDF file."""
        try:
            reader = PdfReader(file_path)
            text_parts = []
            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"[Page {page_num + 1}]\n{page_text}")
            return "\n\n".join(text_parts)
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")

    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        """Extract text from a DOCX file."""
        try:
            doc = DocxDocument(file_path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n\n".join(paragraphs)
        except Exception as e:
            raise ValueError(f"Failed to extract text from DOCX: {str(e)}")

    @staticmethod
    def extract_text_from_txt(file_path: str) -> str:
        """Extract text from a TXT file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            raise ValueError(f"Failed to read TXT file: {str(e)}")

    @staticmethod
    def extract_text(file_path: str, file_type: str) -> str:
        """Extract text based on file type."""
        extractors = {
            "pdf": DocumentProcessor.extract_text_from_pdf,
            "docx": DocumentProcessor.extract_text_from_docx,
            "txt": DocumentProcessor.extract_text_from_txt,
        }
        extractor = extractors.get(file_type)
        if not extractor:
            raise ValueError(f"No extractor for file type: {file_type}")
        return extractor(file_path)

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean extracted text by removing excess whitespace and special chars."""
        # Remove null bytes
        text = text.replace("\x00", "")
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove excessive newlines (keep paragraph breaks)
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove non-printable characters (keep basic printable + newlines)
        text = re.sub(r"[^\x20-\x7E\n\r\t]", "", text)
        return text.strip()

    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        document_name: str = "unknown",
    ) -> List[dict]:
        """
        Split text into overlapping chunks for embedding.
        Returns a list of dicts with chunk text and metadata.
        """
        if not text or not text.strip():
            return []

        # Split by sentences for better chunking
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        current_chunk = ""
        chunk_index = 0

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(
                        {
                            "text": current_chunk.strip(),
                            "metadata": {
                                "document_name": document_name,
                                "chunk_index": chunk_index,
                                "char_start": max(0, len(text) - len(current_chunk)),
                            },
                        }
                    )
                    chunk_index += 1
                    # Keep overlap
                    overlap_text = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else ""
                    current_chunk = overlap_text + " " + sentence
                else:
                    # Single sentence larger than chunk_size — split by characters
                    for i in range(0, len(sentence), chunk_size - chunk_overlap):
                        sub = sentence[i : i + chunk_size]
                        chunks.append(
                            {
                                "text": sub.strip(),
                                "metadata": {
                                    "document_name": document_name,
                                    "chunk_index": chunk_index,
                                    "char_start": i,
                                },
                            }
                        )
                        chunk_index += 1
                    current_chunk = ""

        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append(
                {
                    "text": current_chunk.strip(),
                    "metadata": {
                        "document_name": document_name,
                        "chunk_index": chunk_index,
                        "char_start": 0,
                    },
                }
            )

        return chunks

    @staticmethod
    def process_document(file_path: str, file_type: str, document_name: str) -> Tuple[str, List[dict]]:
        """
        Full pipeline: extract → clean → chunk.
        Returns (full_text, chunks).
        """
        raw_text = DocumentProcessor.extract_text(file_path, file_type)
        if not raw_text or not raw_text.strip():
            raise ValueError("Document appears to be empty or could not be read.")
        cleaned_text = DocumentProcessor.clean_text(raw_text)
        chunks = DocumentProcessor.chunk_text(
            cleaned_text,
            chunk_size=DocumentProcessor.CHUNK_SIZE,
            chunk_overlap=DocumentProcessor.CHUNK_OVERLAP,
            document_name=document_name,
        )
        return cleaned_text, chunks
