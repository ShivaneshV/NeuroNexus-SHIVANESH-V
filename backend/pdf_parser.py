import hashlib
import re
from typing import List, Dict, Any
from pypdf import PdfReader

def extract_pdf_chunks(file_path: str, file_hash: str) -> List[Dict[str, Any]]:
    """
    Extracts text from a PDF page by page, splits it into semantic chunks (paragraphs),
    and assigns metadata (chunk_id, page_number) for RAG and citation highlighting.
    """
    reader = PdfReader(file_path)
    chunks = []
    chunk_index = 0

    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        text = page.extract_text()
        
        if not text:
            continue

        # Basic text cleaning: fix ligatures, normalize spaces, etc.
        text = text.replace('\xa0', ' ')
        
        # Split by paragraph-like boundaries (e.g., double newlines or significant line spacing)
        # In academic papers, paragraphs are often separated by double newlines
        paragraphs = re.split(r'\n\s*\n', text)
        
        for para in paragraphs:
            para = para.strip()
            # Clean up linebreaks within paragraph to make it a single continuous text block
            para_cleaned = re.sub(r'\s+', ' ', para)
            
            # Skip very short fragments that are likely headers/footers/page numbers
            if len(para_cleaned) < 60:
                continue

            # If a paragraph is extremely long, split it by sentences into smaller chunks
            if len(para_cleaned) > 1200:
                sentences = re.split(r'(?<=[.!?])\s+', para_cleaned)
                sub_chunk = ""
                for sent in sentences:
                    if len(sub_chunk) + len(sent) < 1000:
                        sub_chunk += " " + sent
                    else:
                        sub_chunk = sub_chunk.strip()
                        if sub_chunk:
                            chunks.append({
                                "chunk_id": f"{file_hash}_p{page_num}_c{chunk_index}",
                                "page_number": page_num,
                                "text": sub_chunk
                            })
                            chunk_index += 1
                        sub_chunk = sent
                sub_chunk = sub_chunk.strip()
                if sub_chunk:
                    chunks.append({
                        "chunk_id": f"{file_hash}_p{page_num}_c{chunk_index}",
                        "page_number": page_num,
                        "text": sub_chunk
                    })
                    chunk_index += 1
            else:
                chunks.append({
                    "chunk_id": f"{file_hash}_p{page_num}_c{chunk_index}",
                    "page_number": page_num,
                    "text": para_cleaned
                })
                chunk_index += 1
                
    return chunks

def calculate_file_hash(file_bytes: bytes) -> str:
    """
    Computes SHA-256 hash of file bytes to uniquely identify the document for caching.
    """
    return hashlib.sha256(file_bytes).hexdigest()
