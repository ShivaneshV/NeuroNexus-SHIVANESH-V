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

def build_pptx_slides(title_text: str, slides_list: list) -> "io.BytesIO":
    import io
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    
    bg_color = RGBColor(10, 15, 30)         # Dark Navy
    primary_color = RGBColor(139, 92, 246)  # Electric Violet
    text_light = RGBColor(241, 245, 249)    # Light gray/white
    text_muted = RGBColor(148, 163, 184)    # Muted gray
    box_bg = RGBColor(20, 27, 45)           # Lighter box container
    
    blank_layout = prs.slide_layouts[6]
    
    # Title Slide
    slide1 = prs.slides.add_slide(blank_layout)
    slide1.background.fill.solid()
    slide1.background.fill.fore_color.rgb = bg_color
    
    # Title Text
    t_box = slide1.shapes.add_textbox(Inches(1.0), Inches(2.5), Inches(11.333), Inches(2.5))
    tf = t_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.name = 'Arial'
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = text_light
    
    p2 = tf.add_paragraph()
    p2.text = "Presentation generated by PaperPilot AI"
    p2.font.name = 'Arial'
    p2.font.size = Pt(18)
    p2.font.color.rgb = primary_color
    p2.space_before = Pt(12)
    
    # Content Slides
    for slide_data in slides_list:
        slide = prs.slides.add_slide(blank_layout)
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = bg_color
        
        # Slide Header Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.8), Inches(11.7), Inches(0.8))
        ttf = title_box.text_frame
        ttf.word_wrap = True
        tp = ttf.paragraphs[0]
        tp.text = f"Slide {slide_data.get('slide_number', 1)}: {slide_data.get('title', 'Content')}"
        tp.font.name = 'Arial'
        tp.font.size = Pt(28)
        tp.font.bold = True
        tp.font.color.rgb = text_light
        
        # Slide Content Container Box
        box = slide.shapes.add_shape(1, Inches(0.8), Inches(1.8), Inches(11.733), Inches(4.5))
        box.fill.solid()
        box.fill.fore_color.rgb = box_bg
        box.line.color.rgb = RGBColor(30, 41, 59)
        
        btf = box.text_frame
        btf.word_wrap = True
        btf.margin_top = Inches(0.2)
        btf.margin_left = Inches(0.3)
        btf.margin_right = Inches(0.3)
        
        bullet_points = slide_data.get('bullet_points', [])
        for idx, pt in enumerate(bullet_points):
            p_pt = btf.paragraphs[0] if idx == 0 else btf.add_paragraph()
            p_pt.text = f"• {pt}"
            p_pt.font.name = 'Arial'
            p_pt.font.size = Pt(16)
            p_pt.font.color.rgb = text_light
            if idx > 0:
                p_pt.space_before = Pt(14)
                
    output_stream = io.BytesIO()
    prs.save(output_stream)
    output_stream.seek(0)
    return output_stream

class DownloadPresentationRequest(BaseModel):
    file_hash: str
    slides: list

@app.post("/api/download_presentation")
async def download_presentation(payload: DownloadPresentationRequest):
    """
    Generates a dark-themed PPTX slide deck based on generated slides,
    returning it as a file download.
    """
    try:
        title_text = "Research Slide Deck"
        cached_brief = cache.get_cached_brief(payload.file_hash)
        if cached_brief and isinstance(cached_brief, dict):
            title_text = cached_brief.get("title", title_text)
            
        from fastapi.responses import StreamingResponse
        output_stream = build_pptx_slides(title_text, payload.slides)
        
        filename = f"PaperPilot_{payload.file_hash[:8]}_Slides.pptx"
        return StreamingResponse(
            output_stream,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate PowerPoint: {str(e)}")

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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
