from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

import numpy as np

from .config import settings
from .db import blob_to_vector, get_connection, vector_to_blob
from .errors import EmbeddingError
from .security import hash_session_token, new_session_token, session_expiry


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_user(*, username: str, password_hash: str) -> dict[str, Any]:
    created_at = utc_now()
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, created_at),
        )
        user_id = int(cursor.lastrowid)
    return {"id": user_id, "username": username}


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, username, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def create_session(user_id: int) -> tuple[str, str]:
    token = new_session_token()
    expires_at = session_expiry().isoformat(timespec="seconds")
    created_at = utc_now()
    with get_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (created_at,))
        connection.execute(
            """
            INSERT INTO sessions (token_hash, user_id, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (hash_session_token(token), user_id, expires_at, created_at),
        )
    return token, expires_at


def get_user_by_session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    token_hash = hash_session_token(token)
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT u.id, u.username, s.id AS session_id, s.expires_at
            FROM sessions AS s
            JOIN users AS u ON u.id = s.user_id
            WHERE s.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
        if not row:
            return None
        try:
            expires_at = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            connection.execute("DELETE FROM sessions WHERE id = ?", (row["session_id"],))
            return None
        if expires_at <= datetime.now(timezone.utc):
            connection.execute("DELETE FROM sessions WHERE id = ?", (row["session_id"],))
            return None
    return {"id": int(row["id"]), "username": row["username"]}


def delete_session(token: str | None) -> None:
    if not token:
        return
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM sessions WHERE token_hash = ?",
            (hash_session_token(token),),
        )


def create_report(
    *,
    user_id: int,
    kind: str,
    description: str,
    location: str | None,
    happened_at: str | None,
    contact: str,
    embedding: np.ndarray,
) -> tuple[int, list[dict[str, Any]]]:
    vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        raise EmbeddingError("Embedding 为零向量，无法保存记录。")
    vector = (vector / norm).astype(np.float32, copy=False)
    created_at = utc_now()
    provider = settings.embedding_provider
    model = _active_model_name(provider)

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO reports (
                user_id, kind, description, location, happened_at, contact,
                embedding, embedding_dim, embedding_provider, embedding_model, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                kind,
                description,
                location,
                happened_at,
                contact,
                vector_to_blob(vector),
                int(vector.shape[0]),
                provider,
                model,
                created_at,
            ),
        )
        report_id = int(cursor.lastrowid)
        matches = _rank_matches(
            connection,
            report_id=report_id,
            opposite_kind="found" if kind == "lost" else "lost",
            vector=vector,
            provider=provider,
            model=model,
        )
        for match in matches:
            connection.execute(
                """
                INSERT OR IGNORE INTO matches (
                    report_id, matched_report_id, similarity, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    report_id,
                    match["id"],
                    match["similarity"],
                    created_at,
                ),
            )
    return report_id, matches


def _rank_matches(
    connection: Any,
    *,
    report_id: int,
    opposite_kind: str,
    vector: np.ndarray,
    provider: str,
    model: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, description, location, contact, embedding
        FROM reports
        WHERE kind = ?
          AND id != ?
          AND embedding_provider = ?
          AND embedding_model = ?
          AND embedding_dim = ?
        """,
        (opposite_kind, report_id, provider, model, int(vector.shape[0])),
    ).fetchall()

    if not rows:
        return []

    matrix = np.vstack([blob_to_vector(row["embedding"]) for row in rows])
    scores = matrix @ vector
    order = np.argsort(-scores)

    matches: list[dict[str, Any]] = []
    for index in order:
        score = float(scores[int(index)])
        if not np.isfinite(score) or score < settings.match_threshold:
            continue
        row = rows[int(index)]
        matches.append(
            {
                "id": int(row["id"]),
                "description": row["description"],
                "location": row["location"],
                "contact": row["contact"],
                "similarity": max(0.0, min(1.0, score)),
                "kind": opposite_kind,
            }
        )
    return matches


def get_home(user_id: int | None = None) -> dict[str, Any]:
    safe_user_id = int(user_id) if user_id is not None else -1
    with get_connection() as connection:
        lost_posts = _board_posts(connection, "lost", safe_user_id)
        found_posts = _board_posts(connection, "found", safe_user_id)
        match_groups = _match_groups(connection, safe_user_id) if user_id is not None else []

    return {
        "authenticated": user_id is not None,
        "user": get_user_by_id(user_id) if user_id is not None else None,
        "lost_posts": lost_posts,
        "found_posts": found_posts,
        "match_groups": match_groups,
    }


def _board_posts(connection: Any, kind: str, user_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            r.id,
            r.kind,
            r.description,
            r.location,
            r.happened_at,
            u.username,
            CASE WHEN r.user_id = ? THEN 1 ELSE 0 END AS is_mine
        FROM reports AS r
        JOIN users AS u ON u.id = r.user_id
        WHERE r.kind = ?
        ORDER BY is_mine DESC, r.created_at DESC, r.id DESC
        """,
        (user_id, kind),
    ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "kind": row["kind"],
            "description": row["description"],
            "location": row["location"],
            "happened_at": row["happened_at"],
            "username": row["username"],
            "is_mine": bool(row["is_mine"]),
        }
        for row in rows
    ]


