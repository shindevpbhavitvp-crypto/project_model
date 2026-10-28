import re
import math
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from config import Config
from database.db import get_db, split_text_into_chunks

# Optional document parsing libraries
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import docx
except ImportError:
    docx = None

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "tell", "show", "give", "please", "college", "college's"
}

def tokenize(text: str):
    """Clean and extract alphanumeric word tokens."""
    return [w for w in re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower()) if w not in STOP_WORDS]

def extract_text_from_file(file_path: Path):
    """
    Extract readable text from TXT, MD, PDF, or DOCX files.
    Gracefully handles empty or unreadable files.
    """
    suffix = file_path.suffix.lower()
    
    if suffix in {".txt", ".md"}:
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception as e:
            return f"Error reading text file: {e}"
            
    elif suffix == ".pdf":
        if PdfReader is None:
            return "Error: pypdf library is not installed on this system."
        try:
            reader = PdfReader(str(file_path))
            pages_text = []
            for i, page in enumerate(reader.pages):
                txt = page.extract_text()
                if txt:
                    pages_text.append(txt)
            if not pages_text:
                return "Note: Scanned PDF without selectable text or OCR stream."
            return "\n".join(pages_text).strip()
        except Exception as e:
            return f"Error reading PDF file: {e}"
            
    elif suffix == ".docx":
        if docx is None:
            return "Error: python-docx library is not installed on this system."
        try:
            doc = docx.Document(str(file_path))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_txt = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                    if row_txt:
                        paragraphs.append(row_txt)
            return "\n".join(paragraphs).strip()
        except Exception as e:
            return f"Error reading DOCX file: {e}"
            
    return ""

