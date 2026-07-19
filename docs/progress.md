# HRMS AI — Development Progress

## Phase 1: Backend Foundation

**Status:** Complete

---

### 1.1 Project Structure

Created the modular FastAPI backend scaffold under `backend/app/`:

```
backend/
├── .env.example
├── requirements.txt
└── app/
    ├── __init__.py
    ├── main.py
    ├── api/
    │   ├── __init__.py
    │   ├── router.py
    │   └── v1/
    │       ├── __init__.py
    │       ├── router.py
    │       └── endpoints/
    │           ├── __init__.py
    │           └── health.py
    ├── core/
    │   ├── __init__.py
    │   ├── config.py
    │   └── logging.py
    ├── db/
    │   ├── __init__.py
    │   ├── base.py
    │   └── session.py
    ├── models/
    │   └── __init__.py
    ├── schemas/
    │   ├── __init__.py
    │   └── health.py
    ├── services/
    │   ├── __init__.py
    │   └── health_service.py
    └── utils/
        └── __init__.py
```

---

### 1.2 Configuration (`core/config.py`)

- Centralized settings using `pydantic-settings` (`BaseSettings`).
- Reads from `.env` file with fallback defaults.
- Exposes:
  - `app_name`, `environment`, `debug`, `log_level`
  - `api_v1_prefix` (default `/api/v1`)
  - PostgreSQL credentials (`postgres_user`, `postgres_password`, `postgres_host`, `postgres_port`, `postgres_db`)
  - Computed `database_url` property for SQLAlchemy.
- Cached via `@lru_cache` (`get_settings()`) to avoid re-reading env on every call.

---

### 1.3 Logging (`core/logging.py`)

- Application-wide logging configured at startup.
- Format: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`
- Log level driven by `LOG_LEVEL` env var (default `INFO`).
- Outputs to `stdout` for container-friendly log collection.

---

### 1.4 Database Layer (`db/`)

**`db/base.py`**
- Declares `Base` using SQLAlchemy 2.0 `DeclarativeBase`.
- All future ORM models will inherit from this class.

**`db/session.py`**
- Creates the SQLAlchemy `engine` with `pool_pre_ping=True` for connection resilience.
- `SessionLocal` factory for request-scoped sessions.
- `get_db()` generator dependency for FastAPI's `Depends()`.

---

### 1.5 API Routing

Versioned, modular router wiring:

| Layer | File | Purpose |
|---|---|---|
| Root | `api/router.py` | Mounts all version routers under their prefix |
| V1 | `api/v1/router.py` | Aggregates all v1 endpoint routers |
| Endpoints | `api/v1/endpoints/` | Individual endpoint modules |

All v1 endpoints are served under `/api/v1/`.

---

### 1.6 Health Check Endpoint

**Endpoint:** `GET /api/v1/health`

**Response schema (`schemas/health.py`):**

```json
{
  "status": "ok",
  "service": "HRMS AI Backend",
  "environment": "development",
  "db_status": "connected"
}
```

**Implementation details:**

- **`api/v1/endpoints/health.py`** — Injects DB session via `Depends(get_db)`, executes `SELECT 1` to verify connectivity.
- **`services/health_service.py`** — Builds the response dict from settings + db status.
- **`schemas/health.py`** — Pydantic response model with `status`, `service`, `environment`, `db_status`.
- `db_status` returns `"connected"` on success, `"failed"` on any `SQLAlchemyError` or unexpected exception.
- Exceptions are logged with full stack trace via `logger.exception(...)`.
- The endpoint never crashes — it degrades gracefully when the database is unreachable.

---

### 1.7 Application Entrypoint (`main.py`)

- Creates the `FastAPI` app instance with title and debug flag from settings.
- Includes the top-level API router.
- Configures logging at import time.
- `startup` event logs app name and environment.
- `shutdown` event logs graceful shutdown.

**Run command:**

```bash
uvicorn app.main:app --reload
```

---

### 1.8 Dependencies (`requirements.txt`)

Key packages pinned:

| Package | Version | Purpose |
|---|---|---|
| fastapi | 0.135.2 | Web framework |
| uvicorn | 0.42.0 | ASGI server |
| SQLAlchemy | 2.0.48 | ORM / DB toolkit |
| psycopg2-binary | 2.9.11 | PostgreSQL driver |
| pydantic | 2.12.5 | Data validation |
| pydantic-settings | 2.11.0 | Environment config |
| python-dotenv | 1.2.2 | `.env` file loading |

---

### 1.9 Environment Template (`.env.example`)

Provided `.env.example` with all required variables:

```
POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB
APP_NAME, ENVIRONMENT, DEBUG, API_V1_PREFIX, LOG_LEVEL
```

---

## Phase 2: Resume Parser

**Status:** In Progress

---

### 2.1 Parser Module Architecture

Created the initial clean-architecture parser scaffold under `backend/app/parser/`:

```
parser/
├── __init__.py
├── exceptions.py
├── pipeline.py
├── extractors/
│   ├── __init__.py
│   ├── base.py
│   ├── docx.py
│   └── pdf.py
├── llm/
│   ├── __init__.py
│   └── parser.py
├── normalizers/
│   ├── __init__.py
│   └── resume.py
└── validators/
    ├── __init__.py
    └── resume.py