def _match_groups(connection: Any, user_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            m.id,
            m.similarity,
            a.id AS a_id,
            a.user_id AS a_user_id,
            a.kind AS a_kind,
            a.description AS a_description,
            a.location AS a_location,
            a.happened_at AS a_happened_at,
            a.contact AS a_contact,
            ua.username AS a_username,
            b.id AS b_id,
            b.user_id AS b_user_id,
            b.kind AS b_kind,
            b.description AS b_description,
            b.location AS b_location,
            b.happened_at AS b_happened_at,
            b.contact AS b_contact,
            ub.username AS b_username
        FROM matches AS m
        JOIN reports AS a ON a.id = m.report_id
        JOIN users AS ua ON ua.id = a.user_id
        JOIN reports AS b ON b.id = m.matched_report_id
        JOIN users AS ub ON ub.id = b.user_id
        WHERE a.user_id = ? OR b.user_id = ?
        ORDER BY m.similarity DESC, m.id DESC
        """,
        (user_id, user_id),
    ).fetchall()

    groups: OrderedDict[int, dict[str, Any]] = OrderedDict()
    for row in rows:
        choose_first = int(row["a_user_id"]) == user_id
        own_prefix = "a" if choose_first else "b"
        other_prefix = "b" if choose_first else "a"
        own_id = int(row[f"{own_prefix}_id"])
        group = groups.get(own_id)
        if group is None:
            group = {
                "report": {
                    "id": own_id,
                    "kind": row[f"{own_prefix}_kind"],
                    "description": row[f"{own_prefix}_description"],
                    "location": row[f"{own_prefix}_location"],
                    "happened_at": row[f"{own_prefix}_happened_at"],
                    "username": row[f"{own_prefix}_username"],
                    "is_mine": True,
                },
                "matches": [],
            }
            groups[own_id] = group

        group["matches"].append(
            {
                "id": int(row["id"]),
                "similarity": max(0.0, min(1.0, float(row["similarity"]))),
                "own_username": row[f"{own_prefix}_username"],
                "own_contact": row[f"{own_prefix}_contact"],
                "other_username": row[f"{other_prefix}_username"],
                "other_contact": row[f"{other_prefix}_contact"],
                "other_kind": row[f"{other_prefix}_kind"],
                "other_description": row[f"{other_prefix}_description"],
                "other_location": row[f"{other_prefix}_location"],
                "other_happened_at": row[f"{other_prefix}_happened_at"],
            }
        )
    return list(groups.values())


def complete_report(user_id: int, report_id: int) -> list[int]:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT user_id FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        if not row:
            raise LookupError("发布不存在或已经删除。")
        if int(row["user_id"]) != user_id:
            raise PermissionError("只能确认自己发布的物品。")

        related = connection.execute(
            """
            SELECT report_id, matched_report_id
            FROM matches
            WHERE report_id = ? OR matched_report_id = ?
            """,
            (report_id, report_id),
        ).fetchall()
        deleted_ids = {report_id}
        for match in related:
            deleted_ids.add(int(match["report_id"]))
            deleted_ids.add(int(match["matched_report_id"]))

        placeholders = ",".join("?" for _ in deleted_ids)
        connection.execute(
            f"DELETE FROM reports WHERE id IN ({placeholders})",
            tuple(sorted(deleted_ids)),
        )
    return sorted(deleted_ids)


def count_users() -> int:
    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
    return int(row["total"])


def count_reports() -> int:
    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM reports").fetchone()
    return int(row["total"])


def _active_model_name(provider: str) -> str:
    if provider == "qwen":
        return settings.qwen_model
    if provider == "zhipu":
        return settings.zhipu_model
    if provider == "local":
        return settings.local_model
    return provider
