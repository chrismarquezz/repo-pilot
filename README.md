# RepoPilot

**AI-powered codebase Q&A using RAG**

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)

> 🚀 **Live Demo: [repo-pilot-black.vercel.app](https://repo-pilot-black.vercel.app)**

RepoPilot lets you index any public GitHub repository and ask natural language questions about its code. It uses retrieval-augmented generation (RAG) to find the most relevant code chunks via semantic search, then streams context-grounded answers powered by Claude. Every answer includes source references with expandable code snippets so you can verify the context yourself.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + TypeScript + Tailwind CSS |
| Backend | Python 3.11 / FastAPI |
| Vector DB | ChromaDB (local, file-persisted) |
| Embeddings | OpenAI `text-embedding-3-small` |
| LLM | Anthropic Claude (claude-sonnet-4-20250514) |
| Rate Limiting | SlowAPI (IP-based) |
| Testing | Pytest + GitHub Actions CI |
| Containerization | Docker |
| Deployment | Vercel (frontend) + Render (backend) |

## Architecture

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────┐
│  React Frontend  │────▶│  Python/FastAPI Backend   │────▶│  ChromaDB   │
│  (TypeScript)    │◀────│                          │◀────│ (Vector DB) │
│  Vercel          │     │  /api/upload             │     └─────────────┘
└─────────────────┘     │  /api/query              │
                        │  /api/repos              │     ┌─────────────┐
                        │                          │────▶│ Claude API  │
                        │  Render (Docker)         │◀────│ (Anthropic) │
                        └──────────────────────────┘     └─────────────┘
                                    │
                                    ▼
                        ┌──────────────────────┐
                        │  OpenAI Embeddings   │
                        │  text-embedding-3-sm │
                        └──────────────────────┘
```

## Features

- **Repository indexing** — Paste a GitHub URL to clone, chunk, embed, and store any public repo
- **Semantic code search** — Finds relevant code using vector similarity, not keyword matching
- **Streaming responses** — Answers stream token-by-token with real-time markdown rendering and syntax highlighting
- **Source transparency** — Every answer shows which files and line ranges were used, with expandable code cards
- **Rate limiting** — IP-based limits on expensive endpoints (5 uploads/hr, 30 queries/hr)
- **Responsive UI** — Dark theme with collapsible sidebar for mobile

## How It Works

1. **Upload** — You provide a GitHub URL. The backend clones the repo and walks its file tree, skipping non-code files (images, lock files, `node_modules`, etc.)

2. **Chunk** — Code files are split into semantically meaningful chunks using hybrid file-aware chunking: small files stay whole, large files split at function/class boundaries with ~10-line overlap between chunks

3. **Embed** — Each chunk is embedded using OpenAI's `text-embedding-3-small` model and stored in ChromaDB alongside its metadata (filename, line range, language)

4. **Query** — When you ask a question, the question is embedded with the same model, the top-k most similar chunks are retrieved, and Claude generates a streamed answer grounded in those code snippets

## API Endpoints

### `POST /api/upload`

Index a GitHub repository. Rate limited to 5 requests/hour per IP.

```json
// Request
{ "github_url": "https://github.com/user/repo" }

// Response
{
  "repo_id": "repo-a1b2c3d4",
  "repo_name": "repo",
  "files_processed": 42,
  "chunks_created": 156,
  "status": "indexed"
}
```

### `POST /api/query`

Ask a question about an indexed repo. Rate limited to 30 requests/hour per IP. Returns a Server-Sent Events stream.

```json
// Request
{ "repo_id": "repo-a1b2c3d4", "question": "Where is authentication handled?" }
```

```
// Response (SSE stream)
data: {"type": "sources", "chunks": [{"filename": "src/auth.py", "start_line": 1, "end_line": 45, "content": "...", "score": 0.87}]}
data: {"type": "token", "content": "The"}
data: {"type": "token", "content": " authentication"}
...
data: {"type": "done"}
```

### `GET /api/repos`

List all indexed repositories.

```json
// Response
{
  "repos": [
    { "repo_id": "repo-a1b2c3d4", "name": "repo", "files": 42, "chunks": 156, "indexed_at": "2025-01-15T..." }
  ]
}
```

### `DELETE /api/repos/{repo_id}`

Delete an indexed repository and its vector data.

### `GET /api/health`

Health check. Returns `{"status": "ok"}`.

## Local Development

### Backend

```bash
cd backend

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and add your API keys:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=sk-...
#   CHROMA_PERSIST_DIR=./chroma_data
#   ALLOWED_ORIGINS=http://localhost:5173

# Start the server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
echo "VITE_API_URL=http://localhost:8000" > .env

# Start dev server
npm run dev
```

The frontend runs at `http://localhost:5173` and proxies API calls to the backend at `http://localhost:8000`.

## Testing

Tests run with pytest and use mocked external services (no API keys needed):

```bash
cd backend
pytest -v
```

Tests are also run automatically on push and pull requests to `main` via GitHub Actions. See [`.github/workflows/test.yml`](.github/workflows/test.yml).

## Docker

Build and run the backend container:

```bash
cd backend

# Build
docker build -t repopilot-backend .

# Run
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e OPENAI_API_KEY=sk-... \
  -e CHROMA_PERSIST_DIR=/app/chroma_data \
  -e ALLOWED_ORIGINS=http://localhost:5173 \
  repopilot-backend
```

To persist the vector database across container restarts, mount a volume:

```bash
docker run -p 8000:8000 \
  -v repopilot-data:/app/chroma_data \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e OPENAI_API_KEY=sk-... \
  -e CHROMA_PERSIST_DIR=/app/chroma_data \
  -e ALLOWED_ORIGINS=http://localhost:5173 \
  repopilot-backend
```
