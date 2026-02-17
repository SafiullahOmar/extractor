import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'pdf_store'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres'),
        port=os.getenv('DB_PORT', '5432')
    )

def setup_database():
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pdf_documents (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(255),
            page_number INTEGER,
            content_type VARCHAR(50),
            content TEXT,
            image_path VARCHAR(500),
            table_data JSONB,
            qdrant_id VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    conn.commit()
    conn.close()
    print("Database setup complete")

if __name__ == "__main__":
    setup_database()
