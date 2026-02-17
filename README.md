# PDF Extraction and Vector Store

PDF extraction with Qdrant vector store, Airflow pipeline, and FastAPI.

## Quick Start with Docker

1. Clean Docker (if build fails with I/O error):
```bash
docker system prune -a --volumes
```

2. Build and start all services:
```bash
docker-compose build
docker-compose up -d
```

3. Wait for services to be ready (30-60 seconds)

3. Access services:
   - FastAPI: http://localhost:8000
   - Airflow UI: http://localhost:8085 (admin/admin)
   - Qdrant UI: http://localhost:6333/dashboard

## Usage

### Process PDF via Airflow:
1. Copy PDF file to project directory
2. Open Airflow UI: http://localhost:8085
3. Login: admin/admin
4. Trigger DAG `pdf_extraction` with config:
```json
{"pdf_path": "/app/your_file.pdf"}
```
Note: Use `/app/` prefix for file paths in Docker

### API Endpoints:
- `GET http://localhost:8000/` - API info
- `GET http://localhost:8000/documents` - List all documents
- `GET http://localhost:8000/documents/{filename}` - Get document details
- `GET http://localhost:8000/search?query=your query&limit=5` - Semantic search

### Stop services:
```bash
docker-compose down
```

### View logs:
```bash
docker-compose logs -f app
```

## Production Setup with Nginx

See `nginx-setup.md` for nginx configuration to access APIs via browser on port 80.
