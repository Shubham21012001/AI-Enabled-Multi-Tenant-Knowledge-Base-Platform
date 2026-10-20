"""Step 3: split text into overlapping chunks.

Why overlap? A fact can straddle a chunk boundary ("Employees get 24 days of
leave. | Unused days carry over..."). With 200 characters of overlap, the end of
chunk N is repeated at the start of chunk N+1, so a sentence cut by one
boundary still appears whole in a neighbouring chunk and can be retrieved.

We prefer to cut at natural boundaries (paragraph > line > sentence > word)
inside the last part of each window, so chunks rarely split mid-sentence.
"""
from app.core.config import settings

_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "]


def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    size = chunk_size or settings.CHUNK_SIZE
    overlap = settings.CHUNK_OVERLAP if overlap is None else overlap
    if overlap >= size:
        raise ValueError("overlap must be smaller than chunk_size")

    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            end = _find_break(text, start, end, size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        # Step back by `overlap`, but always move forward to avoid infinite loops.
        next_start = max(end - overlap, start + 1)
        # Don't start the next chunk mid-word.
        space = text.find(" ", next_start, end)
        start = space + 1 if space != -1 and space + 1 < end else next_start
    return chunks


def _find_break(text: str, start: int, end: int, size: int) -> int:
    """Find the best natural break in the last half of the window."""
    min_end = start + size // 2
    for sep in _SEPARATORS:
        idx = text.rfind(sep, min_end, end)
        if idx != -1:
            return idx + len(sep)
    return end
