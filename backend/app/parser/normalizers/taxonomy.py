"""Software-engineering skill taxonomy with alias-based normalization.

The taxonomy maps canonical skill names to their aliases and categories.
A pre-built reverse index (alias → canonical name) is constructed at import
time so that ``normalize_skill`` runs in O(1).

To extend the taxonomy, add entries to ``SKILL_TAXONOMY`` below — every alias
is automatically picked up on the next process start.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical taxonomy
# ---------------------------------------------------------------------------

SKILL_TAXONOMY: dict[str, dict[str, object]] = {
    # ── Programming Languages ──────────────────────────────────────────
    "Python": {
        "aliases": ["python", "py"],
        "category": "programming_language",
    },
    "Java": {
        "aliases": ["java"],
        "category": "programming_language",
    },
    "JavaScript": {
        "aliases": ["javascript", "js"],
        "category": "programming_language",
    },
    "TypeScript": {
        "aliases": ["typescript", "ts"],
        "category": "programming_language",
    },
    "C": {
        "aliases": ["c"],
        "category": "programming_language",
    },
    "C++": {
        "aliases": ["c++", "cpp"],
        "category": "programming_language",
    },
    "C#": {
        "aliases": ["c#", "csharp", ".net"],
        "category": "programming_language",
    },
    "Go": {
        "aliases": ["go", "golang"],
        "category": "programming_language",
    },
    "Rust": {
        "aliases": ["rust"],
        "category": "programming_language",
    },
    "Ruby": {
        "aliases": ["ruby"],
        "category": "programming_language",
    },
    "PHP": {
        "aliases": ["php"],
        "category": "programming_language",
    },
    "Scala": {
        "aliases": ["scala"],
        "category": "programming_language",
    },
    "Kotlin": {
        "aliases": ["kotlin"],
        "category": "programming_language",
    },
    "Swift": {
        "aliases": ["swift"],
        "category": "programming_language",
    },
    "SQL": {
        "aliases": ["sql"],
        "category": "programming_language",
    },
    "R": {
        "aliases": ["r"],
        "category": "programming_language",
    },
    "Bash": {
        "aliases": ["bash", "shell scripting", "shell"],
        "category": "programming_language",
    },

    # ── Frontend ───────────────────────────────────────────────────────
    "React": {
        "aliases": ["react", "reactjs", "react.js", "react js"],
        "category": "frontend",
    },
    "Next.js": {
        "aliases": ["nextjs", "next.js", "next js"],
        "category": "frontend",
    },
    "Vue.js": {
        "aliases": ["vue", "vuejs", "vue.js"],
        "category": "frontend",
    },
    "Angular": {
        "aliases": ["angular", "angularjs"],
        "category": "frontend",
    },
    "Svelte": {
        "aliases": ["svelte"],
        "category": "frontend",
    },
    "Redux": {
        "aliases": ["redux"],
        "category": "frontend",
    },
    "Tailwind CSS": {
        "aliases": ["tailwind", "tailwindcss", "tailwind css"],
        "category": "frontend",
    },
    "HTML": {
        "aliases": ["html", "html5"],
        "category": "frontend",
    },
    "CSS": {
        "aliases": ["css", "css3"],
        "category": "frontend",
    },
    "SCSS": {
        "aliases": ["scss", "sass"],
        "category": "frontend",
    },
    "Bootstrap": {
        "aliases": ["bootstrap"],
        "category": "frontend",
    },
    "Material UI": {
        "aliases": ["material ui", "mui"],
        "category": "frontend",
    },
    "Webpack": {
        "aliases": ["webpack"],
        "category": "frontend",
    },
    "Vite": {
        "aliases": ["vite"],
        "category": "frontend",
    },

    # ── Backend ────────────────────────────────────────────────────────
    "Node.js": {
        "aliases": ["nodejs", "node.js", "node js"],
        "category": "backend",
    },
    "Express.js": {
        "aliases": ["express", "expressjs", "express.js"],
        "category": "backend",
    },
    "FastAPI": {
        "aliases": ["fastapi"],
        "category": "backend",
    },
    "Django": {
        "aliases": ["django"],
        "category": "backend",
    },
    "Flask": {
        "aliases": ["flask"],
        "category": "backend",
    },
    "Spring Boot": {
        "aliases": ["spring boot", "springboot"],
        "category": "backend",
    },
    "NestJS": {
        "aliases": ["nestjs", "nest.js"],
        "category": "backend",
    },
    "Laravel": {
        "aliases": ["laravel"],
        "category": "backend",
    },
    "Ruby on Rails": {
        "aliases": ["rails", "ruby on rails"],
        "category": "backend",
    },
    "GraphQL": {
        "aliases": ["graphql"],
        "category": "backend",
    },
    "REST API": {
        "aliases": ["rest api", "restful api", "apis"],
        "category": "backend",
    },
    "gRPC": {
        "aliases": ["grpc"],
        "category": "backend",
    },

    # ── Databases ──────────────────────────────────────────────────────
    "PostgreSQL": {
        "aliases": ["postgres", "postgresql"],
        "category": "database",
    },
    "MySQL": {
        "aliases": ["mysql"],
        "category": "database",
    },
    "MongoDB": {
        "aliases": ["mongodb", "mongo"],
        "category": "database",
    },
    "Redis": {
        "aliases": ["redis"],
        "category": "database",
    },
    "SQLite": {
        "aliases": ["sqlite"],
        "category": "database",
    },
    "Oracle": {
        "aliases": ["oracle", "oracle db"],
        "category": "database",
    },
    "Cassandra": {
        "aliases": ["cassandra"],
        "category": "database",
    },
    "DynamoDB": {
        "aliases": ["dynamodb"],
        "category": "database",
    },
    "Elasticsearch": {
        "aliases": ["elasticsearch", "elastic search", "elastic"],
        "category": "database",
    },
    "Neo4j": {
        "aliases": ["neo4j"],
        "category": "database",
    },
    "Firebase": {
        "aliases": ["firebase"],
        "category": "database",
    },
    "Supabase": {
        "aliases": ["supabase"],
        "category": "database",
    },

    # ── Cloud ──────────────────────────────────────────────────────────
    "AWS": {
        "aliases": ["aws", "amazon web services"],
        "category": "cloud",
    },
    "Azure": {
        "aliases": ["azure", "microsoft azure"],
        "category": "cloud",
    },
    "GCP": {
        "aliases": ["gcp", "google cloud", "google cloud platform"],
        "category": "cloud",
    },

    # ── DevOps ─────────────────────────────────────────────────────────
    "Docker": {
        "aliases": ["docker"],
        "category": "devops",
    },
    "Kubernetes": {
        "aliases": ["kubernetes", "k8s"],
        "category": "devops",
    },
    "Terraform": {
        "aliases": ["terraform"],
        "category": "devops",
    },
    "Ansible": {
        "aliases": ["ansible"],
        "category": "devops",
    },
    "Jenkins": {
        "aliases": ["jenkins"],
        "category": "devops",
    },
    "GitHub Actions": {
        "aliases": ["github actions", "github workflows"],
        "category": "devops",
    },
    "CI/CD": {
        "aliases": ["ci/cd", "continuous integration", "continuous deployment"],
        "category": "devops",
    },
    "Linux": {
        "aliases": ["linux", "unix"],
        "category": "devops",
    },
    "Nginx": {
        "aliases": ["nginx"],
        "category": "devops",
    },
    "Prometheus": {
        "aliases": ["prometheus"],
        "category": "devops",
    },
    "Grafana": {
        "aliases": ["grafana"],
        "category": "devops",
    },

    # ── AI / ML ────────────────────────────────────────────────────────
    "Machine Learning": {
        "aliases": ["machine learning", "ml"],
        "category": "ai_ml",
    },
    "Deep Learning": {
        "aliases": ["deep learning", "dl"],
        "category": "ai_ml",
    },
    "TensorFlow": {
        "aliases": ["tensorflow"],
        "category": "ai_ml",
    },
    "PyTorch": {
        "aliases": ["pytorch"],
        "category": "ai_ml",
    },
    "LangChain": {
        "aliases": ["langchain"],
        "category": "ai_ml",
    },
    "LlamaIndex": {
        "aliases": ["llamaindex"],
        "category": "ai_ml",
    },
    "RAG": {
        "aliases": ["rag", "retrieval augmented generation"],
        "category": "ai_ml",
    },
    "Vector Databases": {
        "aliases": ["vector db", "vector database", "vector databases"],
        "category": "ai_ml",
    },
    "OpenAI": {
        "aliases": ["openai", "gpt"],
        "category": "ai_ml",
    },
    "Hugging Face": {
        "aliases": ["huggingface", "hugging face"],
        "category": "ai_ml",
    },
    "Scikit-learn": {
        "aliases": ["scikit-learn", "sklearn"],
        "category": "ai_ml",
    },
    "Pandas": {
        "aliases": ["pandas"],
        "category": "ai_ml",
    },
    "NumPy": {
        "aliases": ["numpy"],
        "category": "ai_ml",
    },
    "Computer Vision": {
        "aliases": ["computer vision", "cv"],
        "category": "ai_ml",
    },
    "NLP": {
        "aliases": ["nlp", "natural language processing"],
        "category": "ai_ml",
    },
    "LLMs": {
        "aliases": ["llm", "llms", "large language models"],
        "category": "ai_ml",
    },
    "AI Agents": {
        "aliases": ["ai agents", "agentic ai"],
        "category": "ai_ml",
    },

    # ── Data Engineering ───────────────────────────────────────────────
    "Apache Spark": {
        "aliases": ["spark", "apache spark"],
        "category": "data_engineering",
    },
    "Kafka": {
        "aliases": ["kafka", "apache kafka"],
        "category": "data_engineering",
    },
    "Airflow": {
        "aliases": ["airflow", "apache airflow"],
        "category": "data_engineering",
    },
    "Snowflake": {
        "aliases": ["snowflake"],
        "category": "data_engineering",
    },
    "Databricks": {
        "aliases": ["databricks"],
        "category": "data_engineering",
    },
    "ETL": {
        "aliases": ["etl"],
        "category": "data_engineering",
    },
    "Data Warehousing": {
        "aliases": ["data warehouse", "data warehousing"],
        "category": "data_engineering",
    },
    "Hadoop": {
        "aliases": ["hadoop"],
        "category": "data_engineering",
    },
    "dbt": {
        "aliases": ["dbt"],
        "category": "data_engineering",
    },

    # ── Testing ────────────────────────────────────────────────────────
    "Pytest": {
        "aliases": ["pytest"],
        "category": "testing",
    },
    "Jest": {
        "aliases": ["jest"],
        "category": "testing",
    },
    "Cypress": {
        "aliases": ["cypress"],
        "category": "testing",
    },
    "Selenium": {
        "aliases": ["selenium"],
        "category": "testing",
    },
    "JUnit": {
        "aliases": ["junit"],
        "category": "testing",
    },
    "Playwright": {
        "aliases": ["playwright"],
        "category": "testing",
    },
    "Unit Testing": {
        "aliases": ["unit testing"],
        "category": "testing",
    },
    "Integration Testing": {
        "aliases": ["integration testing"],
        "category": "testing",
    },
    "TDD": {
        "aliases": ["tdd", "test driven development"],
        "category": "testing",
    },

    # ── Mobile ─────────────────────────────────────────────────────────
    "React Native": {
        "aliases": ["react native"],
        "category": "mobile",
    },
    "Flutter": {
        "aliases": ["flutter"],
        "category": "mobile",
    },
    "Android": {
        "aliases": ["android"],
        "category": "mobile",
    },
    "iOS": {
        "aliases": ["ios"],
        "category": "mobile",
    },

    # ── Security ───────────────────────────────────────────────────────
    "OAuth": {
        "aliases": ["oauth"],
        "category": "security",
    },
    "JWT": {
        "aliases": ["jwt", "json web token"],
        "category": "security",
    },
    "OWASP": {
        "aliases": ["owasp"],
        "category": "security",
    },
    "Cybersecurity": {
        "aliases": ["cybersecurity", "cyber security"],
        "category": "security",
    },
    "IAM": {
        "aliases": ["iam", "identity access management"],
        "category": "security",
    },

    # ── Architecture / Concepts ────────────────────────────────────────
    "Microservices": {
        "aliases": ["microservices", "microservice architecture"],
        "category": "architecture",
    },
    "Distributed Systems": {
        "aliases": ["distributed systems"],
        "category": "architecture",
    },
    "System Design": {
        "aliases": ["system design"],
        "category": "architecture",
    },
    "Event-Driven Architecture": {
        "aliases": ["event driven architecture", "eda"],
        "category": "architecture",
    },
    "Design Patterns": {
        "aliases": ["design patterns"],
        "category": "architecture",
    },
    "Scalability": {
        "aliases": ["scalability", "high scalability"],
        "category": "architecture",
    },
    "Caching": {
        "aliases": ["caching", "cache systems"],
        "category": "architecture",
    },
    "Message Queues": {
        "aliases": ["message queues", "rabbitmq", "sqs"],
        "category": "architecture",
    },
}

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_skill_category(skill: str) -> str | None:
    """Return the category for *skill*, or ``None`` if not in the taxonomy."""
    from app.parser.normalizers.skills import normalize_skill

    canonical = normalize_skill(skill)
    if canonical is None:
        return None
    return str(SKILL_TAXONOMY[canonical]["category"])


def get_skills_by_category(category: str) -> list[str]:
    """Return all canonical skill names that belong to *category*."""
    lowered = category.strip().lower()
    return [
        name
        for name, meta in SKILL_TAXONOMY.items()
        if str(meta["category"]).lower() == lowered
    ]
