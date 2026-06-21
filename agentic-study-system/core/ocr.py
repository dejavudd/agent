"""Local OCR for scanned or image-based course PDFs."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


class OCRUnavailable(RuntimeError):
    """Raised with an actionable fix hint when OCR cannot run."""


@lru_cache(maxsize=1)
def ocr_available() -> bool:
    """True if both the pytesseract wrapper and the tesseract binary are present."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _require() -> None:
    if ocr_available():
        return
    try:
        import pytesseract  # noqa: F401
    except ModuleNotFoundError as exc:
        raise OCRUnavailable(
            "The 'pytesseract' package is not installed. Run: pip install -r requirements.txt"
        ) from exc
    raise OCRUnavailable(
        "The Tesseract OCR binary is not available on PATH. Install Tesseract "
        "with Chinese language data, then retry. Text-based PDFs can still work without OCR."
    )


def ocr_image(png_path: Path | str, langs: str = "chi_sim+eng") -> str:
    """Return text read from one rendered page image."""
    _require()
    import pytesseract

    try:
        return pytesseract.image_to_string(str(png_path), lang=langs).strip()
    except Exception:
        return ""
