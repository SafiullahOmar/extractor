from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import os
from dotenv import load_dotenv

load_dotenv()

def get_qdrant_client():
    return QdrantClient(
        url=os.getenv('QDRANT_URL', 'http://localhost:6333'),
        api_key=os.getenv('QDRANT_API_KEY', None)
    )

def setup_qdrant():
    client = get_qdrant_client()
    
    collection_name = os.getenv('QDRANT_COLLECTION', 'pdf_documents')
    
    try:
        client.get_collection(collection_name)
        print(f"Collection {collection_name} already exists")
    except:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        print(f"Collection {collection_name} created")

if __name__ == "__main__":
    setup_qdrant()
