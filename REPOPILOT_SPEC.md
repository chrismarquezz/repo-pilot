# RepoPilot — Project Specification

## Overview
RepoPilot is a RAG-powered codebase Q&A tool. Users upload a GitHub repository (via URL or zip), and the app chunks, embeds, and stores the code in a vector database. Users can then ask natural language questions about the codebase and receive streamed, context-grounded answers powered by Claude.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript + TailwindCSS |
| Backend | Python 3.10+ / FastAPI |
| Vector DB | ChromaDB (local, file-persisted) |
| Embeddings | OpenAI `text-embedding-3-small` |
| LLM | Anthropic Claude API (claude-sonnet-4-20250514) |
| Testing | Pytest + GitHub Actions CI |
| Containerization | Docker (backend) |
| Deployment | Frontend → Vercel, Backend → Render |

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

## Backend Structure

```
repopilot/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, CORS, routes
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── upload.py        # POST /api/upload (GitHub URL or zip)
│   │   │   ├── query.py         # POST /api/query (ask a question)
│   │   │   └── repos.py         # GET /api/repos (list indexed repos)
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── github.py        # Clone/download repo from GitHub URL
│   │   │   ├── chunker.py       # Parse and chunk code files
│   │   │   ├── embedder.py      # Generate embeddings via OpenAI
│   │   │   ├── vectorstore.py   # ChromaDB operations (store, query)
│   │   │   └── llm.py           # Claude API calls with streaming
│   │   └── config.py            # Environment variables, settings
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py          # Pytest fixtures
│   │   ├── test_upload.py
│   │   ├── test_query.py
│   │   ├── test_chunker.py
│   │   └── test_embedder.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   └── pytest.ini
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── RepoUpload.tsx    # Upload form (URL input or zip upload)
│   │   │   ├── ChatInterface.tsx # Chat UI with message history
│   │   │   ├── MessageBubble.tsx # Individual message display
│   │   │   ├── SourceChunks.tsx  # Shows which files were retrieved
│   │   │   └── RepoList.tsx      # Sidebar showing indexed repos
│   │   ├── hooks/
│   │   │   └── useStreamResponse.ts  # Hook for streaming API responses
│   │   ├── services/
│   │   │   └── api.ts            # API client
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
├── .github/
│   └── workflows/
│       └── test.yml              # GitHub Actions: run pytest on push
├── docker-compose.yml            # Optional: for local dev
├── README.md
└── .gitignore
```

## API Endpoints

### POST /api/upload
Accepts a GitHub URL or zip file. Clones/extracts the repo, chunks the code, generates embeddings, and stores in ChromaDB.

**Request:**
```json
{
  "github_url": "https://github.com/user/repo"
}
```
**Response:**
```json
{
  "repo_id": "uuid",
  "repo_name": "repo",
  "files_processed": 42,
  "chunks_created": 156,
  "status": "indexed"
}
```

### POST /api/query
Accepts a question about an indexed repo. Retrieves relevant chunks from ChromaDB, builds a prompt with context, and streams Claude's response.

**Request:**
```json
{
  "repo_id": "uuid",
  "question": "Where is authentication handled?"
}
```
**Response:** Server-Sent Events (SSE) stream
```
data: {"type": "source", "chunks": [{"file": "src/auth.py", "lines": "1-45", "content": "..."}]}
data: {"type": "token", "content": "The"}
data: {"type": "token", "content": " authentication"}
data: {"type": "token", "content": " is"}
...
data: {"type": "done"}
```

### GET /api/repos
Returns list of previously indexed repositories.

**Response:**
```json
{
  "repos": [
    {"repo_id": "uuid", "name": "repo", "files": 42, "chunks": 156, "indexed_at": "..."}
  ]
}
```

## Chunking Strategy

This is the most important engineering decision in the project.

**Approach: Hybrid file-aware chunking**
1. Walk the repo, skip non-code files (.gitignore patterns, node_modules, images, binaries, lock files)
2. For each code file:
   - If file is small (<100 lines): treat entire file as one chunk
   - If file is large: split by top-level functions/classes using basic AST-like parsing (regex for function/class definitions)
   - Fallback: split by logical blocks of ~50-80 lines with overlap
3. Each chunk gets metadata: `{filename, start_line, end_line, language, repo_id}`
4. Chunk overlap: ~10 lines between adjacent chunks to preserve context

**Supported languages:** Python, JavaScript, TypeScript, Java, C++, Go, Rust, and generic fallback for others.

## Prompt Template

```
You are RepoPilot, an AI assistant that answers questions about codebases.
You have been given relevant code snippets from the repository to help answer the user's question.
Always reference specific files and line numbers in your answers.
If the retrieved code doesn't contain enough information to answer the question, say so honestly.

## Retrieved Code Context:
{retrieved_chunks}

## User Question:
{question}
```

## Key Engineering Decisions to Be Prepared to Discuss in Interviews

1. **Why chunk by function/class instead of fixed character count?** Code has semantic boundaries — splitting mid-function loses context. AST-aware chunking preserves meaning.

2. **Why ChromaDB?** Free, local, no account needed, persists to disk, supports metadata filtering. For a project this scale, a managed DB like Pinecone would be overkill.

3. **Why separate embedding model (OpenAI) from LLM (Claude)?** Best-of-breed approach. OpenAI's embedding model is cheaper and purpose-built for embeddings. Claude is better at generation. Real production systems often mix providers.

4. **How do you handle context window limits?** Retrieve top-k chunks (k=5-10), calculate total tokens, truncate or reduce k if approaching Claude's context limit. Prioritize chunks with highest similarity scores.

5. **Why stream responses?** Better UX — user sees tokens appear in real-time instead of waiting for full response. Also reduces perceived latency.

6. **How would you scale this?** Swap ChromaDB for Pinecone/Weaviate, add Redis caching for embeddings, queue long-running indexing jobs with Celery, horizontal scale the FastAPI backend.

## Environment Variables

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
CHROMA_PERSIST_DIR=./chroma_data
ALLOWED_ORIGINS=http://localhost:5173
```