```

Implementation notes:

- Parsing is isolated from FastAPI routes.
- `pipeline.py` defines the orchestration boundary for future parser workflows.
- `extractors/` contains placeholder support for PDF and DOCX extraction.
- `llm/` contains a placeholder LLM resume parser.
- `validators/` and `normalizers/` contain placeholder classes for parser output quality control.
- `exceptions.py` defines parser-specific exception types.
- No business logic has been implemented yet.

Verification:

- `python -m compileall -q backend/app/parser`
- Cursor linter check returned no errors for `backend/app/parser`.

### 2.2 PDF Text Extraction (`extractors/pdf.py`)

Implemented production-grade PDF text extraction with dual-engine strategy:

- **Primary engine:** `pdfplumber` — used first for every extraction.
- **Fallback engine:** `PyMuPDF` (`fitz`) — used when pdfplumber yields no text or raises an error.
- Text cleaning via `_clean_text()`: collapses redundant whitespace, normalizes line endings, preserves paragraph breaks.
- Raises `ExtractionError` (from `parser.exceptions`) when both engines fail or the payload is empty.
- Structured logging at every decision point (`info` on success, `warning` on engine failure).
- Exposes a standalone function `extract_text_from_pdf(file_content: bytes) -> str` and a `PdfExtractor` class that satisfies the `DocumentExtractor` protocol.

New dependencies added to `requirements.txt`:

| Package | Version | Purpose |
|---|---|---|
| pdfplumber | 0.11.6 | Primary PDF text extraction |
| PyMuPDF | 1.25.5 | Fallback PDF text extraction |

### 2.3 DOCX Text Extraction (`extractors/docx.py`)

Implemented DOCX text extraction using `python-docx`:

- Iterates all paragraphs via `docx.Document`.
- Preserves section separation by inserting blank lines before heading-style paragraphs.
- Text cleaning via shared `_clean_text()` pattern (collapse whitespace, normalize line endings, cap blank lines).
- Handles malformed files gracefully: catches `PackageNotFoundError` for invalid DOCX archives and wraps unexpected errors in `ExtractionError`.
- Structured logging: `info` on success with character count, `warning` on failure.
- Exposes `extract_text_from_docx(file_content: bytes) -> str` and a `DocxExtractor` class satisfying the `DocumentExtractor` protocol.

New dependency added to `requirements.txt`:

| Package | Version | Purpose |
|---|---|---|
| python-docx | 1.1.2 | DOCX text extraction |

### 2.4 Unified Extraction Pipeline (`pipeline.py`)

Implemented a unified extraction entry-point that detects file type and routes to the correct extractor:

- `extract_resume_text(file_content: bytes, filename: str) -> str` — single public function for all callers.
- File-type detection via extension with `mimetypes.guess_type` fallback.
- Routing map dispatches to `extract_text_from_pdf` or `extract_text_from_docx`.
- Raises `UnsupportedFileTypeError` (new exception added to `exceptions.py`) for unsupported extensions, with a message listing supported types.
- `ResumeParserPipeline.parse()` now delegates to `extract_resume_text` and returns `{"raw_text": ...}`.
- Structured logging at `info` (start/complete with byte and char counts) and `debug` (MIME resolution).
- Both `extract_resume_text` and `ResumeParserPipeline` are re-exported from the top-level `parser` package.

### 2.5 Resume Pydantic Schemas (`schemas/resume.py`)

Created Pydantic v2 schemas for structured resume data, optimized for software-engineering hiring:

| Model | Purpose |
|---|---|
| `Skill` | Technical/soft skill with optional category and years of experience |
| `Experience` | Work history entry with dates, technologies, domain, employment type |
| `Education` | Degree, institution, specialization, CGPA |
| `Project` | Personal/open-source project with GitHub / live URLs |
| `Certification` | Professional credential with issuer and date |
| `CandidateProfile` | Top-level model aggregating all sections above plus contact info, summary, achievements, and languages |

- All fields use `str | None` / `list[...]` with sensible defaults — the LLM parser can populate as much or as little as it extracts.
- `EmailStr` validates email format (requires `email-validator`).
- Python 3.10+ union syntax (`X | None`) used throughout for consistency.

New dependency added to `requirements.txt`:

| Package | Version | Purpose |
|---|---|---|
| email-validator | 2.3.0 | Email format validation for `EmailStr` |

### 2.6 Skill Taxonomy & Normalization (`normalizers/taxonomy.py`)

Created a production-grade skill taxonomy module sourced from the project's `assets/taxonomy` reference data:

- **121 canonical skills** across 12 categories: programming languages, frontend, backend, databases, cloud, devops, AI/ML, data engineering, testing, mobile, security, architecture.
- **195 alias index entries** — a pre-built reverse map (lowered alias → canonical name) constructed at import time for O(1) lookups.
- Case-insensitive normalization: `"reactjs"` → `"React"`, `"k8s"` → `"Kubernetes"`, `"PYTHON"` → `"Python"`.
- Unknown skills return `None` (no exception), so callers can decide whether to keep or drop them.

Public API:

| Function | Signature | Purpose |
|---|---|---|
| `normalize_skill` | `(skill: str) -> str \| None` | Resolve any alias to the canonical name |
| `get_skill_category` | `(skill: str) -> str \| None` | Return the category of a skill |
| `get_skills_by_category` | `(category: str) -> list[str]` | List all canonical skills in a category |

All three functions plus `ResumeNormalizer` are re-exported from `normalizers/__init__.py`.

### 2.7 Gemini LLM Client & Provider Abstraction

Added `gemini_api_key` and `gemini_model` (default `gemini-2.5-flash`) to `core/config.py`.

Created a provider-abstracted LLM layer under `parser/llm/`:

```
llm/
├── __init__.py
├── client.py
├── parser.py
├── prompts.py
└── providers/
    ├── __init__.py
    ├── base.py
    └── gemini.py
