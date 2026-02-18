# How to Run the Project

## Prerequisites

1. **Docker & Docker Compose** installed
2. **OpenAI API Key** (for agent workflows - optional but recommended)

## Quick Start (Docker - Recommended)

### Step 1: Set up environment variables (optional)

Create a `.env` file in the project root (optional - defaults are provided):

```bash
# Database
DB_HOST=postgres
DB_NAME=pdf_store
DB_USER=postgres
DB_PASSWORD=postgres
DB_PORT=5432

# Qdrant
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=pdf_documents

# OpenAI (required for agent workflows)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# Airflow
AIRFLOW_HOME=/app/airflow
```

**Note**: If you don't create `.env`, the project will use defaults. However, **you MUST set `OPENAI_API_KEY`** if you want to use the agent workflow (`use_agent=true`).

### Step 2: Build and start services

```bash
# Navigate to project directory
cd "/Volumes/MyDrive/projects/cursor projects"

# Build Docker images (first time or after changes)
docker-compose build

# Start all services in background
docker-compose up -d
```

### Step 3: Wait for services to be ready

Wait 30-60 seconds for all services to start. Check status:

```bash
# Check all containers are running
docker-compose ps

# View logs
docker-compose logs -f app
```

### Step 4: Access services

Once running, access:

- **FastAPI API**: http://localhost:8005
  - API docs: http://localhost:8005/docs
  - Alternative: http://localhost:8005/redoc

- **Airflow UI**: http://localhost:8085
  - Username: `admin`
  - Password: `admin`

- **Qdrant Dashboard**: http://localhost:6333/dashboard

## Usage Examples

### 1. Upload and Process PDF (Standard)

```bash
curl -X POST "http://localhost:8005/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/document.pdf"
```

### 2. Upload with Agent Workflow (FAIR Metadata Extraction)

```bash
curl -X POST "http://localhost:8005/upload?use_agent=true" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/document.pdf"
```

**Note**: Requires `OPENAI_API_KEY` in `.env` or environment.

### 3. List All Documents

```bash
curl http://localhost:8005/documents
```

### 4. Get Document Details

```bash
curl http://localhost:8005/documents/your_file.pdf
```

### 5. Get FAIR Metadata

```bash
curl http://localhost:8005/documents/your_file.pdf/fair
```

### 6. Semantic Search

```bash
# Basic search
curl "http://localhost:8005/search?query=quantum%20mechanics&limit=5"

# Filtered search
curl "http://localhost:8005/search?query=quantum&author=Einstein&journal=Nature&limit=5"
```

### 7. Get Document Chunks

```bash
# All chunks
curl http://localhost:8005/documents/your_file.pdf/chunks

# Only text
curl http://localhost:8005/documents/your_file.pdf/text

# Only tables
curl http://localhost:8005/documents/your_file.pdf/tables

# Only images
curl http://localhost:8005/documents/your_file.pdf/images
```

## Using Airflow UI

1. Open http://localhost:8085
2. Login with `admin` / `admin`
3. Find the `pdf_extraction` DAG
4. Trigger it with config:
   ```json
   {"pdf_path": "/app/uploads/your_file.pdf"}
   ```

**Note**: Files must be in the `uploads/` directory or mounted volume.

## Troubleshooting

### Port Already in Use

If port 8005 or 8085 is already in use:

```bash
# Stop conflicting containers
docker ps | grep -E "8005|8085" | awk '{print $1}' | xargs docker stop

# Or change ports in docker-compose.yml
```

### Services Not Starting

```bash
# Check logs
docker-compose logs app
docker-compose logs airflow-webserver
docker-compose logs postgres

# Restart services
docker-compose restart
```

### Database Connection Issues

```bash
# Check PostgreSQL is healthy
docker-compose ps postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### Clean Start (Remove All Data)

```bash
# Stop and remove containers, volumes
docker-compose down -v

# Rebuild and start
docker-compose build
docker-compose up -d
```

### OpenAI API Key Issues

If agent workflow fails:

1. Check `.env` file has `OPENAI_API_KEY`
2. Verify API key is valid
3. Check API quota/limits

```bash
# Test API key
export OPENAI_API_KEY=your_key
python -c "from langchain_openai import ChatOpenAI; ChatOpenAI(api_key='$OPENAI_API_KEY').invoke('test')"
```

## Stop Services

```bash
# Stop services (keep data)
docker-compose stop

# Stop and remove containers (keep volumes)
docker-compose down

# Stop and remove everything including data
docker-compose down -v
```

## Development Mode (Local - Without Docker)

If you want to run locally without Docker:

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ (running locally)
- Qdrant (running locally or Docker)

### Setup

```bash
# Install dependencies
pip install -r requirements-app.txt

# Set environment variables
export DB_HOST=localhost
export DB_NAME=pdf_store
export DB_USER=postgres
export DB_PASSWORD=postgres
export QDRANT_URL=http://localhost:6333
export OPENAI_API_KEY=your_key

# Setup database
python db_setup.py

# Setup Qdrant
python qdrant_setup.py

# Run API
uvicorn api:app --host 0.0.0.0 --port 8000
```

## Project Structure

```
.
├── api.py                 # FastAPI application
├── process_pdf.py         # PDF processing logic
├── agent_workflow.py      # LangGraph agent workflow
├── react_agents.py        # ReAct agent implementation
├── fair_extractor.py      # FAIR metadata extraction
├── curation_agents.py     # Curation agent functions
├── pdf_extractor.py       # PDF text/table/image extraction
├── db_setup.py            # PostgreSQL schema setup
├── qdrant_setup.py        # Qdrant collection setup
├── docker-compose.yml     # Docker orchestration
├── Dockerfile             # Docker image definition
├── requirements-app.txt  # App dependencies
├── requirements-airflow.txt # Airflow dependencies
├── uploads/               # Uploaded PDFs
├── images/                # Extracted images
└── notebooks/             # Jupyter notebooks
```

## Next Steps

1. **Upload a PDF** via API or Airflow
2. **Check metadata** using `/documents/{filename}/fair`
3. **Search documents** using semantic search
4. **Explore provenance** using `/documents/{filename}/provenance`
5. **Use Jupyter notebooks** for experiments

## Support

For issues:
1. Check logs: `docker-compose logs -f`
2. Verify environment variables
3. Check service health: `docker-compose ps`
4. Review README.md for detailed API documentation
