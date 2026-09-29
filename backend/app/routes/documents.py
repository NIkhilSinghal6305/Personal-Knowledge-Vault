"""
Document management routes: upload, list, get, delete.
"""
import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.document import Document, Tag
from app.models.category import Category
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
    CategoryCreate,
    CategoryResponse,
    TagResponse,
)
from app.schemas.chat import DashboardResponse
from app.utils.auth import get_current_user
from app.config import get_settings
from app.services.document_processor import DocumentProcessor
from app.services.vector_store import store_document_chunks, delete_document_chunks

settings = get_settings()
router = APIRouter(prefix="/api", tags=["Documents"])


def process_document_background(
    document_id: int,
    file_path: str,
    file_type: str,
    original_filename: str,
    user_id: int,
):
    """Background task to process a document after upload."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return

        # Process the document
        extracted_text, chunks = DocumentProcessor.process_document(
            file_path, file_type, original_filename
        )

        # Store chunks in ChromaDB
        chunk_count = store_document_chunks(user_id, document_id, chunks)

        # Update document record
        doc.extracted_text = extracted_text
        doc.chunk_count = chunk_count
        doc.status = "completed"
        db.commit()

    except Exception as e:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = "failed"
            doc.extracted_text = f"Processing error: {str(e)}"
            db.commit()
    finally:
        db.close()


@router.post("/documents/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category_id: Optional[int] = Form(None),
    tags: Optional[str] = Form(None),  # comma-separated tag names
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document for processing and embedding."""
    # Validate file type
    try:
        file_type = DocumentProcessor.validate_file_type(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Validate file size
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB.",
        )

    # Create upload directory
    user_upload_dir = os.path.join(settings.UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_upload_dir, exist_ok=True)

    # Save file with unique name
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(user_upload_dir, unique_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # Validate category
    if category_id:
        cat = db.query(Category).filter(
            Category.id == category_id, Category.user_id == current_user.id
        ).first()
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")

    # Create document record
    doc = Document(
        user_id=current_user.id,
        filename=unique_filename,
        original_filename=file.filename,
        file_type=file_type,
        file_size=len(content),
        file_path=file_path,
        category_id=category_id,
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Handle tags
    if tags:
        tag_names = [t.strip().lower().replace("#", "") for t in tags.split(",") if t.strip()]
        for tag_name in tag_names:
            tag = db.query(Tag).filter(Tag.name == tag_name, Tag.user_id == current_user.id).first()
            if not tag:
                tag = Tag(name=tag_name, user_id=current_user.id)
                db.add(tag)
                db.commit()
                db.refresh(tag)
            doc.tags.append(tag)
        db.commit()
        db.refresh(doc)

    # Process document in background
    background_tasks.add_task(
        process_document_background,
        doc.id,
        file_path,
        file_type,
        file.filename,
        current_user.id,
    )

    return DocumentResponse.model_validate(doc)


@router.get("/documents", response_model=List[DocumentListResponse])
def list_documents(
    category_id: Optional[int] = None,
    tag: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all documents for the current user."""
    query = db.query(Document).filter(Document.user_id == current_user.id)

    if category_id:
        query = query.filter(Document.category_id == category_id)

    if tag:
        query = query.join(Document.tags).filter(Tag.name == tag.lower())

    docs = query.order_by(Document.created_at.desc()).all()
    return [DocumentListResponse.model_validate(d) for d in docs]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific document by ID."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.put("/documents/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: int,
    update_data: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update document metadata (category, tags)."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if update_data.category_id is not None:
        if update_data.category_id == 0:
            doc.category_id = None
        else:
            cat = db.query(Category).filter(
                Category.id == update_data.category_id,
                Category.user_id == current_user.id,
            ).first()
            if not cat:
                raise HTTPException(status_code=404, detail="Category not found")
            doc.category_id = update_data.category_id

    if update_data.tags is not None:
        doc.tags.clear()
        for tag_name in update_data.tags:
            tag_name = tag_name.strip().lower().replace("#", "")
            if not tag_name:
                continue
            tag = db.query(Tag).filter(Tag.name == tag_name, Tag.user_id == current_user.id).first()
            if not tag:
                tag = Tag(name=tag_name, user_id=current_user.id)
                db.add(tag)
                db.commit()
                db.refresh(tag)
            doc.tags.append(tag)

    db.commit()
    db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document and its embeddings."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete embeddings from ChromaDB
    delete_document_chunks(current_user.id, document_id)

    # Delete the file
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    # Delete from database
    db.delete(doc)
    db.commit()


# ---- Category routes ----

@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    cat_data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new category."""
    existing = db.query(Category).filter(
        Category.name == cat_data.name,
        Category.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")

    cat = Category(
        name=cat_data.name,
        description=cat_data.description,
        color=cat_data.color or "#6366f1",
        user_id=current_user.id,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return CategoryResponse.model_validate(cat)


@router.get("/categories", response_model=List[CategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all categories for the current user."""
    cats = db.query(Category).filter(Category.user_id == current_user.id).order_by(Category.name).all()
    return [CategoryResponse.model_validate(c) for c in cats]


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a category."""
    cat = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user.id,
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(cat)
    db.commit()


# ---- Tags ----

@router.get("/tags", response_model=List[TagResponse])
def list_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all tags for the current user."""
    tags = db.query(Tag).filter(Tag.user_id == current_user.id).order_by(Tag.name).all()
    return [TagResponse.model_validate(t) for t in tags]


# ---- Dashboard ----

@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard stats for the current user."""
    from app.models.note import Note

    total_docs = db.query(Document).filter(Document.user_id == current_user.id).count()
    total_notes = db.query(Note).filter(Note.user_id == current_user.id).count()
    total_cats = db.query(Category).filter(Category.user_id == current_user.id).count()
    total_tags = db.query(Tag).filter(Tag.user_id == current_user.id).count()

    recent_docs = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .limit(5)
        .all()
    )
    recent_notes = (
        db.query(Note)
        .filter(Note.user_id == current_user.id)
        .order_by(Note.updated_at.desc())
        .limit(5)
        .all()
    )

    return DashboardResponse(
        total_documents=total_docs,
        total_notes=total_notes,
        total_categories=total_cats,
        total_tags=total_tags,
        recent_documents=[
            {
                "id": d.id,
                "filename": d.original_filename,
                "file_type": d.file_type,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else "",
            }
            for d in recent_docs
        ],
        recent_notes=[
            {
                "id": n.id,
                "title": n.title,
                "is_pinned": n.is_pinned,
                "updated_at": n.updated_at.isoformat() if n.updated_at else "",
            }
            for n in recent_notes
        ],
    )
