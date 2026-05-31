from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import KnowledgeSnippet
from app.db.session import get_db
from app.dependencies.auth import require_api_key
from app.services.knowledge import create_snippet, retrieve_snippets, serialize_snippet

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge-v1"])


class KnowledgeSnippetRequest(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    category: str | None = None
    keywords: list[str] = Field(default_factory=list)
    created_by: str | None = None


class KnowledgeSnippetUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    keywords: list[str] | None = None


@router.get("")
def list_snippets(db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    rows = (
        db.query(KnowledgeSnippet)
        .filter(KnowledgeSnippet.client_id == current_client.id)
        .order_by(KnowledgeSnippet.updated_at.desc())
        .all()
    )
    return {"items": [serialize_snippet(row) for row in rows]}


@router.post("")
def create_knowledge_snippet(payload: KnowledgeSnippetRequest, db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    snippet = create_snippet(
        db,
        client_id=current_client.id,
        title=payload.title,
        content=payload.content,
        category=payload.category,
        keywords=payload.keywords,
        created_by=payload.created_by,
    )
    db.commit()
    db.refresh(snippet)
    return {"success": True, "item": serialize_snippet(snippet)}


@router.get("/search")
def search_snippets(q: str = Query(default=""), limit: int = 5, db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    return {"items": [serialize_snippet(item) for item in retrieve_snippets(db, client_id=current_client.id, query=q, limit=limit)]}


@router.patch("/{snippet_id}")
def update_snippet(
    snippet_id: str,
    payload: KnowledgeSnippetUpdateRequest,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    snippet = (
        db.query(KnowledgeSnippet)
        .filter(KnowledgeSnippet.id == uuid.UUID(snippet_id), KnowledgeSnippet.client_id == current_client.id)
        .first()
    )
    if snippet is None:
        raise HTTPException(status_code=404, detail="Snippet not found")
    if payload.title is not None:
        snippet.title = payload.title.strip()
    if payload.content is not None:
        snippet.content = payload.content.strip()
    if payload.category is not None:
        snippet.category = payload.category.strip() or None
    if payload.keywords is not None:
        snippet.keywords = payload.keywords
    db.commit()
    db.refresh(snippet)
    return {"success": True, "item": serialize_snippet(snippet)}


@router.delete("/{snippet_id}")
def delete_snippet(
    snippet_id: str,
    db: Session = Depends(get_db),
    current_client=Depends(require_api_key),
):
    snippet = (
        db.query(KnowledgeSnippet)
        .filter(KnowledgeSnippet.id == uuid.UUID(snippet_id), KnowledgeSnippet.client_id == current_client.id)
        .first()
    )
    if snippet is None:
        raise HTTPException(status_code=404, detail="Snippet not found")
    db.delete(snippet)
    db.commit()
    return {"success": True}


@router.patch("/{snippet_id}/status")
def update_snippet_status(snippet_id: str, status: str, db: Session = Depends(get_db), current_client=Depends(require_api_key)):
    if status not in {"active", "archived"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    snippet = (
        db.query(KnowledgeSnippet)
        .filter(KnowledgeSnippet.id == uuid.UUID(snippet_id), KnowledgeSnippet.client_id == current_client.id)
        .first()
    )
    if snippet is None:
        raise HTTPException(status_code=404, detail="Snippet not found")
    snippet.status = status
    db.commit()
    db.refresh(snippet)
    return {"success": True, "item": serialize_snippet(snippet)}
