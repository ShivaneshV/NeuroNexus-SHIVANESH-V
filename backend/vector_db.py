import os
import numpy as np
from typing import List, Dict, Any

# Attempt to import chromadb. If it fails or raises version mismatch, we fall back to SQLite+NumPy.
CHROMA_AVAILABLE = False
try:
    import chromadb
    CHROMA_AVAILABLE = True
except Exception as e:
    print(f"ChromaDB not available or failed to import ({e}). Falling back to NumPy Vector Store.")

from sentence_transformers import SentenceTransformer

class LocalVectorDB:
    def __init__(self, persist_dir: str = "./data"):
        os.makedirs(persist_dir, exist_ok=True)
        self.persist_dir = persist_dir
        
        # Load SentenceTransformer model locally (downloads on first run, cached thereafter)
        print("Loading local SentenceTransformer model (all-MiniLM-L6-v2)...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        print("Model loaded successfully.")
        
        self.chroma_client = None
        self.collection = None
        
        if CHROMA_AVAILABLE:
            try:
                chroma_path = os.path.join(persist_dir, "chroma")
                self.chroma_client = chromadb.PersistentClient(path=chroma_path)
                self.collection = self.chroma_client.get_or_create_collection("paper_chunks")
                print("ChromaDB initialized successfully.")
            except Exception as e:
                print(f"Failed to initialize ChromaDB ({e}). Falling back to NumPy Vector Store.")
                self.chroma_client = None
                self.collection = None
        
        # In-memory index fallback (if Chroma is not used)
        # Structure: { file_hash: [ { "chunk_id", "page_number", "text", "embedding": np.ndarray } ] }
        self.fallback_db = {}
        self.load_fallback_db()

    def load_fallback_db(self):
        """Loads fallback DB from disk if it exists."""
        # For simplicity, we keep it in-memory for the session, but we can write to files if needed.
        pass

    def add_chunks(self, file_hash: str, chunks: List[Dict[str, Any]]):
        """
        Embeds chunks locally and adds them to ChromaDB (or fallback NumPy index).
        """
        if not chunks:
            return
            
        texts = [chunk["text"] for chunk in chunks]
        print(f"Generating embeddings locally for {len(texts)} chunks...")
        embeddings = self.model.encode(texts)
        print("Embeddings generated.")

        if self.collection is not None:
            try:
                ids = [chunk["chunk_id"] for chunk in chunks]
                metadatas = [{"page_number": chunk["page_number"], "file_hash": file_hash} for chunk in chunks]
                # Convert embeddings to list of floats for ChromaDB
                embeddings_list = [emb.tolist() for emb in embeddings]
                
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings_list,
                    metadatas=metadatas,
                    documents=texts
                )
                print(f"Successfully added {len(chunks)} chunks to ChromaDB.")
                return
            except Exception as e:
                print(f"ChromaDB add failed ({e}). Falling back to NumPy store.")

        # NumPy fallback store
        self.fallback_db[file_hash] = []
        for chunk, emb in zip(chunks, embeddings):
            self.fallback_db[file_hash].append({
                "chunk_id": chunk["chunk_id"],
                "page_number": chunk["page_number"],
                "text": chunk["text"],
                "embedding": emb
            })
        print(f"Successfully added {len(chunks)} chunks to NumPy fallback store.")

    def query(self, file_hash: str, query_text: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """
        Queries the vector store for chunks matching the query text.
        """
        query_emb = self.model.encode(query_text)
        
        # Try ChromaDB first
        if self.collection is not None:
            try:
                results = self.collection.query(
                    query_embeddings=[query_emb.tolist()],
                    n_results=n_results,
                    where={"file_hash": file_hash}
                )
                
                retrieved_chunks = []
                if results and results["ids"] and len(results["ids"][0]) > 0:
                    for i in range(len(results["ids"][0])):
                        retrieved_chunks.append({
                            "chunk_id": results["ids"][0][i],
                            "page_number": results["metadatas"][0][i]["page_number"],
                            "text": results["documents"][0][i],
                            "score": results["distances"][0][i] if "distances" in results else 0.0
                        })
                    return retrieved_chunks
            except Exception as e:
                print(f"ChromaDB query failed ({e}). Trying NumPy fallback.")

        # NumPy fallback retrieval
        if file_hash not in self.fallback_db:
            return []
            
        file_chunks = self.fallback_db[file_hash]
        if not file_chunks:
            return []
            
        # Compute cosine similarity
        similarities = []
        for item in file_chunks:
            emb = item["embedding"]
            # Cosine similarity
            sim = np.dot(emb, query_emb) / (np.linalg.norm(emb) * np.linalg.norm(query_emb) + 1e-9)
            similarities.append(sim)
            
        # Get top indices
        top_indices = np.argsort(similarities)[::-1][:n_results]
        
        retrieved_chunks = []
        for idx in top_indices:
            item = file_chunks[idx]
            retrieved_chunks.append({
                "chunk_id": item["chunk_id"],
                "page_number": item["page_number"],
                "text": item["text"],
                "score": float(similarities[idx])
            })
            
        return retrieved_chunks
