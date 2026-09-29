"""
Pydantic schemas for notes.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from app.schemas.document import TagResponse, CategoryResponse


class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    category_id: Optional[int] = None
    tags: Optional[List[str]] = []
    is_pinned: Optional[bool] = False


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None
    is_pinned: Optional[bool] = None


class NoteResponse(BaseModel):
    id: int
    title: str
    content: str
    is_pinned: bool
    category: Optional[CategoryResponse] = None
    tags: List[TagResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
