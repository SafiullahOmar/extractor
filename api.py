from fastapi import FastAPI, HTTPException, UploadFile, File
from qdrant_setup import get_qdrant_client
from db_setup import get_connection
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from process_pdf import process_pdf
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
    cur.execute("SELECT DISTINCT filename FROM pdf_documents ORDER BY filename")
    files = [row[0] for row in cur.fetchall()]
    conn.close()
    return {"documents": files}

@app.get("/documents/{filename}")
def get_document(filename: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, page_number, content_type, content, image_path, table_data, created_at
        FROM pdf_documents WHERE filename = %s ORDER BY page_number
    """, (filename,))
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        raise HTTPException(status_code=404, detail="Document not found")
    
    result = {
        "filename": filename,
        "pages": []
    }
    
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

@app.post("/upload")
async def upload_and_process(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    file_path = UPLOAD_DIR / file.filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
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
def search_documents(query: str, limit: int = 5):
    query_embedding = model.encode(query).tolist()
    
    results = qdrant.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=limit
    )
    
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
                "score": result.score
            })
    
    conn.close()
    return {"query": query, "results": search_results}
