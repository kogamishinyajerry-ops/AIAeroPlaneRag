import os
import sys
import logging
from pathlib import Path

# Add src to Python path so imports work
current_dir = Path(__file__).parent
sys.path.append(str(current_dir / "src"))

from rag.semantic_chunker import StructuralChunker
from rag.vector_engine import VectorStoreEngine
from rag.guardrail import FactCheckingGuardrail
from ingestion.document_parser import HighFidelityParser
from settings import RAW_DATA_DIR, PROCESSED_DATA_DIR, CHROMA_DB_DIR, ensure_data_dirs

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("Demo")

def run_demo():
    print("="*60)
    print(" 🚀 AeroPower-RAG: MVP Demonstration Pipeline")
    print("="*60)
    
    # Paths
    ensure_data_dirs()
    raw_dir = RAW_DATA_DIR
    processed_dir = PROCESSED_DATA_DIR
    
    # 1. Mock Ingestion (Create dummy PDF)
    dummy_pdf = raw_dir / "CCAR-33.pdf"
    if not dummy_pdf.exists():
        dummy_pdf.touch()
        
    print("\n[Step 1] Initializing LlamaParse High-Fidelity Parser...")
    parser = HighFidelityParser(raw_dir=str(raw_dir), processed_dir=str(processed_dir))
    
    print("\n[Step 2] Parsing complex aeronautical document (CCAR-33.pdf)...")
    parsed_docs = parser.parse_document("CCAR-33.pdf")
    
    print("\n[Step 3] Applying structural semantic chunking (Preserving Chapter/Section)...")
    chunker = StructuralChunker(processed_dir=str(processed_dir))
    chunks = chunker.chunk_markdown("CCAR-33.md")
    if chunks:
        print(f" -> Generated {len(chunks)} structural chunks.")
    
    print("\n[Step 4] Initializing ChromaDB Vector Store & Emdedding Model...")
    engine = VectorStoreEngine(db_dir=str(CHROMA_DB_DIR))
    
    print("\n[Step 5] Indexing chunks into DB...")
    engine.index_chunks(chunks)
    
    print("\n[Step 6] Simulating Engineer Query...")
    query = "什么是压气机的喘振裕度要求？"
    print(f" Query: -> '{query}'")
    
    print(" -> Searching Vector Store...")
    retrieved_contexts = engine.search(query, top_k=2)
    
    print("\n[Step 7] Simulating LLM Draft Answer (Mocking generator)...")
    draft_answer = "根据找到的《航空发动机适航规定》，压气机必须设计为能承受工作区域内的应力。其绝对的喘振裕度必须大于 15% 并且最高耐受 650°C。"
    print(f" Draft: -> '{draft_answer}'")
    
    print("\n[Step 8] Triggering Fact-Checking Guardrail Agent...")
    guardrail = FactCheckingGuardrail()
    result = guardrail.verify_response(query, draft_answer, retrieved_contexts)
    
    print("\n" + "="*60)
    print(" 🛡️ Guardrail Final Verdict")
    print("="*60)
    print(f"STATUS    : {result['status']}")
    print(f"REASONING : {result['reasoning']}")
    print(f"FINAL SAFE: {result['safe_answer']}")
    print("="*60)

if __name__ == "__main__":
    run_demo()
