"""Resume parsing API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.parser.exceptions import (
    ExtractionError,
    LLMParsingError,
    UnsupportedFileTypeError,
    ValidationError,
)
from app.schemas.parser import ParserErrorResponse, ResumeParseResponse
from app.services.resume_parser_service import ResumeParserService

router = APIRouter(tags=["parser"])
logger = logging.getLogger(__name__)


def get_resume_parser_service(
    settings: Settings = Depends(get_settings),
) -> ResumeParserService:
    """Provide a configured resume parser service instance."""
    return ResumeParserService(max_upload_bytes=settings.max_upload_bytes)


def _error_response(status_code: int, detail: str, error_code: str) -> JSONResponse:
    payload = ParserErrorResponse(detail=detail, error_code=error_code)
    return JSONResponse(status_code=status_code, content=payload.model_dump())


@router.post(
    "/resume",
    response_model=ResumeParseResponse,
    status_code=status.HTTP_200_OK,
    summary="Parse an uploaded resume",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ParserErrorResponse},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ParserErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ParserErrorResponse},
        status.HTTP_502_BAD_GATEWAY: {"model": ParserErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ParserErrorResponse},
    },
)
async def parse_resume(
    file: UploadFile = File(..., description="Resume file (.pdf or .docx)"),
    service: ResumeParserService = Depends(get_resume_parser_service),
) -> ResumeParseResponse | JSONResponse:
    """Accept a multipart resume upload, extract text, and return a structured profile."""
    filename = file.filename or "<unnamed>"
    logger.info(
        "Received resume parse request filename=%s content_type=%s",
        filename,
        file.content_type,
    )

    try:
        result = await service.parse_upload(file)
    except UnsupportedFileTypeError as exc:
        logger.warning("Unsupported resume file type filename=%s: %s", filename, exc)
        return _error_response(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            str(exc),
            "unsupported_file_type",
        )
    except ValueError as exc:
        logger.warning("Invalid resume upload filename=%s: %s", filename, exc)
        return _error_response(
            status.HTTP_400_BAD_REQUEST,
            str(exc),
            "invalid_upload",
        )
    except ExtractionError as exc:
        logger.error("Resume extraction failed filename=%s: %s", filename, exc)
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            str(exc),
            "extraction_failed",
        )
    except ValidationError as exc:
        logger.error("Resume validation failed filename=%s: %s", filename, exc)
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            str(exc),
            "validation_failed",
        )
    except LLMParsingError as exc:
        logger.error("LLM resume parse failed filename=%s: %s", filename, exc)
        return _error_response(
            status.HTTP_502_BAD_GATEWAY,
            str(exc),
            "llm_parsing_failed",
        )
    except Exception:
        logger.exception("Unhandled error while parsing resume filename=%s", filename)
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "An unexpected error occurred while parsing the resume",
            "internal_error",
        )

    logger.info(
        "Resume parse request succeeded filename=%s chars=%d",
        result.filename,
        len(result.extracted_text),
    )
    return result
