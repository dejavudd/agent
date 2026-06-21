"""PDF parsing for course-material ingestion."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedPDF:
    source: Path
    page_texts: list[str] = field(default_factory=list)
    image_paths: list[Path] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(
            f"[page {i + 1}]\n{text}"
            for i, text in enumerate(self.page_texts)
            if text.strip()
        )


def parse_pdf(
    pdf_path: Path,
    image_dir: Path,
    dpi: int = 150,
    *,
    ocr: bool = True,
    ocr_langs: str = "chi_sim+eng",
    ocr_min_chars: int = 40,
) -> ParsedPDF:
    """Extract per-page text and render per-page PNGs from one PDF."""
    try:
        import fitz
    except ModuleNotFoundError as exc:
        raise RuntimeError("pymupdf is not installed. Run: pip install -r requirements.txt") from exc

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.stat().st_size == 0:
        raise ValueError(f"PDF is empty (0 bytes), likely a failed upload: {pdf_path.name}")
    image_dir.mkdir(parents=True, exist_ok=True)

    use_ocr = ocr
    if use_ocr:
        from core.ocr import ocr_available
        use_ocr = ocr_available()

    result = ParsedPDF(source=pdf_path)
    zoom = dpi / 72.0
    with fitz.open(pdf_path) as doc:
        matrix = fitz.Matrix(zoom, zoom)
        for index, page in enumerate(doc):
            text = page.get_text("text")
            image_path = image_dir / f"{pdf_path.stem}_p{index + 1:03d}.png"
            page.get_pixmap(matrix=matrix).save(image_path)
            result.image_paths.append(image_path)
            if use_ocr and len(text.strip()) < ocr_min_chars:
                from core.ocr import ocr_image
                ocr_text = ocr_image(image_path, langs=ocr_langs)
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
            result.page_texts.append(text)
    return result


def parse_week_inputs(
    input_dir: Path,
    image_dir: Path,
    *,
    ocr: bool = True,
    ocr_langs: str = "chi_sim+eng",
    ocr_min_chars: int = 40,
) -> list[ParsedPDF]:
    """Parse every PDF in a week's input folder."""
    return [
        parse_pdf(pdf, image_dir, ocr=ocr, ocr_langs=ocr_langs, ocr_min_chars=ocr_min_chars)
        for pdf in sorted(input_dir.glob("*.pdf"))
    ]
