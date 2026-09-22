from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
_ENV = dotenv_values(ENV_FILE)


def _env(name: str, default: str) -> str:
    value = _ENV.get(name)
    if value is None:
        return default
    return str(value).strip()


def _float_env(name: str, default: float) -> float:
    raw = _env(name, str(default))
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是数字，当前值为 {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    database_path: Path
    embedding_provider: str
    match_threshold: float
    request_timeout: float
    qwen_api_key: str
    qwen_model: str
    qwen_base_url: str
    zhipu_api_key: str
    zhipu_model: str
    zhipu_base_url: str
    local_model: str


def load_settings() -> Settings:
    database_raw = _env("DATABASE_PATH", "data/lost_found.db")
    database_path = Path(database_raw)
    if not database_path.is_absolute():
        database_path = BASE_DIR / database_path

    threshold = _float_env("MATCH_THRESHOLD", 0.7)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("MATCH_THRESHOLD 必须在 0 到 1 之间")

    return Settings(
        database_path=database_path,
        embedding_provider=_env("EMBEDDING_PROVIDER", "qwen").lower(),
        match_threshold=threshold,
        request_timeout=_float_env("REQUEST_TIMEOUT", 30.0),
        qwen_api_key=_env("DASHSCOPE_API_KEY", ""),
        qwen_model=_env("QWEN_EMBEDDING_MODEL", "text-embedding-v3"),
        qwen_base_url=_env(
            "QWEN_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
        ),
        zhipu_api_key=_env("ZHIPU_API_KEY", ""),
        zhipu_model=_env("ZHIPU_EMBEDDING_MODEL", "embedding-3"),
        zhipu_base_url=_env(
            "ZHIPU_BASE_URL",
            "https://open.bigmodel.cn/api/paas/v4/embeddings",
        ),
        local_model=_env("LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"),
    )


settings = load_settings()