def save_and_index_document(file_storage):
    """
    Validate, save to documents folder, extract text, chunk, and index into SQLite.
    Returns (success_boolean, message, doc_metadata).
    """
    if not file_storage or not file_storage.filename:
        return False, "No file selected.", None
        
    original_name = file_storage.filename
    clean_name = secure_filename(original_name)
    if not clean_name:
        return False, "Invalid filename provided.", None
        
    ext = Path(clean_name).suffix.lower()
    if ext not in Config.ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type '{ext}'. Allowed: {', '.join(Config.ALLOWED_EXTENSIONS)}", None
        
    destination = Config.DOCUMENTS_FOLDER / clean_name
    
    # Save file to disk
    try:
        Config.DOCUMENTS_FOLDER.mkdir(parents=True, exist_ok=True)
        file_storage.save(str(destination))
        file_size = destination.stat().st_size
    except Exception as e:
        return False, f"Failed to save file to disk: {str(e)}", None
        
    # Extract text
    text_content = extract_text_from_file(destination)
    if not text_content or text_content.startswith("Error"):
        # Still keep record or reject if unreadable
        if text_content.startswith("Error"):
            destination.unlink(missing_ok=True)
            return False, text_content, None
            
    chunks = split_text_into_chunks(text_content, max_chunk_words=120, overlap_words=25)
    upload_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    file_type = ext.replace(".", "").upper()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if file with same filename already indexed, remove old index first
        cursor.execute("SELECT id FROM uploaded_documents WHERE filename = ?", (clean_name,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("DELETE FROM uploaded_documents WHERE id = ?", (existing["id"],))
            
        cursor.execute("""
            INSERT INTO uploaded_documents (filename, original_name, file_type, file_size, upload_date, chunk_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (clean_name, original_name, file_type, file_size, upload_date, len(chunks)))
        doc_id = cursor.lastrowid
        
        chunk_rows = []
        for idx, chunk in enumerate(chunks):
            token_count = len(chunk.split())
            chunk_rows.append((doc_id, idx, chunk, token_count))
            
        if chunk_rows:
            cursor.executemany("""
                INSERT INTO document_chunks (document_id, chunk_index, chunk_text, token_count)
                VALUES (?, ?, ?, ?)
            """, chunk_rows)
            
        conn.commit()
        
    return True, f"'{clean_name}' successfully processed and indexed into {len(chunks)} searchable chunks.", {
        "id": doc_id,
        "filename": clean_name,
        "original_name": original_name,
        "file_type": file_type,
        "file_size": file_size,
        "upload_date": upload_date,
        "chunk_count": len(chunks)
    }

def delete_document(doc_id: int):
    """
    Delete a document from disk and database (cascading deletes chunks).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM uploaded_documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        if not row:
            return False, "Document not found."
            
        filename = row["filename"]
        cursor.execute("DELETE FROM uploaded_documents WHERE id = ?", (doc_id,))
        conn.commit()
        
    # Remove file from disk
    file_path = Config.DOCUMENTS_FOLDER / filename
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception:
            pass
            
    return True, f"Document '{filename}' and all its indexed chunks were deleted."

def list_all_documents():
    """List all uploaded documents with metadata."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, filename, original_name, file_type, file_size, upload_date, chunk_count
            FROM uploaded_documents
            ORDER BY id DESC
        """)
        return [dict(r) for r in cursor.fetchall()]

def retrieve_relevant_chunks(query: str, top_k: int = 3):
    """
    Retrieve top K document chunks matching the query using BM25-style scoring.
    Returns list of dicts: {chunk_id, doc_id, filename, chunk_index, chunk_text, score}
    """
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id as chunk_id, c.document_id, c.chunk_index, c.chunk_text, c.token_count, d.filename, d.original_name
            FROM document_chunks c
            JOIN uploaded_documents d ON c.document_id = d.id
        """)
        all_chunks = cursor.fetchall()
        
    if not all_chunks:
        return []
        
    N = len(all_chunks)
    total_tokens = sum(c["token_count"] for c in all_chunks)
    avgdl = (total_tokens / N) if N > 0 else 100
    
    # Document frequency per token
    doc_freq = {}
    for token in set(query_tokens):
        cnt = 0
        for c in all_chunks:
            if token in c["chunk_text"].lower():
                cnt += 1
        doc_freq[token] = cnt
        
    k1 = 1.5
    b = 0.75
    scored = []
    
    for c in all_chunks:
        text_lower = c["chunk_text"].lower()
        fn_lower = c["filename"].lower()
        chunk_len = c["token_count"] or 1
        score = 0.0
        matched_tokens = 0
        
        for token in query_tokens:
            # count term frequency in chunk
            tf = len(re.findall(r"\b" + re.escape(token) + r"\b", text_lower))
            if tf > 0:
                matched_tokens += 1
                df = doc_freq.get(token, 0)
                # Smoothed IDF
                idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
                # BM25 tf normalization
                tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (chunk_len / avgdl)))
                score += idf * tf_norm
                
            # Filename relevance boost
            if token in fn_lower:
                score += 1.2
                
        # Proximity bonus if multiple query terms appear
        if matched_tokens > 1:
            score *= (1.0 + (0.25 * matched_tokens))
            
        if score > 0.05:
            scored.append({
                "chunk_id": c["chunk_id"],
                "document_id": c["document_id"],
                "filename": c["filename"],
                "original_name": c["original_name"],
                "chunk_index": c["chunk_index"],
                "chunk_text": c["chunk_text"],
                "score": round(score, 3)
            })
            
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]

def answer_document_query(query: str):
    """
    High-level document QA handler.
    Retrieves top relevant chunks and returns formatted response citing source documents.
    """
    chunks = retrieve_relevant_chunks(query, top_k=2)
    if not chunks:
        return None
        
    top_chunk = chunks[0]
    filename = top_chunk["filename"]
    chunk_index = top_chunk["chunk_index"]
    relevance = top_chunk["score"]
    
    # Clean excerpt
    excerpt = top_chunk["chunk_text"]
    
    # If second chunk is also relevant and from same doc, or provides extra context, include it
    extra_context = ""
    if len(chunks) > 1 and chunks[1]["score"] > (top_chunk["score"] * 0.65):
        if chunks[1]["filename"] == filename:
            extra_context = f"\n\n*Additional section from {filename} (Chunk #{chunks[1]['chunk_index']}):*\n{chunks[1]['chunk_text']}"
        else:
            extra_context = f"\n\n*Related reference from {chunks[1]['filename']} (Chunk #{chunks[1]['chunk_index']}):*\n{chunks[1]['chunk_text']}"
            
    response = (
        f"**From official college document: `{filename}`** (Section #{chunk_index + 1}):\n\n"
        f"{excerpt}{extra_context}\n\n"
        f"---\n"
        f"**Source Document:** `{filename}` | **Retrieval Confidence:** {relevance:.1f} score\n"
        f"*Engine: Local BM25 Academic Chunk Retrieval Pipeline (Fallback RAG Engine)*"
    )
    
    return {
        "answer": response,
        "source": f"College Document Retrieval ({filename})",
        "chunks": chunks
    }
