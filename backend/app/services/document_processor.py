import fitz  # PyMuPDF
import docx
import subprocess
import uuid
import re
from pathlib import Path
from app.models.schemas import ChunkPayload, DocumentMetadata

# 제안서 섹션 헤더 패턴 (목차 기반 분할)
SECTION_PATTERNS = [
    re.compile(r"^\s*제\s*\d+\s*[장절항]"),        # 제1장, 제2절
    re.compile(r"^\s*\d+\s*\.\s*[가-힣A-Za-z]"),   # 1. 사업개요
    re.compile(r"^\s*[가-힣]\s*\.\s*[가-힣A-Za-z]"), # 가. 추진전략
    re.compile(r"^\s*[①②③④⑤⑥⑦⑧⑨⑩]"),          # ① 항목
]


def is_section_header(line: str) -> bool:
    return any(p.match(line) for p in SECTION_PATTERNS)


def _extract_pdf_pages(path: str) -> list[dict]:
    doc = fitz.open(path)
    return [{"page": i + 1, "text": page.get_text()} for i, page in enumerate(doc)]


def _extract_docx_pages(path: str) -> list[dict]:
    document = docx.Document(path)
    text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
    return [{"page": 1, "text": text}]


def _hwp_to_pdf(hwp_path: str) -> str:
    output_dir = "/tmp/rag_converted"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", output_dir, hwp_path],
        check=True,
        capture_output=True,
    )
    return f"{output_dir}/{Path(hwp_path).stem}.pdf"


def extract_pages(file_path: str) -> list[dict]:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return _extract_pdf_pages(file_path)
    elif ext == ".docx":
        return _extract_docx_pages(file_path)
    elif ext == ".hwp":
        pdf_path = _hwp_to_pdf(file_path)
        return _extract_pdf_pages(pdf_path)
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {ext}")


def semantic_chunk(pages: list[dict], metadata: DocumentMetadata) -> list[ChunkPayload]:
    chunks: list[ChunkPayload] = []
    current_section = "본문"
    current_lines: list[str] = []
    current_page = 1

    def flush(page: int):
        text = "\n".join(current_lines).strip()
        if len(text) > 50:  # 너무 짧은 조각은 무시
            meta = metadata.model_dump(exclude={"page"})  # page는 청크별로 따로 지정
            chunks.append(ChunkPayload(
                chunk_id=str(uuid.uuid4()),
                text=text,
                section=current_section,
                page=page,
                **meta,
            ))

    for page_data in pages:
        for line in page_data["text"].split("\n"):
            line = line.strip()
            if not line:
                continue
            if is_section_header(line):
                flush(current_page)
                current_section = line
                current_lines = []
            else:
                current_lines.append(line)
        current_page = page_data["page"]

    flush(current_page)
    return chunks
