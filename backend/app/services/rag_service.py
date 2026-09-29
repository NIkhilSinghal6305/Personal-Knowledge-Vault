"""
RAG (Retrieval-Augmented Generation) service.
Orchestrates the full RAG pipeline: query → retrieve → generate.
"""
import json
from typing import List, Optional, Dict
from app.services.vector_store import query_similar_chunks
from app.services.llm_service import generate_response


SYSTEM_INSTRUCTION = """You are an intelligent knowledge assistant for a Personal Knowledge Vault.
Your role is to help users understand and work with their uploaded documents and notes.

IMPORTANT RULES:
1. Answer ONLY based on the provided context from the user's documents.
2. If the context does not contain enough information, clearly state:
   "I couldn't find enough information in your knowledge vault to answer this confidently."
3. Do NOT hallucinate or make up information.
4. Always cite which document(s) your answer comes from.
5. Be clear, concise, and well-structured in your responses.
6. Use markdown formatting for readability.
"""


def build_context(chunks: List[Dict]) -> str:
    """Build a context string from retrieved chunks."""
    if not chunks:
        return "No relevant documents found."

    context_parts = []
    for i, chunk in enumerate(chunks):
        doc_name = chunk.get("metadata", {}).get("document_name", "Unknown")
        chunk_idx = chunk.get("metadata", {}).get("chunk_index", "?")
        text = chunk.get("text", "")
        context_parts.append(
            f"--- Source: {doc_name} (Chunk {chunk_idx}) ---\n{text}"
        )

    return "\n\n".join(context_parts)


def extract_sources(chunks: List[Dict]) -> List[Dict]:
    """Extract source references from chunks."""
    sources = []
    seen = set()
    for chunk in chunks:
        doc_name = chunk.get("metadata", {}).get("document_name", "Unknown")
        if doc_name not in seen:
            sources.append(
                {
                    "document_name": doc_name,
                    "chunk_text": chunk.get("text", "")[:200] + "...",
                    "relevance_score": round(1 - chunk.get("distance", 0), 4),
                }
            )
            seen.add(doc_name)
    return sources


def rag_query(
    user_id: int,
    question: str,
    document_ids: Optional[List[int]] = None,
    n_results: int = 5,
) -> Dict:
    """
    Full RAG pipeline:
    1. Retrieve relevant chunks from ChromaDB
    2. Build context from chunks
    3. Generate answer using LLM with context
    4. Return answer with source references
    """
    # Step 1: Retrieve relevant chunks
    chunks = query_similar_chunks(
        user_id=user_id,
        query_text=question,
        n_results=n_results,
        document_ids=document_ids,
    )

    # Step 2: Build context
    context = build_context(chunks)

    # Step 3: Create the prompt
    prompt = f"""Based on the following context from the user's knowledge vault, answer the question.

CONTEXT:
{context}

QUESTION: {question}

Provide a clear, well-structured answer based ONLY on the context above. If the context doesn't contain enough information, say so clearly. Cite the source documents in your answer."""

    # Step 4: Generate answer
    answer = generate_response(prompt, system_instruction=SYSTEM_INSTRUCTION)

    # Step 5: Extract sources
    sources = extract_sources(chunks)

    return {
        "answer": answer,
        "sources": sources,
        "context_chunks": len(chunks),
    }


def summarize_document(
    user_id: int,
    document_id: int,
    document_text: str,
    document_name: str,
    summary_type: str = "short",
) -> str:
    """Generate a summary of a document."""
    type_instructions = {
        "short": "Provide a brief summary in 3-5 sentences capturing the main points.",
        "detailed": "Provide a comprehensive summary covering all major topics, arguments, and conclusions. Use headings and bullet points.",
        "key_points": "Extract and list the key points, important facts, and main takeaways as a numbered list.",
    }

    instruction = type_instructions.get(summary_type, type_instructions["short"])

    # Use first ~3000 chars for summary if text is very long
    text_for_summary = document_text[:5000] if len(document_text) > 5000 else document_text

    # Also get relevant chunks for a more complete picture
    chunks = query_similar_chunks(user_id, f"summary of {document_name}", n_results=3, document_ids=[document_id])
    extra_context = "\n".join([c["text"] for c in chunks]) if chunks else ""

    prompt = f"""Summarize the following document.

Document: {document_name}

{instruction}

DOCUMENT CONTENT:
{text_for_summary}

{f"ADDITIONAL CONTEXT: {extra_context}" if extra_context else ""}

Provide the summary in well-formatted markdown."""

    return generate_response(
        prompt,
        system_instruction="You are a helpful document summarizer. Create clear, accurate summaries based only on the provided content.",
    )


def explain_topic(
    user_id: int,
    topic: str,
    mode: str = "simple",
    document_ids: Optional[List[int]] = None,
) -> Dict:
    """Explain a topic using knowledge from the vault."""
    mode_instructions = {
        "simple": "Explain in simple, easy-to-understand language. Avoid jargon.",
        "technical": "Provide a technical, detailed explanation with proper terminology.",
        "examples": "Explain with practical examples and analogies.",
        "beginner": "Explain as if teaching a complete beginner. Use analogies, step-by-step explanations, and simple language.",
    }

    instruction = mode_instructions.get(mode, mode_instructions["simple"])

    chunks = query_similar_chunks(user_id, topic, n_results=5, document_ids=document_ids)
    context = build_context(chunks)
    sources = extract_sources(chunks)

    prompt = f"""Using the following context from the user's knowledge vault, explain the topic.

CONTEXT:
{context}

TOPIC: {topic}

{instruction}

Use markdown formatting. If the context doesn't cover the topic, indicate that."""

    answer = generate_response(
        prompt,
        system_instruction="You are a knowledgeable tutor. Explain concepts clearly using the provided context.",
    )

    return {"explanation": answer, "sources": sources}


def generate_notes(
    user_id: int,
    document_id: int,
    document_text: str,
    document_name: str,
) -> str:
    """Generate structured notes from a document."""
    text_for_notes = document_text[:5000] if len(document_text) > 5000 else document_text

    chunks = query_similar_chunks(user_id, f"key concepts in {document_name}", n_results=5, document_ids=[document_id])
    extra_context = "\n".join([c["text"] for c in chunks]) if chunks else ""

    prompt = f"""Convert the following document into well-structured study notes.

Document: {document_name}

DOCUMENT CONTENT:
{text_for_notes}

{f"ADDITIONAL CONTEXT: {extra_context}" if extra_context else ""}

Create notes in this format:
## Topic
### Definition
[Clear definition]

### Important Concepts
- Concept 1
- Concept 2

### Examples
- Example 1
- Example 2

### Key Points
- Point 1
- Point 2

Cover all major topics in the document. Use markdown formatting."""

    return generate_response(
        prompt,
        system_instruction="You are an expert note-taker. Create comprehensive, well-organized study notes from the provided content.",
        max_tokens=3000,
    )
