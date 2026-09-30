"""Document -> chunks -> embeddings -> vector store, with status updates for the UI."""
import json
import logging
from pathlib import Path

from db import connect

from . import chunker, document_processor, embedding_service
from .document_processor import DocumentError
from .embedding_service import EmbeddingError
from .vector_store import VectorStoreError, get_store

logger = logging.getLogger(__name__)


def document_path(kb_dir, user_id: int, doc_id: int, ext: str) -> Path:
    return Path(kb_dir) / "documents" / str(user_id) / f"{doc_id}.{ext}"


def ingest_document(cfg: dict, doc_id: int) -> None:
    conn = connect(cfg["DATABASE"])

    def set_status(status, **extra):
        cols = {"status": status, **extra}
        conn.execute(f"UPDATE documents SET {', '.join(k + '=?' for k in cols)} WHERE id=?", (*cols.values(), doc_id))
        conn.commit()

    try:
        doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        if doc is None:
            return
        uid = doc["user_id"]
        set_status("extracting", error=None)
        sections = document_processor.extract(document_path(cfg["KB_DIR"], uid, doc_id, doc["file_type"]), doc["file_type"])
        set_status("chunking")
        chunks = chunker.chunk_sections(sections, cfg["CHUNK_WORDS"], cfg["CHUNK_OVERLAP"])
        set_status("embedding")
        vectors = embedding_service.generate_embeddings([c["text"] for c in chunks])
        set_status("indexing")
        conn.execute("DELETE FROM document_chunks WHERE document_id=?", (doc_id,))
        records = []
        for i, c in enumerate(chunks):
            cur = conn.execute("INSERT INTO document_chunks(document_id,user_id,chunk_index,text,location) VALUES(?,?,?,?,?)",
                               (doc_id, uid, i, c["text"], c["location"]))
            records.append({"chunk_id": cur.lastrowid, "document_id": doc_id, "filename": doc["filename"],
                            "text": c["text"], "location": c["location"], "metadata": {"chunk_index": i}})
        store = get_store(Path(cfg["KB_DIR"]) / "embeddings", uid)
        store.delete_document(doc_id)
        store.add_documents(records, vectors)
        meta_dir = Path(cfg["KB_DIR"]) / "metadata"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / f"{doc_id}.json").write_text(json.dumps(
            {"document_id": doc_id, "user_id": uid, "filename": doc["filename"], "chunks": len(chunks)}))
        set_status("ready", num_chunks=len(chunks), error=None)
    except (DocumentError, EmbeddingError, VectorStoreError) as e:
        conn.rollback()
        set_status("failed", error=str(e), num_chunks=0)
    except Exception:
        logger.exception("Unexpected ingestion error")
        conn.rollback()
        set_status("failed", error="Unexpected error while processing this document.", num_chunks=0)
    finally:
        conn.close()
