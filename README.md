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
   - FastAPI: http://localhost:8005
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
- `GET http://localhost:8005/` - API info
- `POST http://localhost:8005/upload?use_agent=true` - Upload and process PDF with agent workflow (extracts FAIR metadata)
- `POST http://localhost:8005/upload` - Upload and process PDF file
- `GET http://localhost:8005/documents` - List all documents with metadata
- `GET http://localhost:8005/documents/{filename}` - Get document details with metadata
- `GET http://localhost:8005/documents/{filename}/metadata` - Get document metadata only
- `GET http://localhost:8005/documents/{filename}/fair` - Get FAIR-compliant metadata (with PIDs, vocabularies, provenance)
- `GET http://localhost:8005/documents/{filename}/provenance` - Get complete provenance chain
- `GET http://localhost:8005/documents/{filename}/chunks` - Get all chunks (optionally filter by `?content_type=text|table|image`)
- `GET http://localhost:8005/documents/{filename}/text` - Get all text chunks
- `GET http://localhost:8005/documents/{filename}/images` - Get all images
- `GET http://localhost:8005/documents/{filename}/tables` - Get all tables
- `GET http://localhost:8005/search?query=your query&limit=5` - Semantic search
- `GET http://localhost:8005/search?query=quantum&author=Einstein&journal=Nature&limit=5` - Filtered semantic search

### Upload PDF Example:
```bash
# Standard upload
curl -X POST "http://localhost:8005/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/file.pdf"

# Upload with agent workflow (FAIR metadata extraction)
curl -X POST "http://localhost:8005/upload?use_agent=true" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/file.pdf"
```

### Agent Workflow:
The multi-agent curation workflow uses LangGraph to:
1. Extract text from PDF
2. Extract FAIR-compliant metadata (full DataCite schema)
3. **Validate** metadata (completeness, correctness)
4. **Enrich** metadata (add missing PACS codes, MeSH terms)
5. **Assess quality** (FAIR compliance scoring)
6. **Resolve conflicts** (if document already exists)
7. Store content in PostgreSQL and Qdrant
8. Store FAIR metadata with provenance tracking

### Enhanced FAIR Compliance:
- **Full DataCite 4.4 schema** support
- **PIDs**: DOI, Handle, ARK identifiers
- **Standardized vocabularies**: PACS codes, MeSH terms
- **Provenance tracking**: Complete chain of curation actions
- **Quality assessment**: FAIR compliance scoring
- **Curation status**: Track validation, enrichment, quality assessment

### Jupyter Notebooks:
Access notebooks in `notebooks/` directory for experiments:
```bash
jupyter notebook notebooks/experiment_template.ipynb
```

### Check Document Content Examples:
```bash
# Get all chunks for a document
curl "http://localhost:8005/documents/your_file.pdf/chunks"

# Get only text chunks
curl "http://localhost:8005/documents/your_file.pdf/text"

# Get only images
curl "http://localhost:8005/documents/your_file.pdf/images"

# Get only tables
curl "http://localhost:8005/documents/your_file.pdf/tables"

# Filter chunks by type
curl "http://localhost:8005/documents/your_file.pdf/chunks?content_type=text"

# Get document metadata
curl "http://localhost:8005/documents/your_file.pdf/metadata"
```

## Metadata Storage

The project stores comprehensive metadata for each document:

### Document-Level Metadata:
- **File size** - Size of the PDF file in bytes
- **Total pages** - Number of pages in the PDF
- **File hash** - SHA-256 hash for duplicate detection
- **Upload timestamp** - When the file was uploaded
- **Processing status** - Status of processing (completed, failed, etc.)
- **PDF metadata** - Original PDF metadata (title, author, creator, etc.)

### Chunk-Level Metadata:
- **Page number** - Which page the chunk is from
- **Content type** - text, table, or image
- **Qdrant ID** - Vector store identifier
- **Created timestamp** - When the chunk was created

All metadata is stored in PostgreSQL and can be queried via the API endpoints.

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
