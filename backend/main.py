import os
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any

from pdf_parser import extract_pdf_chunks, calculate_file_hash
from vector_db import LocalVectorDB
from cache_manager import CacheManager
from agent import generate_single_pass_brief

app = FastAPI(title="PaperPilot API", version="2.0.0")

# Setup CORS to allow Next.js on port 3000 to query our backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For hackathon/local dev, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize storage directories
PDF_DIR = "./data/pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

# Initialize components
db = LocalVectorDB(persist_dir="./data")
cache = CacheManager(db_dir="./data")

class BriefRequest(BaseModel):
    file_hash: str
    eli5: bool = False

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Accepts PDF file, calculates hash, extracts text, embeds, and stores in Vector DB.
    Checks cache first to bypass duplicate ingestion.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    try:
        contents = await file.read()
        file_hash = calculate_file_hash(contents)
        
        # Save file to disk to serve it to the frontend PDF viewer
        pdf_path = os.path.join(PDF_DIR, f"{file_hash}.pdf")
        if not os.path.exists(pdf_path):
            with open(pdf_path, "wb") as f:
                f.write(contents)
        
        # Check if the brief for this file hash is already cached
        cached_brief = cache.get_cached_brief(file_hash)
        if cached_brief and isinstance(cached_brief, dict):
            print(f"File {file_hash} already analyzed and cached. Bypassing ingestion.")
            return {
                "file_hash": file_hash,
                "cached": True,
                "title": cached_brief.get("title", file.filename),
                "message": "File already analyzed and cached."
            }

        # Otherwise, parse and chunk
        print(f"Extracting chunks from uploaded PDF: {file.filename}")
        chunks = extract_pdf_chunks(pdf_path, file_hash)
        print(f"Extracted {len(chunks)} chunks.")
        
        if not chunks:
            raise HTTPException(status_code=400, detail="Unable to extract text content from the PDF.")
            
        # Add to local vector store (using SentenceTransformer embeddings)
        db.add_chunks(file_hash, chunks)
        
        return {
            "file_hash": file_hash,
            "cached": False,
            "num_chunks": len(chunks),
            "message": "File successfully uploaded, parsed, and embedded locally."
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.post("/api/brief")
async def generate_brief(payload: BriefRequest):
    """
    Retrieves chunks relevant to Methodology, Results, and Limitations,
    calls LLM in single-pass JSON mode, caches response, and updates cost stats.
    """
    file_hash = payload.file_hash
    eli5 = payload.eli5
    cache_key = f"{file_hash}_eli5" if eli5 else file_hash
    
    # 1. Check SQLite cache first for semantic cache hits
    cached_brief = cache.get_cached_brief(cache_key)
    if cached_brief:
        print(f"Cache Hit for key {cache_key}! Returning cached research brief.")
        return {
            "brief": cached_brief,
            "source": "cache",
            "message": "Retrieved from local SQLite cache."
        }
        
    # 2. Cache Miss - Execute local RAG retrieval
    print(f"Cache Miss for key {cache_key}. Performing local semantic search across index...")
    
    # Query 3 key areas of study separately (local computations, 0 API calls)
    q_methodology = db.query(file_hash, "methodology dataset experimental setup model training architecture framework implementation", n_results=3)
    q_results = db.query(file_hash, "results evaluation metrics findings benchmarks comparison accuracy loss graphs tables performance", n_results=3)
    q_limitations = db.query(file_hash, "limitations future work assumptions drawbacks challenges scope issues scope outline", n_results=3)
    
    # Deduplicate retrieved chunks
    seen_ids = set()
    retrieved_chunks = []
    for chunk in (q_methodology + q_results + q_limitations):
        if chunk["chunk_id"] not in seen_ids:
            seen_ids.add(chunk["chunk_id"])
            retrieved_chunks.append(chunk)
            
    if not retrieved_chunks:
        raise HTTPException(status_code=404, detail="No text chunks found for this file hash. Please re-upload.")
        
    print(f"Retrieved {len(retrieved_chunks)} unique context chunks. Sending to single-pass LLM agent (ELI5={eli5})...")
    
    # 3. Call LLM agent (Structured single-pass call)
    try:
        brief_data, tokens, cost = generate_single_pass_brief(retrieved_chunks, eli5=eli5)
        
        # 4. Save to cache
        cache.save_brief_to_cache(cache_key, brief_data)
        
        # 5. Record API call metrics
        cache.record_llm_call(tokens, cost)
        
        return {
            "brief": brief_data,
            "source": "llm",
            "message": "Successfully generated brief with single-pass LLM."
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Brief generation failed: {str(e)}")

@app.get("/api/stats")
async def get_stats():
    """
    Returns system performance and API savings statistics.
    """
    return cache.get_stats()

@app.post("/api/stats/reset")
async def reset_stats():
    """
    Resets all performance statistics.
    """
    cache.reset_stats()
    return {"message": "System stats reset successfully."}

class ChatRequest(BaseModel):
    file_hash: str
    question: str

@app.post("/api/chat")
async def copilot_chat(payload: ChatRequest):
    """
    Retrieves custom question context, queries the active client (Groq/OpenAI),
    caches responses semantic-style, and returns answers with clickable citations.
    """
    file_hash = payload.file_hash
    question = payload.question
    
    if not file_hash or not question:
        raise HTTPException(status_code=400, detail="Missing file_hash or question.")
        
    # 1. Check SQLite copilot cache
    cached_ans = cache.get_cached_copilot(file_hash, question)
    if cached_ans:
        print(f"Copilot Cache Hit for: {question}")
        return {
            "answer_data": cached_ans,
            "source": "cache",
            "message": "Retrieved from local SQLite copilot cache."
        }
        
    # 2. Local RAG Retrieval (0 API call embeddings/search)
    print(f"Copilot Cache Miss. Searching local index for: {question}")
    retrieved = db.query(file_hash, question, n_results=4)
    if not retrieved:
         raise HTTPException(status_code=404, detail="No source context retrieved for this question.")
        
    # 3. Call LLM for single-pass structured JSON
    try:
        from agent import generate_copilot_answer
        answer_data, tokens, cost = generate_copilot_answer(question, retrieved)
        
        # 4. Save to SQLite cache
        cache.save_copilot_to_cache(file_hash, question, answer_data)
        
        # 5. Record API call
        cache.record_llm_call(tokens, cost)
        
        return {
            "answer_data": answer_data,
            "source": "llm",
            "message": "Successfully generated answer with RAG copilot."
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Copilot query failed: {str(e)}")

@app.get("/api/pdfs/{file_hash}")
async def get_pdf(file_hash: str):
    """
    Serves the uploaded PDF file to the frontend PDF viewer.
    """
    pdf_path = os.path.join(PDF_DIR, f"{file_hash}.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found.")
    return FileResponse(pdf_path, media_type="application/pdf")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
