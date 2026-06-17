from io import BytesIO
from typing import BinaryIO, Union

from pypdf import PdfReader


PdfInput = Union[bytes, BinaryIO]


def extract_pdf_text(file: PdfInput) -> str:
    """Extract text from a PDF file-like object or bytes."""
    source = BytesIO(file) if isinstance(file, bytes) else file
    reader = PdfReader(source)
    pages = []

    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())

    return "\n\n".join(pages).strip()