```

| Module | Purpose |
|---|---|
| `providers/base.py` | Abstract `LLMProvider` contract (`generate(system, user) -> str`) |
| `providers/gemini.py` | Concrete Gemini implementation using `google-genai` SDK |
| `client.py` | Facade: `generate_completion(system_prompt, user_prompt) -> str` |
| `prompts.py` | Placeholder for prompt templates (populated in next step) |

Production hardening in `GeminiProvider`:

- **Retry logic** via `tenacity`: retries on `ResourceExhausted` and `ServiceUnavailable` with exponential back-off (max 3 attempts, 2–30 s wait).
- **Timeout**: 120 s per request via `request_options`.
- **Error handling**: empty/blank responses, rate limits, service unavailability, generic API errors — all wrapped in `LLMParsingError`.
- **Singleton client**: SDK configured once via `@lru_cache`, reused across calls.
- **Structured logging**: SDK init, retry sleeps, completion receipt, and all error paths.

New dependencies added to `requirements.txt`:

| Package | Version | Purpose |
|---|---|---|
| google-genai | 2.6.0 | Google Gemini SDK (new, replaces deprecated `google-generativeai`) |
| tenacity | 9.1.4 | Retry/back-off library |

### 2.8 LLM Integration Test Script (`scripts/test_llm.py`)

Created a manual integration test for the Gemini client:

- Calls `generate_completion()` with a simple JSON API prompt.
- Prints raw model output, elapsed time, and parsed JSON on success.
- Strips optional markdown code fences before `json.loads`.
- Validates expected keys (`hello`, `status`).
- Exit code `0` on success, `1` on failure (missing API key, LLM errors, invalid JSON).

Run from `backend/`:

```bash
python scripts/test_llm.py
```

Requires `GEMINI_API_KEY` in `backend/.env`.

### 2.9 Resume Parser Prompt Builder (`llm/prompts.py`)

Created a production-grade, modular prompt builder for structured ATS extraction:

- **`RESUME_PARSER_SYSTEM_PROMPT`** — system instructions (JSON-only output, anti-hallucination, section rules).
- **`build_resume_parser_prompt(resume_text)`** — user prompt with embedded schema reference and delimited resume text.

Prompt sections (maintainable string constants):

| Section | Covers |
|---|---|
| JSON output rules | Strict JSON only, no markdown, null/[] conventions |
| Anti-hallucination | No inferred data; exact company/role names |
| General rules | Chronology, human-readable dates, precision over completeness |
| Skills | Canonical names, categories, no inferred years |
| Experience | Exact titles, technologies per role, ordering |
| Education / Projects / Certifications | Section-specific extraction rules |

Schema embedded from `CandidateProfile` structure. Usage with the LLM client:

```python
from app.parser.llm import RESUME_PARSER_SYSTEM_PROMPT, build_resume_parser_prompt, generate_completion

