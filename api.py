from fastapi import FastAPI, HTTPException, UploadFile, File
from qdrant_setup import get_qdrant_client
from db_setup import get_connection
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from process_pdf import process_pdf
from agent_workflow import process_paper
import os
import shutil
from pathlib import Path

load_dotenv()

app = FastAPI()
model = SentenceTransformer('all-MiniLM-L6-v2')
qdrant = get_qdrant_client()
collection_name = os.getenv('QDRANT_COLLECTION', 'pdf_documents')

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/")
def root():
    return {"message": "PDF Document API"}

@app.get("/documents")
def list_documents():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT filename, file_size, total_pages, upload_timestamp, processing_status
        FROM pdf_metadata 
        ORDER BY upload_timestamp DESC
    """)
    rows = cur.fetchall()
    conn.close()
    
    documents = []
    for row in rows:
        documents.append({
            "filename": row[0],
            "file_size": row[1],
            "total_pages": row[2],
            "upload_timestamp": str(row[3]),
            "processing_status": row[4]
        })
    
    return {"documents": documents}

@app.get("/documents/{filename}")
def get_document(filename: str):
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT file_size, total_pages, file_hash, upload_timestamp, processing_status, metadata
        FROM pdf_metadata WHERE filename = %s
    """, (filename,))
    meta_row = cur.fetchone()
    
    cur.execute("""
        SELECT id, page_number, content_type, content, image_path, table_data, created_at
        FROM pdf_documents WHERE filename = %s ORDER BY page_number
    """, (filename,))
    rows = cur.fetchall()
    conn.close()
    
    if not rows and not meta_row:
        raise HTTPException(status_code=404, detail="Document not found")
    
    result = {
        "filename": filename,
        "metadata": {}
    }
    
    if meta_row:
        result["metadata"] = {
            "file_size": meta_row[0],
            "total_pages": meta_row[1],
            "file_hash": meta_row[2],
            "upload_timestamp": str(meta_row[3]),
            "processing_status": meta_row[4],
            "pdf_metadata": meta_row[5]
        }
    
    result["pages"] = []
    for row in rows:
        page_data = {
            "page": row[1],
            "type": row[2],
            "content": row[3],
            "image_path": row[4],
            "table_data": row[5],
            "created_at": str(row[6])
        }
        result["pages"].append(page_data)
    
    return result

@app.get("/documents/{filename}/metadata")
def get_document_metadata(filename: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT file_size, total_pages, file_hash, upload_timestamp, processing_status, metadata, created_at
        FROM pdf_metadata WHERE filename = %s
    """, (filename,))
    row = cur.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Document metadata not found")
    
    cur.execute("""
        SELECT content_type, COUNT(*) 
        FROM pdf_documents 
        WHERE filename = %s 
        GROUP BY content_type
    """, (filename,))
    chunk_stats = {r[0]: r[1] for r in cur.fetchall()}
    conn.close()
    
    return {
        "filename": filename,
        "file_size": row[0],
        "total_pages": row[1],
        "file_hash": row[2],
        "upload_timestamp": str(row[3]),
        "processing_status": row[4],
        "pdf_metadata": row[5],
        "created_at": str(row[6]),
        "chunk_statistics": chunk_stats
    }

@app.post("/upload")
async def upload_and_process(file: UploadFile = File(...), use_agent: bool = False):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    file_path = UPLOAD_DIR / file.filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        if use_agent:
            result = process_paper(str(file_path))
            return {
                "status": "success",
                "filename": file.filename,
                "message": "PDF processed with agent workflow",
                "fair_metadata": result.get("fair_metadata", {})
            }
        else:
            result = process_pdf(str(file_path))
            if "error" in result:
                raise HTTPException(status_code=500, detail=result["error"])
            
            return {
                "status": "success",
                "filename": file.filename,
                "message": f"PDF processed successfully. {result.get('points', 0)} items stored.",
                "details": result
            }
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{filename}/chunks")
def get_document_chunks(filename: str, content_type: str = None):
    conn = get_connection()
    cur = conn.cursor()
    
    if content_type:
        cur.execute("""
            SELECT id, page_number, content_type, content, image_path, table_data, qdrant_id, created_at
            FROM pdf_documents 
            WHERE filename = %s AND content_type = %s 
            ORDER BY page_number, id
        """, (filename, content_type))
    else:
        cur.execute("""
            SELECT id, page_number, content_type, content, image_path, table_data, qdrant_id, created_at
            FROM pdf_documents 
            WHERE filename = %s 
            ORDER BY page_number, id
        """, (filename,))
    
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        raise HTTPException(status_code=404, detail="Document or chunks not found")
    
    chunks = []
    for row in rows:
        chunk = {
            "id": row[0],
            "page": row[1],
            "type": row[2],
            "content": row[3],
            "image_path": row[4],
            "table_data": row[5],
            "qdrant_id": row[6],
            "created_at": str(row[7])
        }
        chunks.append(chunk)
    
    return {
        "filename": filename,
        "content_type_filter": content_type,
        "total_chunks": len(chunks),
        "chunks": chunks
    }

@app.get("/documents/{filename}/text")
def get_document_text(filename: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT page_number, content, created_at
        FROM pdf_documents 
        WHERE filename = %s AND content_type = 'text'
        ORDER BY page_number
    """, (filename,))
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        raise HTTPException(status_code=404, detail="No text content found for this document")
    
    text_chunks = []
    for row in rows:
        text_chunks.append({
            "page": row[0],
            "text": row[1],
            "created_at": str(row[2])
        })
    
    return {
        "filename": filename,
        "total_text_chunks": len(text_chunks),
        "text_chunks": text_chunks
    }

