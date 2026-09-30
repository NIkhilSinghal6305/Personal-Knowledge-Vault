# Personal Knowledge Vault

A local, private RAG app: upload PDF/DOCX/TXT files, index them with Sentence Transformers, and ask questions answered by a **local Qwen GGUF model** (via llama-cpp-python) with real source citations. Black-and-white UI, Flask backend, SQLite + persistent NumPy vector store.

## Pipeline

Upload → text extraction (`document_processor`) → cleaning → chunking (`chunker`, word-based with overlap, page/section labels kept) → embeddings (`embedding_service`, normalised) → per-user vector store (`vector_store`) → question embedding → cosine search → top-K chunks → prompt → Qwen (`llm_service`) → answer + sources (`rag_service`).

Knowledge Base mode only calls the model if retrieval finds chunks above `MIN_SCORE`; otherwise it returns *"I couldn't find relevant information in your knowledge base."* General AI mode never receives your documents and is labelled "General AI Answer". Sources are the actual retrieved chunks' filenames and page/section (shown only when known).

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # set SECRET_KEY
python app.py               # http://127.0.0.1:5000
```

Sign up, upload a document on **Knowledge Base**, then open **Chat**.

First-run downloads (internet needed once): the embedding model (~90 MB, on first upload) and the Qwen model (default `Qwen2.5-1.5B-Instruct` Q4_K_M, ~1.1 GB, on first chat) into `models/qwen/`. Set `HF_TOKEN` in `.env` only if your repo needs it; it is server-side only.

`llama-cpp-python` compiles native code: you need a C/C++ compiler and CMake (Windows: Visual Studio Build Tools). For a larger/better model set `QWEN_REPO` / `QWEN_FILE` (e.g. a 3B or 7B Instruct GGUF) and raise `LLM_CONTEXT` if needed.

## Configuration (`.env`)

See `.env.example`. Key values: `CHUNK_WORDS`, `CHUNK_OVERLAP`, `TOP_K`, `MIN_SCORE`, `EMBEDDING_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_CONTEXT`. Keep `TOP_K × CHUNK_WORDS` comfortably below `LLM_CONTEXT`. Note: `all-MiniLM-L6-v2` embeds roughly the first 256 tokens of each chunk, so use ~150–250 words per chunk for best retrieval with that model, or pick a longer-context embedding model. If you change `EMBEDDING_MODEL`, click **Rebuild index** in Settings.

## Layout

```
personal-knowledge-vault/
├── backend/    Flask app, API, RAG services, tests, data
│   ├── app.py  config.py  db.py  requirements.txt  .env.example
│   ├── routes/    (auth, documents, chat, dashboard)
│   ├── services/  (document_processor, chunker, embedding_service, vector_store,
│   │               llm_service, rag_service, ingestion, pdf_export)
│   ├── knowledge_base/{documents,embeddings,metadata}  database/  models/qwen/
│   └── tests/
└── frontend/   templates/ (Jinja HTML) and static/ (css, js)
```
The backend serves the frontend folder (path configurable with `FRONTEND_DIR`), so a single `python app.py` from `backend/` runs everything. All commands below run from `backend/`.

## API

`POST /api/auth/{signup,login,logout}` · `GET /api/documents` · `GET /api/documents/<id>` · `POST /api/documents/upload` · `DELETE /api/documents/<id>` · `POST /api/documents/<id>/reprocess` · `POST /api/documents/rebuild` · `GET /api/search?q=` · `POST /api/chat` `{message, mode, conversation_id}` · `GET /api/conversations[/<id>]` · `GET /api/messages/<id>/pdf` · `GET /api/dashboard/stats`.

## Tests

```bash
pytest
```
Tests use a small fake embedder and fake generator, so they run offline and need no model downloads. They cover auth, per-user isolation, upload/error handling, chunking, vector store, and the RAG flow.

## Production

```bash
export SECRET_KEY=$(python -c "import secrets;print(secrets.token_hex(32))")
export SESSION_COOKIE_SECURE=1
gunicorn -w 1 --threads 4 -b 127.0.0.1:8000 --timeout 300 "app:create_app()"
```

- Use **one worker**: the LLM and embedding model live in memory and the vector store is in-process. Scale with threads, or split the model into its own service if you need more.
- Put nginx/Caddy in front with HTTPS and set `client_max_body_size` ≥ `MAX_UPLOAD_MB`.
- Persist `database/`, `knowledge_base/` and `models/` (volumes if using Docker) and back them up.
- Uploads are processed in a background thread; a restart mid-processing leaves that document as "processing" — use **Re-process**.

## Security notes

Passwords use Werkzeug hashing; sessions are HttpOnly, SameSite=Lax cookies; every query is scoped to the logged-in user and each user has a separate vector index. There is no rate limiting or email verification, so add both before exposing this publicly.
