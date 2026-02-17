import os
import json
import uuid
from pdf_extractor import extract_text, extract_tables, extract_images
from db_setup import get_connection
from qdrant_setup import get_qdrant_client
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

def process_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        return {"error": f"PDF not found: {pdf_path}"}
    
    model = SentenceTransformer('all-MiniLM-L6-v2')
    conn = get_connection()
    cur = conn.cursor()
    qdrant = get_qdrant_client()
    collection_name = os.getenv('QDRANT_COLLECTION', 'pdf_documents')
    
    filename = os.path.basename(pdf_path)
    
    texts = extract_text(pdf_path)
    tables = extract_tables(pdf_path)
    images = extract_images(pdf_path)
    
    points = []
    
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
                "filename": filename,
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
                "filename": filename,
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
                "filename": filename,
                "page": item['page'],
                "content_type": "image",
                "image_path": item['path']
            }
        })
    
    if points:
        qdrant.upsert(collection_name=collection_name, points=points)
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "filename": filename, "points": len(points)}