@app.get("/documents/{filename}/images")
def get_document_images(filename: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT page_number, image_path, created_at
        FROM pdf_documents 
        WHERE filename = %s AND content_type = 'image'
        ORDER BY page_number
    """, (filename,))
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        raise HTTPException(status_code=404, detail="No images found for this document")
    
    images = []
    for row in rows:
        images.append({
            "page": row[0],
            "image_path": row[1],
            "created_at": str(row[2])
        })
    
    return {
        "filename": filename,
        "total_images": len(images),
        "images": images
    }

@app.get("/documents/{filename}/tables")
def get_document_tables(filename: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT page_number, table_data, created_at
        FROM pdf_documents 
        WHERE filename = %s AND content_type = 'table'
        ORDER BY page_number
    """, (filename,))
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        raise HTTPException(status_code=404, detail="No tables found for this document")
    
    tables = []
    for row in rows:
        tables.append({
            "page": row[0],
            "table_data": row[1],
            "created_at": str(row[2])
        })
    
    return {
        "filename": filename,
        "total_tables": len(tables),
        "tables": tables
    }

@app.get("/search")
def search_documents(query: str, limit: int = 5, author: str = None, journal: str = None, keyword: str = None):
    from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
    
    query_embedding = model.encode(query).tolist()
    
    filter_conditions = []
    if author:
        filter_conditions.append(FieldCondition(key="authors", match=MatchValue(value=author)))
    if journal:
        filter_conditions.append(FieldCondition(key="journal", match=MatchValue(value=journal)))
    if keyword:
        filter_conditions.append(FieldCondition(key="keywords", match=MatchAny(any=[keyword])))
    
    search_params = {
        "collection_name": collection_name,
        "query_vector": query_embedding,
        "limit": limit
    }
    
    if filter_conditions:
        search_params["query_filter"] = Filter(must=filter_conditions)
    
    results = qdrant.search(**search_params)
    
    conn = get_connection()
    cur = conn.cursor()
    
    search_results = []
    for result in results:
        cur.execute("""
            SELECT filename, page_number, content_type, content, image_path, table_data
            FROM pdf_documents WHERE qdrant_id = %s
        """, (result.id,))
        row = cur.fetchone()
        if row:
            search_results.append({
                "filename": row[0],
                "page": row[1],
                "type": row[2],
                "content": row[3],
                "image_path": row[4],
                "table_data": row[5],
                "score": result.score,
                "metadata": result.payload
            })
    
    conn.close()
    return {"query": query, "filters": {"author": author, "journal": journal, "keyword": keyword}, "results": search_results}

@app.get("/documents/{filename}/fair")
def get_fair_metadata(filename: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT doi, title, authors, abstract, keywords, publication_date,
               journal, license, repository_url, data_availability, methodology,
               citation_info, controlled_vocabularies, metadata_schema
        FROM fair_metadata WHERE filename = %s
    """, (filename,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="FAIR metadata not found")
    
    return {
        "filename": filename,
        "doi": row[0],
        "title": row[1],
        "authors": row[2],
        "abstract": row[3],
        "keywords": row[4],
        "publication_date": str(row[5]) if row[5] else None,
        "journal": row[6],
        "license": row[7],
        "repository_url": row[8],
        "data_availability": row[9],
        "methodology": row[10],
        "citation_info": row[11],
        "controlled_vocabularies": row[12],
        "metadata_schema": row[13]
    }
