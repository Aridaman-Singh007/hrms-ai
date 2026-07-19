#!/usr/bin/env python3
"""Evaluate the resume parser against local sample resumes.

Run from the repository root:

    python scripts/evaluate_resume_parser.py

Re-run only previously failed resumes (saves LLM tokens):

    python scripts/evaluate_resume_parser.py --only-failed

Re-run specific files by name or stem:

    python scripts/evaluate_resume_parser.py anish_SDE1_resume.pdf "Snesh's_Resume.pdf"

Or from backend (paths resolve to repo root):

    python ../scripts/evaluate_resume_parser.py --only-failed

Requires LLM credentials in ``backend/.env`` (Gemini or Bedrock via
``LLM_PROVIDER``) and sample files in ``sample_resumes/``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

# Paths: script lives in repo/scripts/, backend is sibling
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_ROOT = _REPO_ROOT / "backend"
sys.path.insert(0, str(_BACKEND_ROOT))
os.chdir(_BACKEND_ROOT)

from app.core.config import get_settings  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.parser.exceptions import (  # noqa: E402
    ExtractionError,
    LLMParsingError,
    ParserError,
    UnsupportedFileTypeError,
    ValidationError,
)
from app.parser.llm.client import generate_completion  # noqa: E402
from app.parser.llm.prompts import (  # noqa: E402
    RESUME_PARSER_SYSTEM_PROMPT,
    build_resume_parser_prompt,
)
from app.parser.llm.resume_parser import (  # noqa: E402
    _normalize_skills_in_payload,
    _parse_llm_json,
    _sanitize_payload,
    _validate_candidate_profile,
)
from app.parser.normalizers.resume import ResumeNormalizer  # noqa: E402
from app.parser.normalizers.skills import normalize_skills  # noqa: E402
from app.parser.pipeline import extract_resume_text  # noqa: E402
from app.schemas.resume import CandidateProfile  # noqa: E402

logger = logging.getLogger(__name__)

_RESUME_NORMALIZER = ResumeNormalizer()

SAMPLE_RESUMES_DIR = _REPO_ROOT / "sample_resumes"
OUTPUTS_DIR = _REPO_ROOT / "outputs"
RAW_DIR = OUTPUTS_DIR / "raw"
PARSED_DIR = OUTPUTS_DIR / "parsed"
FAILED_DIR = OUTPUTS_DIR / "failed"

_SUPPORTED_SUFFIXES = {".pdf", ".docx"}


@dataclass
class ResumeEvalResult:
    """Outcome for a single resume evaluation."""

    filename: str
    success: bool
    elapsed_seconds: float
    candidate_name: str | None = None
    normalized_skills: list[str] = field(default_factory=list)
    experience_count: int = 0
    education_count: int = 0
    error_stage: str | None = None
    error_message: str | None = None


@dataclass
class EvalMetrics:
    """Aggregate metrics across all resumes."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    total_seconds: float = 0.0

    @property
    def average_seconds(self) -> float:
        if self.total == 0:
            return 0.0
        return self.total_seconds / self.total


def _ensure_output_dirs() -> None:
    """Create output directories if they do not exist."""
    for directory in (RAW_DIR, PARSED_DIR, FAILED_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured output directory: %s", directory)


def _discover_resumes(
    *,
    only_failed: bool = False,
    names: list[str] | None = None,
) -> list[Path]:
    """Return supported resume files from ``sample_resumes/``.

    Args:
        only_failed: If True, restrict to stems present under ``outputs/failed/``.
        names: Optional filenames or stems to include (case-insensitive match).
    """
    if not SAMPLE_RESUMES_DIR.exists():
        logger.warning("Sample resumes directory does not exist: %s", SAMPLE_RESUMES_DIR)
        return []

    files = sorted(
        path
        for path in SAMPLE_RESUMES_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES
    )

    if only_failed:
        failed_stems = {
            path.stem
            for path in FAILED_DIR.glob("*.json")
            if path.is_file()
        }
        if not failed_stems:
            logger.warning("No failed resume records found in %s", FAILED_DIR)
            return []
        files = [path for path in files if path.stem in failed_stems]
        logger.info("Filtered to %d previously failed resume(s)", len(files))

    if names:
        wanted = {name.strip().lower() for name in names if name.strip()}
        files = [
            path
            for path in files
            if path.name.lower() in wanted or path.stem.lower() in wanted
        ]
        logger.info("Filtered to %d resume(s) matching name args", len(files))

    logger.info("Selected %d resume(s) from %s", len(files), SAMPLE_RESUMES_DIR)
    return files


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the resume parser against sample resumes.",
    )
    parser.add_argument(
        "--only-failed",
        action="store_true",
        help="Only re-run resumes listed under outputs/failed/.",
    )
    parser.add_argument(
        "names",
        nargs="*",
        help="Optional resume filenames or stems to evaluate.",
    )
    return parser.parse_args(argv)


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    logger.debug("Wrote %s (%d chars)", path, len(content))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.debug("Wrote %s", path)