raw = generate_completion(
    RESUME_PARSER_SYSTEM_PROMPT,
    build_resume_parser_prompt(resume_text),
)
```

### 2.10 LLM JSON Response Utilities (`llm/utils.py`)

Created utilities for sanitizing and parsing LLM JSON responses:

| Function | Purpose |
|---|---|
| `clean_llm_response(raw)` | Strip whitespace/BOM, remove markdown fences, extract outermost `{...}` object |
| `safe_json_loads(raw)` | Clean + parse JSON; retry with object extraction; raise `LLMParsingError` on failure |

Features:

- Handles full-string and inline ` ```json ` code fences.
- Brace-aware JSON object extraction (respects quoted strings).
- Structured logging at `debug` / `warning` / `error` levels.
- Re-exported from `app.parser.llm`; `scripts/test_llm.py` updated to use `safe_json_loads`.

### 2.11 LLM Structured Resume Parser (`llm/resume_parser.py`)

Implemented production-grade LLM resume parsing:

- **`parse_resume_with_llm(resume_text) -> CandidateProfile`** — main entry-point.
- Pipeline: prompt build → `generate_completion()` → `safe_json_loads()` → sanitize → skill normalization → Pydantic validation.

Helper stages:

| Stage | Purpose |
|---|---|
| `_parse_llm_json` | Ensure root JSON object via `safe_json_loads` |
| `_sanitize_payload` | Whitelist fields, coerce lists, drop unknown/hallucinated keys |
| `_normalize_skills_in_payload` | Canonicalize skills/technologies via taxonomy |
| `_validate_candidate_profile` | `CandidateProfile.model_validate`; raises `ValidationError` |

Handles: markdown-wrapped JSON, invalid emails (→ null), malformed arrays, missing required nested fields (skipped with warnings), duplicate skills, chronological order preserved from LLM output.

`LLMResumeParser` in `llm/parser.py` now delegates to `parse_resume_with_llm` (`parse()` returns dict, `parse_profile()` returns model).

### 2.12 Temporary Upload File Utilities (`utils/file_handler.py`)

Created async utilities for FastAPI resume uploads:

| Function | Purpose |
|---|---|
| `save_temp_file(upload)` | Stream `UploadFile` to disk in 1 MiB chunks with UUID filename |
| `cleanup_temp_file(path)` | Delete temp file safely via `asyncio.to_thread` |

