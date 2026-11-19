import io

import pytest
from fastapi import HTTPException
from PIL import Image

from app.services import ocr_service


def make_png_bytes(width=120, height=80):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_validate_image_bytes_accepts_supported_png():
    assert ocr_service.validate_image_bytes(make_png_bytes()) is True


def test_validate_image_bytes_rejects_invalid_image():
    with pytest.raises(HTTPException) as error:
        ocr_service.validate_image_bytes(b"not-an-image")

    assert error.value.status_code == 400


def test_preprocess_image_returns_grayscale_image():
    processed = ocr_service.preprocess_image(make_png_bytes())

    assert processed.mode == "L"
    assert processed.size == (120, 80)


def test_preprocess_image_limits_large_dimensions():
    processed = ocr_service.preprocess_image(
        make_png_bytes(width=3400, height=3200)
    )

    assert processed.width <= 3000
    assert processed.height <= 3000


def test_extract_text_from_image_returns_extracted_text(monkeypatch):
    monkeypatch.setattr(ocr_service, "configure_tesseract", lambda: None)
    monkeypatch.setattr(
        ocr_service.pytesseract,
        "image_to_string",
        lambda image, lang, config, timeout: "  Handwritten answer text  ",
    )

    result = ocr_service.extract_text_from_image(make_png_bytes())

    assert result["success"] is True
    assert result["extracted_text"] == "Handwritten answer text"
    assert result["character_count"] == len("Handwritten answer text")
    assert result["word_count"] == 3
    assert result["requires_manual_review"] is True


def test_extract_text_from_image_requests_manual_review_when_empty(monkeypatch):
    monkeypatch.setattr(ocr_service, "configure_tesseract", lambda: None)
    monkeypatch.setattr(
        ocr_service.pytesseract,
        "image_to_string",
        lambda image, lang, config, timeout: "   ",
    )

    result = ocr_service.extract_text_from_image(make_png_bytes())

    assert result["success"] is True
    assert result["extracted_text"] == ""
    assert result["requires_manual_review"] is True
    assert "No readable text" in result["message"]


def test_extract_text_from_image_reports_missing_tesseract(monkeypatch):
    def missing_tesseract():
        raise RuntimeError("Tesseract OCR is not installed.")

    monkeypatch.setattr(
        ocr_service,
        "configure_tesseract",
        missing_tesseract,
    )

    with pytest.raises(HTTPException) as error:
        ocr_service.extract_text_from_image(make_png_bytes())

    assert error.value.status_code == 503
    assert "Tesseract OCR is not installed" in error.value.detail


def test_extract_text_from_image_rejects_unsafe_language_identifier():
    with pytest.raises(HTTPException) as error:
        ocr_service.extract_text_from_image(
            make_png_bytes(),
            language="eng; rm -rf /",
        )

    assert error.value.status_code == 400
    assert "Invalid OCR language" in error.value.detail
