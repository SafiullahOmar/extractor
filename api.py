from fastapi import FastAPI, HTTPException
from qdrant_setup import get_qdrant_client
from db_setup import get_connection
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()
model = SentenceTransformer('all-MiniLM-L6-v2')
qdrant = get_qdrant_client()
collection_name = os.getenv('QDRANT_COLLECTION', 'pdf_documents')

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
