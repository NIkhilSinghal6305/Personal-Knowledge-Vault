"""
Pydantic schemas for documents.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class TagResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    color: Optional[str] = "#6366f1"


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    color: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    summary: Optional[str] = None
    extracted_text: Optional[str] = None
    category: Optional[CategoryResponse] = None
    tags: List[TagResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    category: Optional[CategoryResponse] = None
    tags: List[TagResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentUpdate(BaseModel):
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None
