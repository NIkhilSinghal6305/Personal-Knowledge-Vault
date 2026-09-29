"""
Pydantic schemas for chat and AI features.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class SourceReference(BaseModel):
    document_name: str
    chunk_text: str
    relevance_score: float


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: Optional[int] = None
    document_ids: Optional[List[int]] = None  # optionally scope to specific docs


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceReference] = []
    session_id: int


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    sources: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageResponse] = []

    class Config:
        from_attributes = True


class SummarizeRequest(BaseModel):
    document_id: int
    summary_type: str = "short"  # short, detailed, key_points


class SummarizeResponse(BaseModel):
    summary: str
    document_name: str
    summary_type: str


class QuizRequest(BaseModel):
    document_ids: List[int] = Field(..., min_length=1)
    num_questions: int = Field(default=5, ge=1, le=20)
    difficulty: str = "medium"  # easy, medium, hard
    topic: Optional[str] = None


class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: int  # index of correct option
    explanation: str


class QuizResponse(BaseModel):
    questions: List[QuizQuestion]
    topic: Optional[str] = None
    difficulty: str
    source_documents: List[str]


class ExplainRequest(BaseModel):
    topic: str
    mode: str = "simple"  # simple, technical, examples, beginner
    document_ids: Optional[List[int]] = None


class ExplainResponse(BaseModel):
    explanation: str
    mode: str
    sources: List[SourceReference] = []


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    search_type: str = "semantic"  # semantic, keyword
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None


class SearchResult(BaseModel):
    type: str  # document, note
    id: int
    title: str
    snippet: str
    relevance_score: Optional[float] = None
    category: Optional[str] = None
    tags: List[str] = []


class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str
    total: int


class DashboardResponse(BaseModel):
    total_documents: int
    total_notes: int
    total_categories: int
    total_tags: int
    recent_documents: List[dict]
    recent_notes: List[dict]
