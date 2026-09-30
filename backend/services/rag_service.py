from config import Config

from . import embedding_service, llm_service

NOT_FOUND = "I couldn't find relevant information in your knowledge base."
LABELS = {"knowledge_base": "Knowledge Base Answer", "general": "General AI Answer"}

KB_SYSTEM = """You are the Personal Knowledge Vault AI assistant.

Answer the user's question using the retrieved knowledge-base context.

Do not invent facts that are not supported by the retrieved context.

If the retrieved context does not contain enough information to answer the question, explicitly state that the information was not found in the user's knowledge base.

Always distinguish between information retrieved from the knowledge base and general model knowledge. Cite context passages as [1], [2], etc. Be concise but useful."""

GENERAL_SYSTEM = ("You are the Personal Knowledge Vault AI assistant in General AI mode. "
                  "Answer from your general knowledge. You have not been given the user's documents, "
                  "so never claim that anything comes from them. Be concise but useful.")


def build_context(hits: list[dict]) -> str:
    parts = []
    for i, h in enumerate(hits, 1):
        loc = f", {h['location']}" if h.get("location") else ""
        parts.append(f"[{i}] Source: {h['filename']}{loc}\n{h['text']}")
    return "\n\n".join(parts)


def _sources(hits: list[dict]) -> list[dict]:
    seen, out = set(), []
    for h in hits:
        key = (h["document_id"], h.get("location"))
        if key not in seen:
            seen.add(key)
            out.append({"document_id": h["document_id"], "filename": h["filename"],
                        "location": h.get("location"), "score": round(h["score"], 3)})
    return out


def answer_question(query: str, mode: str = "knowledge_base", store=None, history: list[dict] | None = None) -> dict:
    """Run the RAG pipeline. `store` is the user's VectorStore (required in knowledge_base mode)."""
    if mode not in LABELS:
        raise ValueError("Unknown mode")
    history = (history or [])[-6:]
    if mode == "general":
        messages = [{"role": "system", "content": GENERAL_SYSTEM}, *history, {"role": "user", "content": query}]
        return {"answer": llm_service.generate(messages), "sources": [], "mode": mode, "label": LABELS[mode]}

    hits = []
    if store is not None:
        hits = store.search(embedding_service.generate_embedding(query), k=Config.TOP_K, min_score=Config.MIN_SCORE)
    if not hits:
        return {"answer": NOT_FOUND, "sources": [], "mode": mode, "label": LABELS[mode]}
    user = f"Context:\n{build_context(hits)}\n\nQuestion: {query}"
    messages = [{"role": "system", "content": KB_SYSTEM}, *history, {"role": "user", "content": user}]
    return {"answer": llm_service.generate(messages), "sources": _sources(hits), "mode": mode, "label": LABELS[mode]}
