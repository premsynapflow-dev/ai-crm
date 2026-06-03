"""Complaint clustering via Gemini embeddings + pure-Python DBSCAN.

Pipeline:
  1. generate_embeddings_batch()  — calls Gemini text-embedding-004, stores to complaint_embeddings
  2. cluster_complaints()         — loads embeddings, runs DBSCAN (cosine), stores clusters
  3. label_clusters()             — generates Gemini summaries for each cluster

DBSCAN parameters:
  epsilon = 0.25 (cosine distance threshold)
  min_samples = 3
"""
from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Complaint, ComplaintCluster, ComplaintEmbedding
from app.utils.logging import get_logger

logger = get_logger(__name__)

_EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "text-embedding-004:embedContent"
)
_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)

DBSCAN_EPSILON = 0.25
DBSCAN_MIN_SAMPLES = 3


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

def _gemini_embed(text_input: str, api_key: str) -> list[float] | None:
    """Call Gemini text-embedding-004 and return the embedding vector."""
    try:
        resp = httpx.post(
            _EMBED_URL,
            params={"key": api_key},
            json={
                "model": "models/text-embedding-004",
                "content": {"parts": [{"text": text_input[:2000]}]},
                "taskType": "CLUSTERING",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]["values"]
    except Exception as exc:
        logger.warning("Gemini embed failed: %s", exc)
        return None


def generate_embeddings_batch(
    db: Session,
    client_id: str,
    batch_size: int = 50,
    days: int = 30,
) -> int:
    """Generate and store embeddings for complaints that don't have one yet."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Complaints without an embedding
    existing_ids = {
        row[0]
        for row in db.query(ComplaintEmbedding.complaint_id).all()
    }

    complaints = (
        db.query(Complaint)
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= cutoff,
            Complaint.summary.isnot(None),
        )
        .limit(batch_size * 2)
        .all()
    )

    stored = 0
    for complaint in complaints:
        if complaint.id in existing_ids:
            continue
        if stored >= batch_size:
            break

        text_input = f"{complaint.category or ''} {complaint.summary or ''}"
        vector = _gemini_embed(text_input.strip(), api_key)
        if vector is None:
            continue

        emb = ComplaintEmbedding(
            complaint_id=complaint.id,
            embedding=json.dumps(vector),
            model_version="text-embedding-004",
        )
        db.add(emb)
        stored += 1

    if stored:
        db.commit()

    return stored


# ---------------------------------------------------------------------------
# Pure-Python DBSCAN on cosine distance
# ---------------------------------------------------------------------------

def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 1.0
    return 1.0 - (dot / (mag_a * mag_b))


def _range_query(
    idx: int,
    vectors: list[list[float]],
    epsilon: float,
) -> list[int]:
    return [
        j
        for j, v in enumerate(vectors)
        if j != idx and _cosine_distance(vectors[idx], v) <= epsilon
    ]


def dbscan(
    vectors: list[list[float]],
    epsilon: float = DBSCAN_EPSILON,
    min_samples: int = DBSCAN_MIN_SAMPLES,
) -> list[int]:
    """
    Returns a label array parallel to `vectors`.
    -1 = noise, 0+ = cluster id.
    """
    n = len(vectors)
    labels = [-1] * n
    cluster_id = 0
    visited = set()

    for i in range(n):
        if i in visited:
            continue
        visited.add(i)
        neighbors = _range_query(i, vectors, epsilon)
        if len(neighbors) < min_samples:
            continue  # noise for now; may be absorbed by another cluster

        labels[i] = cluster_id
        seed_set = list(neighbors)
        j = 0
        while j < len(seed_set):
            q = seed_set[j]
            if q not in visited:
                visited.add(q)
                q_neighbors = _range_query(q, vectors, epsilon)
                if len(q_neighbors) >= min_samples:
                    seed_set.extend(
                        nb for nb in q_neighbors if nb not in seed_set
                    )
            if labels[q] == -1:
                labels[q] = cluster_id
            j += 1

        cluster_id += 1

    return labels


# ---------------------------------------------------------------------------
# Cluster persistence + Gemini labelling
# ---------------------------------------------------------------------------

def _gemini_cluster_summary(complaint_texts: list[str], api_key: str) -> str:
    """Ask Gemini to summarise a cluster of complaint snippets in 1-2 sentences."""
    snippets = "\n".join(f"- {t[:200]}" for t in complaint_texts[:5])
    prompt = (
        "These customer complaints are grouped together because they are semantically similar.\n"
        f"Complaints:\n{snippets}\n\n"
        "Write a single sentence (max 20 words) describing the common issue."
    )
    try:
        resp = httpx.post(
            _GEMINI_URL,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 80},
            },
            timeout=8.0,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return "Mixed customer complaints"


def cluster_complaints(
    db: Session,
    client_id: str,
    days: int = 30,
) -> dict[str, Any]:
    """
    Load embeddings for the past `days`, run DBSCAN, store results.
    Returns summary: {clusters_created, noise_count, complaints_clustered}.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    period_start = cutoff.date()
    period_end = date.today()

    # Load all embeddings for this client in the window
    rows = (
        db.query(Complaint.id, Complaint.summary, Complaint.category, ComplaintEmbedding.embedding)
        .join(ComplaintEmbedding, ComplaintEmbedding.complaint_id == Complaint.id)
        .filter(
            Complaint.client_id == client_id,
            Complaint.created_at >= cutoff,
        )
        .all()
    )

    if len(rows) < DBSCAN_MIN_SAMPLES:
        return {"clusters_created": 0, "noise_count": len(rows), "complaints_clustered": 0}

    complaint_ids = [r[0] for r in rows]
    summaries = [r[1] or "" for r in rows]
    categories = [r[2] or "unknown" for r in rows]
    vectors = []
    for r in rows:
        try:
            vectors.append(json.loads(r[3]))
        except Exception:
            vectors.append([0.0] * 768)

    labels = dbscan(vectors, epsilon=DBSCAN_EPSILON, min_samples=DBSCAN_MIN_SAMPLES)

    # Group by cluster label
    cluster_members: dict[int, list[int]] = defaultdict(list)
    for idx, label in enumerate(labels):
        cluster_members[label].append(idx)

    noise_count = len(cluster_members.get(-1, []))
    clusters_created = 0

    for label, member_indices in cluster_members.items():
        if label == -1:
            continue

        member_categories = [categories[i] for i in member_indices]
        top_category = Counter(member_categories).most_common(1)[0][0]
        member_summaries = [summaries[i] for i in member_indices]

        # Generate summary via Gemini if available
        summary_text = (
            _gemini_cluster_summary(member_summaries, api_key)
            if api_key
            else f"Cluster of {len(member_indices)} {top_category} complaints"
        )

        cluster = ComplaintCluster(
            client_id=client_id,
            cluster_label=label,
            cluster_size=len(member_indices),
            summary=summary_text,
            top_category=top_category,
            top_entities={},
            period_start=period_start,
            period_end=period_end,
        )
        db.add(cluster)
        db.flush()

        # Tag complaints with their cluster
        for i in member_indices:
            comp = db.query(Complaint).filter(Complaint.id == complaint_ids[i]).first()
            if comp:
                comp.cluster_id = cluster.id

        clusters_created += 1

    db.commit()

    return {
        "clusters_created": clusters_created,
        "noise_count": noise_count,
        "complaints_clustered": len(rows) - noise_count,
    }
