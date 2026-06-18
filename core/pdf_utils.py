from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Union
from xml.etree import ElementTree
from zipfile import ZipFile

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


def _decode_text(file_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return file_bytes.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="ignore").strip()


def extract_docx_text(file: PdfInput) -> str:
    source = BytesIO(file) if isinstance(file, bytes) else file
    paragraphs = []
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    with ZipFile(source) as docx:
        xml_content = docx.read("word/document.xml")
        root = ElementTree.fromstring(xml_content)
        for paragraph in root.findall(".//w:p", namespace):
            runs = [
                node.text or ""
                for node in paragraph.findall(".//w:t", namespace)
            ]
            text = "".join(runs).strip()
            if text:
                paragraphs.append(text)

    return "\n".join(paragraphs).strip()


def extract_document_text(file_bytes: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(file_bytes)
    if suffix == ".docx":
        return extract_docx_text(file_bytes)
    if suffix in {".txt", ".md", ".markdown"}:
        return _decode_text(file_bytes)
    raise ValueError(f"暂不支持的简历文件格式：{suffix or '未知'}")
