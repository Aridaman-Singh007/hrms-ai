"""Temporary file utilities for uploaded resume processing.

Streams FastAPI ``UploadFile`` objects to disk with unique UUID filenames,
preserves the original extension, and exposes explicit async cleanup so
callers never leave resume bytes on disk longer than needed.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

logger = logging.getLogger(__name__)

_DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB — stream without loading the full file
_TEMP_UPLOAD_DIR = Path(tempfile.gettempdir()) / "hrms-ai" / "uploads"
_MAX_EXTENSION_LENGTH = 10


def _resolve_extension(filename: str | None) -> str:
    """Return a normalized extension including the leading dot, or empty string."""
    if not filename:
        return ""

    suffix = Path(filename).suffix.lower()
    # Reject absurd / path-like suffixes that could confuse tooling later.
    if not suffix or len(suffix) > _MAX_EXTENSION_LENGTH:
        return ""
    if not suffix[1:].isalnum():
        return ""

    return suffix


def _build_temp_path(original_filename: str | None, temp_dir: Path | None = None) -> Path:
    """Generate a unique absolute path preserving the original file extension."""
    base_dir = (temp_dir or _TEMP_UPLOAD_DIR).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    extension = _resolve_extension(original_filename)
    unique_name = f"{uuid4().hex}{extension}"
    return (base_dir / unique_name).resolve()


async def save_temp_file(
    upload: UploadFile,
    *,
    temp_dir: Path | None = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    max_bytes: int | None = None,
) -> Path:
    """Stream an uploaded file to a uniquely named temporary path.

    Uses chunked async reads so large resumes are never held fully in memory.
    Disk writes run in a worker thread to avoid blocking the event loop.

    Args:
        upload: FastAPI ``UploadFile`` from an incoming request.
        temp_dir: Optional directory for temp files (created if missing).
        chunk_size: Bytes per read/write cycle.
        max_bytes: Optional hard size limit; exceeding it raises ``ValueError``
            and deletes any partial file.

    Returns:
        Absolute path to the saved temporary file.

    Raises:
        ValueError: When the upload is empty or exceeds ``max_bytes``.
        OSError: When the file cannot be written to disk.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    if max_bytes is not None and max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer when set")

    destination = _build_temp_path(upload.filename, temp_dir)
    original_name = upload.filename or "<unnamed>"

    logger.info(
        "Saving upload filename=%s temp_path=%s chunk_size=%d max_bytes=%s",
        original_name,
        destination,
        chunk_size,
        max_bytes if max_bytes is not None else "none",
    )

    total_bytes = 0

    try:
        # Open / write / close on a worker thread so the async loop stays free.
        def _open() -> object:
            return destination.open("wb")

        buffer = await asyncio.to_thread(_open)
        try:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break

                total_bytes += len(chunk)
                if max_bytes is not None and total_bytes > max_bytes:
                    raise ValueError(
                        f"Uploaded file exceeds maximum size of {max_bytes} bytes"
                    )

                await asyncio.to_thread(buffer.write, chunk)
        finally:
            await asyncio.to_thread(buffer.close)
    except ValueError:
        logger.warning(
            "Rejected upload filename=%s temp_path=%s bytes_written=%d",
            original_name,
            destination,
            total_bytes,
        )
        await cleanup_temp_file(destination)
        raise
    except Exception:
        logger.exception(
            "Failed while writing temp file filename=%s temp_path=%s bytes_written=%d",
            original_name,
            destination,
            total_bytes,
        )
        await cleanup_temp_file(destination)
        raise
    finally:
        # Rewind so callers that re-read the same UploadFile still work.
        try:
            await upload.seek(0)
        except Exception:
            logger.debug("Upload seek(0) unavailable for filename=%s", original_name)

    if total_bytes == 0:
        await cleanup_temp_file(destination)
        logger.error("Upload was empty filename=%s", original_name)
        raise ValueError("Uploaded file is empty")

    logger.info(
        "Saved temp file filename=%s temp_path=%s size_bytes=%d",
        original_name,
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
        logger.debug("Temp file already absent path=%s", file_path)
        return

    try:
        await asyncio.to_thread(file_path.unlink)
        logger.info("Cleaned up temp file path=%s", file_path)
    except OSError:
        logger.exception("Failed to delete temp file path=%s", file_path)
        raise


@asynccontextmanager
async def temporary_upload(
    upload: UploadFile,
    *,
    temp_dir: Path | None = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    max_bytes: int | None = None,
) -> AsyncIterator[Path]:
    """Save an upload and always clean it up when the block exits.

    Example::

        async with temporary_upload(file) as path:
            data = path.read_bytes()
    """
    path = await save_temp_file(
        upload,
        temp_dir=temp_dir,
        chunk_size=chunk_size,
        max_bytes=max_bytes,
    )
    try:
        yield path
    finally:
        await cleanup_temp_file(path)
