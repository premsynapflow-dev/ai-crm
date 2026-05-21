from __future__ import annotations

import re
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import KnowledgeSnippet


def normalize_keywords(value: list[str] | None, title: str = "", content: str = "") -> list[str]:
    items = [str(item).strip().lower() for item in (value or []) if str(item).strip()]
    if not items:
        words = re.findall(r"\b[a-zA-Z0-9]{4,}\b", f"{title} {content}".lower())
        items = list(dict.fromkeys(words[:12]))
    return items[:25]


def create_snippet(
    db: Session,
    *,
    client_id,
    title: str,
    content: str,
    category: str | None = None,
    keywords: list[str] | None = None,
    created_by: str | None = None,
) -> KnowledgeSnippet:
    snippet = KnowledgeSnippet(
        client_id=client_id,
        title=title.strip(),
        content=content.strip(),
        category=(category or "").strip() or None,
        keywords=normalize_keywords(keywords, title, content),
        created_by=created_by,
    )
    db.add(snippet)
    db.flush()
    return snippet


def retrieve_snippets(db: Session, *, client_id, query: str, limit: int = 5) -> list[KnowledgeSnippet]:
    query_text = (query or "").strip().lower()
    snippets = (
        db.query(KnowledgeSnippet)
        .filter(KnowledgeSnippet.client_id == client_id, KnowledgeSnippet.status == "active")
        .limit(200)
        .all()
    )
    terms = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", query_text))
    scored: list[tuple[int, KnowledgeSnippet]] = []
    for snippet in snippets:
        haystack = f"{snippet.title} {snippet.content} {snippet.category or ''}".lower()
        keywords = {str(item).lower() for item in (snippet.keywords or [])}
        score = sum(2 for term in terms if term in keywords) + sum(1 for term in terms if term in haystack)
        if score > 0 or not terms:
            scored.append((score, snippet))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [snippet for _, snippet in scored[: max(1, min(limit, 20))]]


def serialize_snippet(snippet: KnowledgeSnippet) -> dict[str, Any]:
    return {
        "id": str(snippet.id),
        "client_id": str(snippet.client_id),
        "title": snippet.title,
        "content": snippet.content,
        "category": snippet.category,
        "keywords": snippet.keywords or [],
        "source_type": snippet.source_type,
        "status": snippet.status,
        "created_by": snippet.created_by,
        "created_at": snippet.created_at.isoformat() if snippet.created_at else None,
        "updated_at": snippet.updated_at.isoformat() if snippet.updated_at else None,
    }