Features:

- Unique filenames via `uuid4().hex` with preserved extension from original filename.
- Default temp directory: `{system_temp}/hrms-ai/uploads/`.
- Memory-efficient chunked `await upload.read()` — no full-file buffering.
- Auto-cleanup on failed/empty writes; structured logging throughout.
- Re-exported from `app.utils`.

Example usage in an endpoint:

```python
path = await save_temp_file(upload)
try:
    ...
finally:
    await cleanup_temp_file(path)
```

### 2.13 Skill Normalization (`normalizers/skills.py`)

Implemented deterministic skill normalization using `SKILL_TAXONOMY`:

| Function | Purpose |
|---|---|
| `normalize_skill(skill)` | Map one skill to canonical name, or `None` if unknown |
| `normalize_skills(skills)` | Batch normalize with dedupe; unknown skills preserved as cleaned originals |
| `normalize_skill_objects(skills)` | Returns `NormalizedSkill` structs (`name`, `in_taxonomy`, `category`) |

Features:

- Case-insensitive lookup with whitespace/punctuation normalization and compact keys (e.g. `react.js` → `React`).
- No embeddings or fuzzy matching — taxonomy index only.
- Unknown skills kept separately (not dropped); known skills mapped to canonical names.
- `get_skill_category` in `taxonomy.py` now delegates to `skills.normalize_skill` (lazy import).
- Re-exported from `app.parser.normalizers`.

### 2.14 Resume Parser Evaluation Script (`scripts/evaluate_resume_parser.py`)

Created a local batch evaluation script for the full parser pipeline:

- Reads all `.pdf` / `.docx` files from `sample_resumes/` (repo root).
- Per resume: extract text → LLM parse → schema validate → skill normalize.
- Prints: name, normalized skills, experience/education counts, success/failure, elapsed time.
- Writes outputs under `outputs/`:
  - `raw/` — raw LLM responses (`.txt`)
  - `parsed/` — validated JSON (`.json`)
  - `failed/` — error details by stage (`.json`)
- Ends with aggregate metrics (totals, success rate, timing).

Run from repo root or `backend/`:

```bash
python scripts/evaluate_resume_parser.py
```

Requires `GEMINI_API_KEY` in `backend/.env` and resumes in `sample_resumes/`.

### 2.15 Parser Quality Improvements (from evaluation feedback)

Acted on findings from the first real-resume evaluation run:

**Taxonomy (`normalizers/taxonomy.py`)**
- Added new `devtools` category with: VS Code, Jupyter Notebook, PyCharm, IntelliJ IDEA, Visual Studio, Git, GitHub, GitLab, Bitbucket, Postman, Jira, Figma.
- Fixes previously uncategorized skills like `Jupyter Notebook` and `VsCode`.

**Education schema (`schemas/resume.py`)**
- Added `percentage: float | None` and `grade: str | None` so percentage-based results are preserved instead of dropped into a null `cgpa`.
- Prompt updated: `cgpa` only for point-scale GPA, `percentage` for percent grades (no lossy conversion), plus `devtools` in the allowed skill categories.

**Deterministic normalizer (`normalizers/resume.py`)**
- `ResumeNormalizer.normalize(profile)` now runs after schema validation.
- Computes `duration_months` (inclusive) from `start_date`/`end_date`, using today's date for `Present`/current roles.
- Normalizes present-tense end dates to `"Present"` and sets `currently_working`.
- Computes `total_experience_years` from summed durations when the LLM left it null.
- Fills known certification issuers via a deterministic map (e.g. AWS Developer Associate → Amazon Web Services) — no LLM inference.

**PDF extraction (`extractors/pdf.py`)**
- Tuned pdfplumber with `x_tolerance`/`y_tolerance` to reduce merged words.
- Added `_merged_word_ratio()` quality heuristic; when pdfplumber output looks glued, PyMuPDF is run and the cleaner result is chosen (fixes Shipsy "mergedwords" description issue).

Wired `ResumeNormalizer` into `parse_resume_with_llm` after validation. All changes verified with unit checks; no lint errors.

