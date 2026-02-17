import os
import json
import uuid
import hashlib
import pdfplumber
from pdf_extractor import extract_text, extract_tables, extract_images
from fair_extractor import extract_fair_metadata, store_fair_metadata
from db_setup import get_connection
from qdrant_setup import get_qdrant_client
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

def get_file_hash(file_path):
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def get_pdf_metadata(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return {
                "total_pages": len(pdf.pages),
                "metadata": pdf.metadata or {}
            }
    except:
        return {"total_pages": 0, "metadata": {}}

def process_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        return {"error": f"PDF not found: {pdf_path}"}
    
    model = SentenceTransformer('all-MiniLM-L6-v2')
    conn = get_connection()
    cur = conn.cursor()
    qdrant = get_qdrant_client()
    collection_name = os.getenv('QDRANT_COLLECTION', 'pdf_documents')
    
    filename = os.path.basename(pdf_path)
    file_size = os.path.getsize(pdf_path)
    file_hash = get_file_hash(pdf_path)
    pdf_info = get_pdf_metadata(pdf_path)
    
    texts = extract_text(pdf_path)
    tables = extract_tables(pdf_path)
    images = extract_images(pdf_path)
    
    total_chunks = len(texts) + len(tables) + len(images)
    
    full_text = "\n\n".join([item['text'] for item in texts])
    fair_data = {}
    if full_text:
        fair_data = extract_fair_metadata(full_text)
        store_fair_metadata(filename, fair_data)
    
    points = []
    
    base_payload = {
        "filename": filename,
        "doi": fair_data.get('doi'),
        "title": fair_data.get('title'),
        "authors": fair_data.get('authors', []),
        "journal": fair_data.get('journal'),
        "publication_date": fair_data.get('publication_date'),
        "keywords": fair_data.get('keywords', [])
    }
    
    for item in texts:
        embedding = model.encode(item['text']).tolist()
        point_id = str(uuid.uuid4())
        
        cur.execute("""
            INSERT INTO pdf_documents (filename, page_number, content_type, content, qdrant_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (filename, item['page'], 'text', item['text'], point_id))
        
        points.append({
            "id": point_id,
            "vector": embedding,
            "payload": {
                **base_payload,
                "page": item['page'],
                "content_type": "text",
                "content": item['text']
            }
        })
    
    for item in tables:
        embedding = model.encode(str(item['table'])).tolist()
        point_id = str(uuid.uuid4())
        
        cur.execute("""
            INSERT INTO pdf_documents (filename, page_number, content_type, table_data, qdrant_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (filename, item['page'], 'table', json.dumps(item['table']), point_id))
        
        points.append({
            "id": point_id,
            "vector": embedding,
            "payload": {
                **base_payload,
                "page": item['page'],
                "content_type": "table",
                "table_data": item['table']
            }
        })
    
    for item in images:
        embedding = model.encode(f"Image from page {item['page']}").tolist()
        point_id = str(uuid.uuid4())
        
        cur.execute("""
            INSERT INTO pdf_documents (filename, page_number, content_type, image_path, qdrant_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (filename, item['page'], 'image', item['path'], point_id))
        
        points.append({
            "id": point_id,
            "vector": embedding,
            "payload": {
                **base_payload,
                "page": item['page'],
                "content_type": "image",
                "image_path": item['path']
            }
        })
    
    if points:
        qdrant.upsert(collection_name=collection_name, points=points)
    
    cur.execute("""
        INSERT INTO pdf_metadata (filename, file_size, total_pages, file_hash, processing_status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (filename) 
        DO UPDATE SET 
            file_size = EXCLUDED.file_size,
            total_pages = EXCLUDED.total_pages,
            file_hash = EXCLUDED.file_hash,
            processing_status = EXCLUDED.processing_status,
            metadata = EXCLUDED.metadata,
            upload_timestamp = CURRENT_TIMESTAMP
    """, (filename, file_size, pdf_info['total_pages'], file_hash, 'completed', json.dumps(pdf_info['metadata'])))
    
    conn.commit()
    conn.close()
    
    return {
        "status": "success", 
        "filename": filename, 
        "points": len(points),
        "metadata": {
            "file_size": file_size,
            "total_pages": pdf_info['total_pages'],
            "file_hash": file_hash,
            "text_chunks": len(texts),
            "table_chunks": len(tables),
            "image_chunks": len(images),
            "total_chunks": total_chunks
        }
    }
