"""Central runtime limits and storage configuration."""

import os
from dataclasses import dataclass
from pathlib import Path


def _load_backend_env_file() -> None:
    """Read backend/.env without overriding environment variables or logging values."""
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if name and name not in os.environ:
            os.environ[name] = value.strip("\"'")


_load_backend_env_file()


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    return tuple(x.strip().rstrip("/") for x in raw.split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    storage_dir: Path = Path(os.getenv("DATAFIX_STORAGE_DIR", "./datafix_storage"))
    max_upload_bytes: int = int(os.getenv("DATAFIX_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
    max_rows: int = int(os.getenv("DATAFIX_MAX_ROWS", "50000"))
    max_columns: int = int(os.getenv("DATAFIX_MAX_COLUMNS", "60"))
    max_cell_chars: int = int(os.getenv("DATAFIX_MAX_CELL_CHARS", "100000"))
    max_evidence_examples: int = int(os.getenv("DATAFIX_MAX_EVIDENCE_EXAMPLES", "8"))
    sample_diff_limit: int = int(os.getenv("DATAFIX_SAMPLE_DIFF_LIMIT", "20"))
    delimiter: str = ","
    engine_version: str = "0.1.0"
    cors_origins: tuple[str, ...] = _csv(
        "DATAFIX_CORS_ORIGINS", ("http://localhost:5173", "http://127.0.0.1:5173")
    )
    storage_backend: str = os.getenv("DATAFIX_STORAGE_BACKEND", "local").strip().lower()
    database_url: str = os.getenv("DATAFIX_DATABASE_URL", "")
    supabase_url: str = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_secret_key: str = os.getenv("SUPABASE_SECRET_KEY", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_storage_bucket: str = os.getenv("SUPABASE_STORAGE_BUCKET", "datafix")
    llm_enabled: bool = _bool("LLM_ENABLED", False)
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "8"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "1"))
    llm_requests_per_run: int = int(os.getenv("LLM_REQUESTS_PER_RUN", "20"))
    minimum_backtest_samples: int = int(os.getenv("MINIMUM_BACKTEST_SAMPLES", "20"))
    aggregate_drift_format_max_pct: float = float(
        os.getenv("DATAFIX_AGGREGATE_DRIFT_FORMAT_MAX_PCT", "5.0")
    )
    aggregate_drift_substitution_max_pct: float = float(
        os.getenv("DATAFIX_AGGREGATE_DRIFT_SUBSTITUTION_MAX_PCT", "5.0")
    )
    aggregate_drift_imputation_max_pct: float = float(
        os.getenv("DATAFIX_AGGREGATE_DRIFT_IMPUTATION_MAX_PCT", "1.0")
    )
    aggregate_drift_destructive_max_pct: float = float(
        os.getenv("DATAFIX_AGGREGATE_DRIFT_DESTRUCTIVE_MAX_PCT", "10.0")
    )

    @property
    def llm_available(self) -> bool:
        return bool(self.llm_enabled and self.groq_api_key and self.llm_model)

    @property
    def supabase_configured(self) -> bool:
        return bool(
            self.supabase_url and (self.supabase_secret_key or self.supabase_service_role_key)
        )

    @property
    def supabase_backend_key(self) -> str:
        return self.supabase_secret_key or self.supabase_service_role_key


settings = Settings()
