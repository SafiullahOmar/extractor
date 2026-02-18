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
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pdf_metadata (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(255) UNIQUE,
            file_size BIGINT,
            total_pages INTEGER,
            file_hash VARCHAR(64),
            upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processing_status VARCHAR(50) DEFAULT 'completed',
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fair_metadata (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(255) UNIQUE,
            doi VARCHAR(255),
            handle VARCHAR(255),
            ark VARCHAR(255),
            title TEXT,
            authors JSONB,
            abstract TEXT,
            keywords TEXT[],
            publication_date DATE,
            journal VARCHAR(255),
            license VARCHAR(100),
            repository_url VARCHAR(500),
            data_availability TEXT,
            methodology TEXT,
            citation_info JSONB,
            pacs_codes TEXT[],
            mesh_terms TEXT[],
            subject_classifications JSONB,
            metadata_schema VARCHAR(100) DEFAULT 'DataCite',
            datacite_schema JSONB,
            provenance_chain JSONB,
            curation_status VARCHAR(50) DEFAULT 'pending',
            quality_score FLOAT,
            validation_status VARCHAR(50),
            enrichment_history JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS provenance (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(255),
            action VARCHAR(100),
            agent VARCHAR(100),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            input_data JSONB,
            output_data JSONB,
            metadata JSONB
        );
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_provenance_filename ON provenance(filename);")
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_filename ON pdf_documents(filename);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_metadata_filename ON pdf_metadata(filename);")
    
    conn.commit()
    conn.close()
    print("Database setup complete")

if __name__ == "__main__":
    setup_database()
