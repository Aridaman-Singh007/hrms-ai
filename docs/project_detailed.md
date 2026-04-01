# 📘 HRMS --- AI Resume Filtering & Scoring Engine (Elite Production README)

## 1. Overview

End-to-end AI hiring system that ingests resumes, parses them into
structured data, scores candidates against job descriptions, and ranks
them with explainable outputs.

------------------------------------------------------------------------

## 2. Architecture

### Flow

Input → Parsing (LLM) → Structured JSON → Scoring Engine → Storage →
Dashboard

### Components

-   FastAPI (API layer)
-   PostgreSQL (relational data)
-   Qdrant (vector DB)
-   S3 (file storage)
-   Celery + Redis (async jobs)

------------------------------------------------------------------------

## 3. Project Structure

backend/ ├── app/ │ ├── main.py │ ├── core/ │ ├── api/routes/ │ ├──
models/ │ ├── schemas/ │ ├── services/ │ ├── workers/ │ └── utils/ ├──
alembic/ ├── requirements.txt └── .env

------------------------------------------------------------------------

## 4. Environment Setup

Create `.env`:

POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=hrms
POSTGRES_USER=postgres POSTGRES_PASSWORD=password
REDIS_URL=redis://localhost:6379/0 OPENAI_API_KEY=your_key
QDRANT_HOST=localhost QDRANT_PORT=6333

------------------------------------------------------------------------

## 5. Local Setup

### Install

python -m venv venv venv`\Scripts`{=tex}`\activate`{=tex} pip install -r
requirements.txt

### Run

uvicorn app.main:app --reload redis-server celery -A app.workers worker
--loglevel=info

------------------------------------------------------------------------

## 6. Core Modules

### JD Parser

-   LLM-based structured extraction
-   JSON schema validation

### Resume Parser

-   pdfplumber + OCR
-   LLM extraction
-   Skill normalization

### Scoring Engine

Score = Σ(weight × dimension_score)

Dimensions: - Skills (35%) - Experience (25%) - Education (10%) -
Semantic similarity (10%) - Others (20%)

### Embeddings

-   Generate vectors
-   Store in Qdrant
-   Cosine similarity

------------------------------------------------------------------------

## 7. API Design

POST /api/jobs GET /api/jobs/:id POST /api/jobs/:id/resumes GET
/api/jobs/:id/resumes GET /api/resumes/:id POST
/api/scores/recalculate/:job_id POST /api/shortlists

------------------------------------------------------------------------

## 8. Database Schema

Tables: - jobs - candidates - resumes - scores - shortlists - feedback -
skill_taxonomy

------------------------------------------------------------------------

## 9. Async Workflow

Upload → Queue → Parse → Store → Score → Rank

Celery handles: - Resume parsing - JD parsing - Scoring jobs

------------------------------------------------------------------------

## 10. Deployment

### Docker

-   Containerize backend
-   Add Redis + Qdrant services

### Cloud

-   AWS ECS / Kubernetes
-   RDS (Postgres)
-   S3 (files)

------------------------------------------------------------------------

## 11. Security

-   JWT authentication
-   AES encryption for PII
-   Role-based access control

------------------------------------------------------------------------

## 12. Observability

-   Logging (structured logs)
-   Metrics (queue size, API latency)
-   Alerts (failure rates)

------------------------------------------------------------------------

## 13. Roadmap

Phase 1: Backend + DB Phase 2: Parsing Phase 3: Scoring Phase 4:
Dashboard Phase 5: Scaling

------------------------------------------------------------------------

## 14. Future Enhancements

-   Feedback loop learning
-   Bias detection
-   AI recruiter agent
-   Interview scheduling automation

------------------------------------------------------------------------

## 15. Final Note

This is a scalable AI system combining: - backend engineering - ML
pipelines - distributed systems

Build smart. Scale smarter.