def _save_failure(stem: str, *, stage: str, error: str, detail: str | None = None) -> None:
    """Persist failure details under ``outputs/failed/``."""
    payload = {
        "stage": stage,
        "error": error,
    }
    if detail:
        payload["detail"] = detail

    _write_json(FAILED_DIR / f"{stem}.json", payload)


def _parse_llm_to_profile(raw_response: str) -> CandidateProfile:
    """Parse raw LLM output through sanitize, skill normalize, validate, and enrich."""
    payload = _parse_llm_json(raw_response)
    sanitized = _sanitize_payload(payload)
    normalized = _normalize_skills_in_payload(sanitized)
    profile = _validate_candidate_profile(normalized)
    return _RESUME_NORMALIZER.normalize(profile)


def _profile_to_dict(profile: CandidateProfile) -> dict:
    return profile.model_dump(mode="json")


def evaluate_resume(resume_path: Path) -> ResumeEvalResult:
    """Run the full parse pipeline for one resume file."""
    stem = resume_path.stem
    filename = resume_path.name
    started = time.perf_counter()

    logger.info("Evaluating resume: %s", filename)

    try:
        file_content = resume_path.read_bytes()
        resume_text = extract_resume_text(file_content, filename)

        if not resume_text.strip():
            raise ExtractionError("No text extracted from resume")

        user_prompt = build_resume_parser_prompt(resume_text)
        raw_response = generate_completion(RESUME_PARSER_SYSTEM_PROMPT, user_prompt)
        _write_text(RAW_DIR / f"{stem}.txt", raw_response)

        profile = _parse_llm_to_profile(raw_response)
        parsed_dict = _profile_to_dict(profile)
        _write_json(PARSED_DIR / f"{stem}.json", parsed_dict)

        skill_names = [skill.name for skill in profile.skills if skill.name]
        normalized = normalize_skills(skill_names)

        elapsed = time.perf_counter() - started
        logger.info("Successfully parsed %s in %.2fs", filename, elapsed)

        return ResumeEvalResult(
            filename=filename,
            success=True,
            elapsed_seconds=elapsed,
            candidate_name=profile.full_name,
            normalized_skills=normalized,
            experience_count=len(profile.experience),
            education_count=len(profile.education),
        )

    except UnsupportedFileTypeError as exc:
        return _handle_failure(stem, filename, started, "extraction", exc)
    except ExtractionError as exc:
        return _handle_failure(stem, filename, started, "extraction", exc)
    except LLMParsingError as exc:
        return _handle_failure(stem, filename, started, "llm", exc, save_raw=True)
    except ValidationError as exc:
        return _handle_failure(stem, filename, started, "validation", exc, save_raw=True)
    except ParserError as exc:
        return _handle_failure(stem, filename, started, "parser", exc)
    except Exception as exc:
        return _handle_failure(
            stem,
            filename,
            started,
            "unexpected",
            exc,
            include_traceback=True,
        )


def _handle_failure(
    stem: str,
    filename: str,
    started: float,
    stage: str,
    exc: Exception,
    *,
    save_raw: bool = False,
    include_traceback: bool = False,
) -> ResumeEvalResult:
    """Log, persist, and return a failed evaluation result."""
    elapsed = time.perf_counter() - started
    error_message = str(exc)
    detail = traceback.format_exc() if include_traceback else None

    logger.error("Failed to parse %s at stage '%s': %s", filename, stage, error_message)
    _save_failure(stem, stage=stage, error=error_message, detail=detail)

    if save_raw:
        raw_path = RAW_DIR / f"{stem}.txt"
        if raw_path.exists():
            logger.debug("Raw LLM output preserved at %s", raw_path)

    return ResumeEvalResult(
        filename=filename,
        success=False,
        elapsed_seconds=elapsed,
        error_stage=stage,
        error_message=error_message,
    )


