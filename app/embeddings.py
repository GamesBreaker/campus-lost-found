from __future__ import annotations

import threading
from typing import Any

import httpx
import numpy as np

from .config import settings
from .errors import EmbeddingError

_local_model: Any | None = None
_local_lock = threading.Lock()


def normalize_rows(vectors: np.ndarray) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise EmbeddingError("Embedding 服务返回了零向量，无法计算相似度。")
    return (matrix / norms).astype(np.float32, copy=False)


def embed_one(text: str) -> np.ndarray:
    return embed_texts([text])[0]


def embed_texts(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.empty((0, 0), dtype=np.float32)

    provider = settings.embedding_provider
    if provider == "qwen":
        vectors = _embed_remote_batches(texts, batch_size=10, provider=provider)
    elif provider == "zhipu":
        vectors = _embed_remote_batches(texts, batch_size=16, provider=provider)
    elif provider == "local":
        vectors = _embed_local(texts)
    else:
        raise EmbeddingError(
            "EMBEDDING_PROVIDER 配置无效，只能是 qwen、zhipu 或 local。"
        )

    return normalize_rows(vectors)


def _embed_remote_batches(texts: list[str], batch_size: int, provider: str) -> np.ndarray:
    chunks: list[np.ndarray] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        if provider == "qwen":
            chunks.append(_embed_qwen(batch))
        else:
            chunks.append(_embed_zhipu(batch))
    return np.vstack(chunks).astype(np.float32, copy=False)


def _embed_qwen(texts: list[str]) -> np.ndarray:
    if not settings.qwen_api_key:
        raise EmbeddingError(
            "未配置 DASHSCOPE_API_KEY，请在项目根目录的 .env 中填写通义 API key。",
            status_code=400,
        )
    payload = {"model": settings.qwen_model, "input": texts}
    return _post_embeddings(
        url=settings.qwen_base_url,
        headers={"Authorization": f"Bearer {settings.qwen_api_key}"},
        payload=payload,
        expected_count=len(texts),
        provider_label="通义",
        key_name="DASHSCOPE_API_KEY",
    )


def _embed_zhipu(texts: list[str]) -> np.ndarray:
    if not settings.zhipu_api_key:
        raise EmbeddingError(
            "未配置 ZHIPU_API_KEY，请在项目根目录的 .env 中填写智谱 API key。",
            status_code=400,
        )
    payload = {"model": settings.zhipu_model, "input": texts}
    return _post_embeddings(
        url=settings.zhipu_base_url,
        headers={"Authorization": f"Bearer {settings.zhipu_api_key}"},
        payload=payload,
        expected_count=len(texts),
        provider_label="智谱",
        key_name="ZHIPU_API_KEY",
    )


def _post_embeddings(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    expected_count: int,
    provider_label: str,
    key_name: str,
) -> np.ndarray:
    try:
        response = httpx.post(
            url,
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=settings.request_timeout,
        )
    except httpx.TimeoutException as exc:
        raise EmbeddingError(f"{provider_label} Embedding 调用超时，请稍后重试。") from exc
    except httpx.HTTPError as exc:
        raise EmbeddingError(f"无法连接{provider_label} Embedding 服务，请检查网络。") from exc

    if response.status_code >= 400:
        message = _provider_error_message(response)
        auth_problem = response.status_code in (401, 403) or any(
            marker in message.lower()
            for marker in ("api key", "apikey", "invalid key", "unauthorized", "鉴权", "密钥")
        )
        if auth_problem:
            raise EmbeddingError(
                f"{provider_label} API key 无效、已过期或无权限，请检查 .env 中的 {key_name}。",
                status_code=502,
            )
        raise EmbeddingError(
            f"{provider_label} Embedding 调用失败（HTTP {response.status_code}）：{message}"
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise EmbeddingError(f"{provider_label} Embedding 返回了无法解析的数据。") from exc

    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list) or len(data) != expected_count:
        raise EmbeddingError(f"{provider_label} Embedding 返回格式异常或数量不匹配。")

    ordered = sorted(data, key=lambda item: item.get("index", 0) if isinstance(item, dict) else 0)
    vectors: list[list[float]] = []
    for item in ordered:
        vector = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(vector, list) or not vector:
            raise EmbeddingError(f"{provider_label} Embedding 返回格式异常。")
        vectors.append(vector)
    return np.asarray(vectors, dtype=np.float32)


def _provider_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        text = response.text.strip()
        return text[:200] if text else "服务未返回错误详情"

    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code")
            if message:
                return str(message)[:200]
        message = body.get("message") or body.get("code")
        if message:
            return str(message)[:200]
    return str(body)[:200]


def _embed_local(texts: list[str]) -> np.ndarray:
    global _local_model

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingError(
            "本地 BGE 依赖未安装。请先执行：pip install -r requirements-local.txt",
            status_code=500,
        ) from exc

    if _local_model is None:
        with _local_lock:
            if _local_model is None:
                try:
                    _local_model = SentenceTransformer(settings.local_model, device="cpu")
                except Exception as exc:
                    raise EmbeddingError(
                        f"本地 BGE 模型加载失败：{exc}",
                        status_code=500,
                    ) from exc

    try:
        vectors = _local_model.encode(
            texts,
            normalize_embeddings=False,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
    except Exception as exc:
        raise EmbeddingError(f"本地 BGE 推理失败：{exc}", status_code=500) from exc
    return np.asarray(vectors, dtype=np.float32)

