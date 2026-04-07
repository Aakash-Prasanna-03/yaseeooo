"""Brand memory: Pinecone primary, PostgreSQL JSONB fallback."""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings
from app import database as db


async def _gemini_embed(texts: List[str]) -> Optional[List[List[float]]]:
    s = get_settings()
    if not s.google_api_key or not texts:
        return None
    # text-embedding-004 often returns 404 on the consumer API; gemini-embedding-001 matches current REST docs.
    embed_model = "gemini-embedding-001"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{embed_model}:embedContent?key={s.google_api_key}"
    out: List[List[float]] = []
    async with httpx.AsyncClient(timeout=60) as client:
        for chunk in texts:
            body = {
                "model": f"models/{embed_model}",
                "content": {"parts": [{"text": chunk[:8000]}]},
            }
            r = await client.post(url, json=body)
            if r.status_code != 200:
                return None
            data = r.json()
            vals = data.get("embedding", {}).get("values")
            if not vals:
                return None
            out.append(vals)
    return out


async def upsert_brand_memory(workspace_id: uuid.UUID, texts: List[str], metadata: Dict[str, Any]) -> None:
    vectors = await _gemini_embed(texts)
    if vectors:
        for t, vec in zip(texts, vectors):
            await db.execute(
                """
                INSERT INTO brand_memory_embeddings (workspace_id, chunk_text, embedding, metadata)
                VALUES ($1, $2, $3::jsonb, $4::jsonb)
                """,
                workspace_id,
                t,
                json.dumps(vec),
                json.dumps(metadata),
            )


async def search_brand_memory(workspace_id: uuid.UUID, query: str, top_k: int = 5) -> List[str]:
    vecs = await _gemini_embed([query])
    if not vecs:
        rows = await db.fetch_all(
            """
            SELECT chunk_text FROM brand_memory_embeddings
            WHERE workspace_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            workspace_id,
            top_k,
        )
        return [r["chunk_text"] for r in rows]
    # Without Pinecone query endpoint wired, return recent PG chunks scored by naive length overlap
    rows = await db.fetch_all(
        """
        SELECT chunk_text, embedding FROM brand_memory_embeddings
        WHERE workspace_id = $1
        ORDER BY created_at DESC
        LIMIT 50
        """,
        workspace_id,
    )
    q = vecs[0]
    scored = []
    for r in rows:
        try:
            emb = json.loads(r["embedding"]) if isinstance(r["embedding"], str) else r["embedding"]
            sim = sum(a * b for a, b in zip(q, emb)) / (sum(a * a for a in q) ** 0.5 * sum(b * b for b in emb) ** 0.5 + 1e-9)
            scored.append((sim, r["chunk_text"]))
        except Exception:
            continue
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored[:top_k]] or [r["chunk_text"] for r in rows[:top_k]]
