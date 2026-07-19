#!/usr/bin/env python3
"""Integration test for the configured LLM client (Gemini or Bedrock).

Run from the backend directory:

    python scripts/test_llm.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Ensure backend root is on sys.path and cwd so .env is found
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))
os.chdir(_BACKEND_ROOT)

SYSTEM_PROMPT = "You are a JSON API."
USER_PROMPT = "Return a JSON object with keys hello and status."


def main() -> int:
    from app.core.config import get_settings
    from app.parser.exceptions import LLMParsingError, ParserError
    from app.parser.llm.client import generate_completion
    from app.parser.llm.utils import safe_json_loads

    settings = get_settings()
    provider = settings.llm_provider.strip().lower() or "gemini"

    print("=" * 60)
    print("LLM integration test")
    print("=" * 60)
    print(f"Provider: {provider}")

    if provider == "bedrock":
        print(f"Model:    {settings.bedrock_model_id}")
        print(f"Region:   {settings.aws_region}")
        print(f"AWS key set: {bool(settings.aws_access_key_id)}")
        print()
        if not settings.aws_access_key_id or not settings.aws_secret_access_key:
            print("FAIL: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY not set in backend/.env")
            return 1
    else:
        print(f"Model:    {settings.gemini_model}")
        print(f"API key set: {bool(settings.gemini_api_key)}")
        print()
        if not settings.gemini_api_key:
            print("FAIL: GEMINI_API_KEY is not set. Add it to backend/.env")
            return 1

    print("System prompt:", repr(SYSTEM_PROMPT))
    print("User prompt:  ", repr(USER_PROMPT))
    print()

    started = time.perf_counter()

    try:
        raw = generate_completion(SYSTEM_PROMPT, USER_PROMPT)
    except LLMParsingError as exc:
        elapsed = time.perf_counter() - started
        print(f"FAIL: LLM error after {elapsed:.2f}s")
        print(f"  {exc}")
        return 1
    except ParserError as exc:
        elapsed = time.perf_counter() - started
        print(f"FAIL: Parser error after {elapsed:.2f}s")
        print(f"  {exc}")
        return 1
    except Exception as exc:
        elapsed = time.perf_counter() - started
        print(f"FAIL: Unexpected error after {elapsed:.2f}s")
        print(f"  {type(exc).__name__}: {exc}")
        return 1

    elapsed = time.perf_counter() - started

    print("-" * 60)
    print("Raw response:")
    print("-" * 60)
    print(raw)
    print()

    try:
        parsed = safe_json_loads(raw)
    except LLMParsingError as exc:
        print(f"FAIL: Response is not valid JSON ({elapsed:.2f}s)")
        print(f"  {exc}")
        return 1

    if not isinstance(parsed, dict):
        print(f"FAIL: Expected JSON object, got {type(parsed).__name__} ({elapsed:.2f}s)")
        return 1

    missing = [key for key in ("hello", "status") if key not in parsed]
    if missing:
        print(f"FAIL: JSON object missing keys: {missing} ({elapsed:.2f}s)")
        print(f"  Parsed: {parsed}")
        return 1

    print("-" * 60)
    print(f"SUCCESS: Valid JSON received in {elapsed:.2f}s")
    print("-" * 60)
    print(json.dumps(parsed, indent=2))
    print()
    print(f"hello  = {parsed['hello']!r}")
    print(f"status = {parsed['status']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
