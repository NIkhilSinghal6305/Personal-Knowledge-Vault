"""Word-based chunking with overlap."""


def chunk_text(text: str, size: int = 400, overlap: int = 50) -> list[str]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("chunk size must be > 0 and overlap must be smaller than size")
    words = text.split()
    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        piece = words[start:start + size]
        if piece:
            chunks.append(" ".join(piece))
        if start + size >= len(words):
            break
    return chunks


def chunk_sections(sections: list[tuple[str | None, str]], size: int, overlap: int) -> list[dict]:
    """Chunk each (location, text) section separately so page/section labels stay accurate."""
    out = []
    for location, text in sections:
        for piece in chunk_text(text, size, overlap):
            out.append({"text": piece, "location": location})
    return out
