
import io
import os
import shutil
from pathlib import Path

import pytesseract
from PIL import (
    Image,
    ImageEnhance,
    ImageFilter,
    ImageOps,
    UnidentifiedImageError,
)

from fastapi import HTTPException, status


# ==========================================
# CONFIGURATION
# ==========================================

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED_IMAGE_FORMATS = {
    "JPEG",
    "PNG",
    "WEBP",
    "TIFF",
    "BMP",
}

DEFAULT_OCR_LANGUAGE = "eng"

OCR_CONFIG = "--oem 3 --psm 6"


# ==========================================
# TESSERACT CONFIGURATION
# ==========================================

def configure_tesseract():
    """
    Configure the Tesseract executable.

    TESSERACT_CMD can be configured in the backend environment.
    """

    configured_path = os.getenv("TESSERACT_CMD")

    if configured_path:
        executable = Path(configured_path)

        if not executable.is_file():
            raise RuntimeError(
                "Configured Tesseract executable was not found."
            )

        pytesseract.pytesseract.tesseract_cmd = str(executable)

    elif shutil.which("tesseract") is None:
        raise RuntimeError(
            "Tesseract OCR is not installed or not available in PATH."
        )


# ==========================================
# IMAGE VALIDATION
# ==========================================

def validate_image_bytes(
    image_bytes: bytes,
):
    """Validate uploaded image data."""

    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An image file is required.",
        )

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image size cannot exceed 10 MB.",
        )

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image_format = image.format

            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Unsupported image format.",
                )

            image.verify()

    except HTTPException:
        raise

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not a valid image.",
        )

    return True


# ==========================================
# IMAGE PREPROCESSING
# ==========================================

def preprocess_image(
    image_bytes: bytes,
):
    """
    Prepare an image for OCR.

    Processing includes:
    - EXIF orientation correction
    - Grayscale conversion
    - Contrast enhancement
    - Noise reduction
    - Sharpening
    """

    validate_image_bytes(image_bytes)

    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            image = ImageOps.exif_transpose(source)
            image = image.convert("RGB")

            # Limit image dimensions to reduce memory usage.
            image.thumbnail(
                (3000, 3000),
                Image.Resampling.LANCZOS,
            )

            image = ImageOps.grayscale(image)

            image = ImageEnhance.Contrast(
                image
            ).enhance(1.8)

            image = image.filter(
                ImageFilter.MedianFilter(size=3)
            )

            image = ImageEnhance.Sharpness(
                image
            ).enhance(1.5)

            return image.copy()

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to process the uploaded image.",
        )


# ==========================================
# OCR TEXT EXTRACTION
# ==========================================

def extract_text_from_image(
    image_bytes: bytes,
    language: str = DEFAULT_OCR_LANGUAGE,
):
    """
    Extract text from an uploaded answer image.

    Returns extracted text for examiner review.
    OCR output is not an awarded examination score.
    """

    if not isinstance(language, str) or not language.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid OCR language is required.",
        )

    language = language.strip()

    # Restrict language identifiers to safe Tesseract syntax.
    if not all(
        character.isalnum() or character in "_+-"
        for character in language
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OCR language identifier.",
        )

    image = preprocess_image(image_bytes)

    try:
        configure_tesseract()

        extracted_text = pytesseract.image_to_string(
            image,
            lang=language,
            config=OCR_CONFIG,
            timeout=30,
        )

        extracted_text = extracted_text.strip()

        if not extracted_text:
            return {
                "success": True,
                "extracted_text": "",
                "message": (
                    "No readable text was detected. "
                    "The examiner should review the image manually."
                ),
                "requires_manual_review": True,
            }

        return {
            "success": True,
            "extracted_text": extracted_text,
            "character_count": len(extracted_text),
            "word_count": len(extracted_text.split()),
            "message": "Text extracted successfully.",
            "requires_manual_review": True,
        }

    except pytesseract.TesseractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tesseract OCR is not installed or configured.",
        )

    except pytesseract.TesseractError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Tesseract could not process the uploaded image.",
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


# ==========================================
# OCR FROM IMAGE FILE
# ==========================================

def extract_text_from_file(
    file_path: str,
    language: str = DEFAULT_OCR_LANGUAGE,
):
    """
    Extract text from an existing image file.

    The caller must provide a trusted server-side file path.
    """

    if not isinstance(file_path, str) or not file_path.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid image file path is required.",
        )

    path = Path(file_path)

    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found.",
        )

    try:
        file_size = path.stat().st_size

        if file_size > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Image size cannot exceed 10 MB.",
            )

        image_bytes = path.read_bytes()

    except HTTPException:
        raise

    except OSError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to read the image file.",
        )

    return extract_text_from_image(
        image_bytes=image_bytes,
        language=language,
    )