### 2.19 OCR for Scanned / Image-Only PDFs

Added OCR fallback for resumes like `Snesh's_Resume.pdf` (1 page, 1 image, 0 text chars):

- New `extractors/ocr.py` with provider chain controlled by `OCR_PROVIDER`:
  - `auto` (default): **PaddleOCR → Tesseract → Bedrock vision → Textract**
  - `paddleocr`: local PaddleOCR (preferred cheap path)
  - `tesseract`: optional local `pytesseract`
  - `bedrock`: multimodal Converse OCR (expensive fallback only)
  - `textract`: kept last for optional future use
- PDF pages rendered to PNG via PyMuPDF (`2x` scale) before OCR.
- `extract_text_from_pdf()` calls OCR when native text is missing/sparse.
- Settings: `OCR_ENABLED`, `OCR_PROVIDER` (defaults `true` / `auto`).
- Dependencies: `paddlepaddle`, `paddleocr`, `numpy`, `Pillow` (installed; models auto-download on first run).
- Verified on `Snesh's_Resume.pdf`: PaddleOCR extracted ~3800 chars; full parse eval **SUCCESS** (Snesh Subbiah Raj).

### 2.18 Education Field Sanitization

Hardened LLM output sanitization after batch eval failures (4/5 failed on education field types):

- `_coerce_year()`: `"Nov 2022"`, `"11/2021"`, `"May 2026 (Expected)"` → year ints; `"Present"` / `"Expected"` → `null`.
- `_coerce_optional_string()`: numeric `grade` values like `10` → `"10"`.
- Also coerce `cgpa` / `percentage` / `years_experience` / `duration_months` to proper numeric types.
- Prompt updated to require YYYY integers for education years.

### 2.17 AWS Bedrock LLM Provider

Added Bedrock as a swappable LLM backend so Gemini quota exhaustion does not block parsing:

- New `providers/bedrock.py` using boto3 **Converse API** with throttling retries.
- `LLM_PROVIDER` setting selects `gemini` or `bedrock` in `client.py`.
- Config: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `BEDROCK_MODEL_ID`.
- Default Bedrock model: `amazon.nova-lite-v1:0` (region default `ap-south-1`).
- Dependency: `boto3==1.38.36`.
- `.env.example` updated with Bedrock placeholders.

Switch with `LLM_PROVIDER=bedrock` in `backend/.env`, then run `python scripts/test_llm.py`.

### 2.16 Evaluation Fixes: durations, totals, embedded links

Follow-up fixes after batch-evaluating ~19 real resumes:

- **Bug: normalizer bypassed in eval** — `scripts/evaluate_resume_parser.py` called the internal parse helpers directly and skipped `ResumeNormalizer`, so `duration_months` and `total_experience_years` stayed null in batch outputs (they worked via `parse_resume_with_llm`). Eval now runs `ResumeNormalizer.normalize()` after validation.
- **Date parsing** confirmed for day-first formats like `"16 Feb 2026"` (durations computed inclusively; e.g. 5 and 4 months → 0.8 total years).
- **Embedded PDF hyperlinks** — LinkedIn/GitHub/portfolio links are stored as PDF link annotations, not in the text stream, so they were never extracted. `extractors/pdf.py` now reads link annotations via PyMuPDF (`page.get_links()`) and appends an `EMBEDDED LINKS:` section to the extracted text. Prompt updated to route those URLs into `linkedin_url` / `github_url` / `portfolio_url`.

---

## What's Next

Planned work for upcoming phases:

- [ ] Alembic migration scaffold
- [ ] ORM models (`jobs`, `candidates`, `resumes`, `scores`)
- [ ] CRUD service layer
- [ ] JD and Resume API endpoints
- [ ] Celery + Redis async worker setup
- [ ] Middleware (request ID, CORS, error handling)
- [ ] Authentication (JWT)
- [ ] Qdrant vector DB integration
- [ ] Resume validator module (`validators/resume.py`)
- [ ] Resume normalizer module (`normalizers/resume.py`)
- [ ] Wire full parser pipeline in `pipeline.py`
