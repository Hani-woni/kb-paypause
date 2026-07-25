"""[B 소유] ocr_parser.py

계약서 이미지 또는 PDF에서 텍스트를 추출하고,
contract_parser.parse()를 이용해 contract_data를 생성한다.

처리 방식
---------
1. 텍스트가 포함된 PDF:
   PyMuPDF로 텍스트를 직접 추출한다.

2. 스캔 PDF:
   PDF 페이지를 이미지로 변환한 뒤 EasyOCR을 적용한다.

3. PNG / JPG / JPEG:
   EasyOCR을 직접 적용한다.

주의
----
- 확인되지 않은 계약정보를 임의로 생성하지 않는다.
- OCR 결과가 없더라도 예외 대신 안전한 빈 결과를 반환한다.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import easyocr
import fitz
import numpy as np
from PIL import Image

from contract_parser import parse


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | {".pdf"}

PDF_TEXT_MIN_LENGTH = 30
PDF_RENDER_DPI = 200


@lru_cache(maxsize=1)
def _get_reader() -> easyocr.Reader:
    """EasyOCR 모델을 최초 한 번만 로드한다.

    한국어 계약서를 대상으로 하므로 한국어와 영어를 함께 사용한다.
    GPU가 없는 환경에서도 동작하도록 CPU 모드로 고정한다.
    """
    return easyocr.Reader(
        ["ko", "en"],
        gpu=False,
    )


def _normalize_text(text: str) -> str:
    """추출된 텍스트의 공백과 빈 줄을 정리한다."""
    if not isinstance(text, str):
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []

    for line in text.splitlines():
        cleaned = " ".join(line.split())

        if cleaned:
            lines.append(cleaned)

    return "\n".join(lines).strip()


def _ocr_image(image: Image.Image) -> str:
    """PIL 이미지를 EasyOCR로 인식한다."""
    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")

    image_array = np.array(image)

    reader = _get_reader()
    results = reader.readtext(
        image_array,
        detail=0,
        paragraph=False,
    )

    lines = [
        str(result).strip()
        for result in results
        if str(result).strip()
    ]

    return _normalize_text("\n".join(lines))


def _extract_text_from_image(file_path: Path) -> str:
    """이미지 파일에서 OCR 텍스트를 추출한다."""
    try:
        with Image.open(file_path) as image:
            return _ocr_image(image)
    except OSError as exc:
        raise ValueError(
            f"이미지 파일을 열 수 없습니다: {file_path}"
        ) from exc


def _render_pdf_page(
    page: fitz.Page,
    dpi: int = PDF_RENDER_DPI,
) -> Image.Image:
    """PDF 페이지를 OCR 가능한 PIL 이미지로 변환한다."""
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    pixmap = page.get_pixmap(
        matrix=matrix,
        alpha=False,
    )

    mode = "RGB"

    return Image.frombytes(
        mode,
        (pixmap.width, pixmap.height),
        pixmap.samples,
    )


def _extract_text_from_pdf(file_path: Path) -> str:
    """PDF에서 텍스트를 추출한다.

    각 페이지에 텍스트 레이어가 충분하면 직접 추출하고,
    텍스트가 거의 없으면 해당 페이지만 OCR 처리한다.
    """
    page_texts = []

    try:
        document = fitz.open(file_path)
    except (fitz.FileDataError, RuntimeError) as exc:
        raise ValueError(
            f"PDF 파일을 열 수 없습니다: {file_path}"
        ) from exc

    try:
        if document.page_count == 0:
            return ""

        for page in document:
            direct_text = _normalize_text(
                page.get_text("text")
            )

            if len(direct_text) >= PDF_TEXT_MIN_LENGTH:
                page_texts.append(direct_text)
                continue

            image = _render_pdf_page(page)
            ocr_text = _ocr_image(image)

            if ocr_text:
                page_texts.append(ocr_text)

    finally:
        document.close()

    return _normalize_text("\n\n".join(page_texts))


def _empty_contract_data() -> dict:
    """OCR 실패 시에도 공통 구조를 유지하는 빈 데이터를 만든다."""
    return parse("")


def extract(file_path: str) -> tuple[str, dict]:
    """계약서 파일에서 OCR 원문과 contract_data를 반환한다.

    Parameters
    ----------
    file_path:
        PNG, JPG, JPEG 또는 PDF 파일 경로.

    Returns
    -------
    tuple[str, dict]
        첫 번째 값은 OCR 원문,
        두 번째 값은 contract_parser.parse() 결과.
    """
    if not isinstance(file_path, str) or not file_path.strip():
        return "", _empty_contract_data()

    path = Path(file_path).expanduser()

    if not path.exists():
        raise FileNotFoundError(
            f"계약서 파일을 찾을 수 없습니다: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"파일 경로가 아닙니다: {path}"
        )

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "지원하지 않는 파일 형식입니다. "
            "png, jpg, jpeg, pdf만 사용할 수 있습니다."
        )

    if extension == ".pdf":
        ocr_text = _extract_text_from_pdf(path)
    else:
        ocr_text = _extract_text_from_image(path)

    ocr_text = _normalize_text(ocr_text)
    contract_data = parse(ocr_text)

    return ocr_text, contract_data