def _print_result(result: ResumeEvalResult) -> None:
    """Print a human-readable summary for one resume."""
    status = "SUCCESS" if result.success else "FAILURE"
    print("-" * 60)
    print(f"File:       {result.filename}")
    print(f"Status:     {status}")
    print(f"Time:       {result.elapsed_seconds:.2f}s")

    if result.success:
        print(f"Name:       {result.candidate_name or '(not found)'}")
        print(f"Skills:     {', '.join(result.normalized_skills) or '(none)'}")
        print(f"Experience: {result.experience_count}")
        print(f"Education:  {result.education_count}")
    else:
        print(f"Stage:      {result.error_stage}")
        print(f"Error:      {result.error_message}")


def _print_metrics_summary(metrics: EvalMetrics, results: list[ResumeEvalResult]) -> None:
    """Print aggregate parsing metrics."""
    print("=" * 60)
    print("PARSING METRICS SUMMARY")
    print("=" * 60)
    print(f"Total resumes:     {metrics.total}")
    print(f"Succeeded:         {metrics.succeeded}")
    print(f"Failed:            {metrics.failed}")
    print(f"Success rate:      {metrics.succeeded / metrics.total * 100:.1f}%" if metrics.total else "N/A")
    print(f"Total time:        {metrics.total_seconds:.2f}s")
    print(f"Average time:      {metrics.average_seconds:.2f}s")

    if metrics.failed:
        print("\nFailed files:")
        for result in results:
            if not result.success:
                print(f"  - {result.filename} ({result.error_stage}): {result.error_message}")

    print("=" * 60)
    print(f"Outputs written to: {_REPO_ROOT / 'outputs'}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()
    setup_logging(settings.log_level)

    provider = settings.llm_provider.strip().lower() or "gemini"
    if provider == "bedrock":
        if not settings.aws_access_key_id or not settings.aws_secret_access_key:
            print("FAIL: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY not set in backend/.env")
            return 1
        model_label = settings.bedrock_model_id
    else:
        if not settings.gemini_api_key:
            print("FAIL: GEMINI_API_KEY is not set in backend/.env")
            return 1
        model_label = settings.gemini_model

    _ensure_output_dirs()
    resume_files = _discover_resumes(
        only_failed=args.only_failed,
        names=args.names or None,
    )

    if not resume_files:
        if args.only_failed:
            print(f"No matching failed resumes found under {FAILED_DIR}")
        elif args.names:
            print(f"No resumes matched: {', '.join(args.names)}")
        else:
            print(f"No resumes found in {SAMPLE_RESUMES_DIR}")
            print("Add .pdf or .docx files and re-run.")
        return 1

    print("=" * 60)
    print("Resume Parser Evaluation")
    print("=" * 60)
    print(f"Samples:  {SAMPLE_RESUMES_DIR}")
    print(f"Outputs:  {OUTPUTS_DIR}")
    print(f"Provider: {provider}")
    print(f"Model:    {model_label}")
    if args.only_failed:
        print("Filter:   only previously failed")
    if args.names:
        print(f"Names:    {', '.join(args.names)}")
    print(f"Selected: {len(resume_files)} resume(s)")
    print()

    metrics = EvalMetrics(total=len(resume_files))
    results: list[ResumeEvalResult] = []

    for resume_path in resume_files:
        result = evaluate_resume(resume_path)
        results.append(result)
        metrics.total_seconds += result.elapsed_seconds

        if result.success:
            metrics.succeeded += 1
            # Clear stale failure record if this run succeeded.
            stale_failure = FAILED_DIR / f"{resume_path.stem}.json"
            if stale_failure.exists():
                stale_failure.unlink()
                logger.info("Removed stale failure record: %s", stale_failure.name)
        else:
            metrics.failed += 1

        _print_result(result)
        print()

    _print_metrics_summary(metrics, results)
    return 0 if metrics.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
