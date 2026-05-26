"""Temporary file utilities for uploaded resume processing."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

logger = logging.getLogger(__name__)

_DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB — stream without loading full file into memory
_TEMP_UPLOAD_DIR = Path(tempfile.gettempdir()) / "hrms-ai" / "uploads"


def _resolve_extension(filename: str | None) -> str:
    """Return a normalized extension including the leading dot, or empty string."""
    if not filename:
        return ""

    suffix = Path(filename).suffix.lower()
    if suffix and len(suffix) <= 10:
        return suffix

    return ""


def _build_temp_path(original_filename: str | None, temp_dir: Path | None = None) -> Path:
    """Generate a unique path preserving the original file extension."""
    base_dir = temp_dir or _TEMP_UPLOAD_DIR
    base_dir.mkdir(parents=True, exist_ok=True)

    extension = _resolve_extension(original_filename)
    unique_name = f"{uuid4().hex}{extension}"
    return base_dir / unique_name


async def save_temp_file(
    upload: UploadFile,
    *,
    temp_dir: Path | None = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> Path:
    """Stream an uploaded file to a uniquely named temporary path.

    Uses chunked async reads so large resumes are not held fully in memory.

    Args:
        upload: FastAPI ``UploadFile`` from an incoming request.
        temp_dir: Optional directory for temp files (created if missing).
        chunk_size: Bytes per read/write cycle.

    Returns:
        Absolute path to the saved temporary file.

    Raises:
        ValueError: When the upload has no readable content.
        OSError: When the file cannot be written to disk.
    """
    destination = _build_temp_path(upload.filename, temp_dir)

    logger.info(
        "Saving upload '%s' to temp file '%s'",
        upload.filename or "<unnamed>",
        destination,
    )

    total_bytes = 0

    try:
        with destination.open("wb") as buffer:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break
                buffer.write(chunk)
                total_bytes += len(chunk)
    except Exception:
        logger.exception("Failed while writing temp file '%s'", destination)
        await cleanup_temp_file(destination)
        raise

    if total_bytes == 0:
        await cleanup_temp_file(destination)
        logger.error("Upload '%s' was empty", upload.filename or "<unnamed>")
        raise ValueError("Uploaded file is empty")

    logger.info(
        "Saved temp file '%s' (%d bytes)",
        destination,
        total_bytes,
    )
    return destination


async def cleanup_temp_file(path: Path | str) -> None:
    """Remove a temporary file if it exists.

    Safe to call multiple times or when the file is already deleted.

    Args:
        path: Path returned by ``save_temp_file`` or equivalent.
    """
    file_path = Path(path)

    if not file_path.exists():
        logger.debug("Temp file already absent, nothing to clean: '%s'", file_path)
        return

    try:
        await asyncio.to_thread(file_path.unlink)
        logger.info("Cleaned up temp file '%s'", file_path)
    except OSError:
        logger.exception("Failed to delete temp file '%s'", file_path)
        raise
