# RAG Deployment Notes

This project integrates RAG in two layers:

1. Preferred: LightRAG Server over REST.
2. Fallback: local lexical retrieval over the current subject's Markdown notes and PDFs.

The fallback is automatic. If `LIGHTRAG_BASE_URL` is empty or the server is unavailable, `/api/rag/ask` still answers from local course files.

## Main App Configuration

Create or edit `agentic-study-system/.env`:

```env
API_PROVIDER=vllm
VLLM_BASE_URL=http://your-llm-host/v1
VLLM_API_KEY=your-key

LIGHTRAG_BASE_URL=http://127.0.0.1:9621
LIGHTRAG_API_KEY=
LIGHTRAG_DEFAULT_MODE=mix
```

If you use official OpenAI or Anthropic, set `API_PROVIDER=openai` or `API_PROVIDER=anthropic` instead.

## LightRAG Server Configuration

The LightRAG repo is expected at:

```text
E:\aistudy\agent\LightRAG
```

Create `E:\aistudy\agent\LightRAG\.env` from `env.example`, then set:

```env
PORT=9621
HOST=127.0.0.1

LLM_BINDING=openai
LLM_BINDING_HOST=http://your-llm-host/v1
LLM_BINDING_API_KEY=your-key
LLM_MODEL=your-chat-model

EMBEDDING_BINDING=openai
EMBEDDING_BINDING_HOST=http://your-embedding-host/v1
EMBEDDING_BINDING_API_KEY=your-key
EMBEDDING_MODEL=your-embedding-model
EMBEDDING_DIM=your-embedding-dimension
```

Important: embedding model and dimension must be fixed before indexing. If you change them, clear the LightRAG workspace and re-index.

## Start Order

1. Start LightRAG Server:

```powershell
cd E:\aistudy\agent\LightRAG
.\.venv\Scripts\lightrag-server.exe --port 9621
```

2. Start the study system:

```powershell
cd E:\aistudy\agent\agentic-study-system
.\.venv\Scripts\python.exe main.py serve --port 8000
```

3. In the study UI:

- Open a week.
- Click `RAG Tutor`.
- Click `Index Selected Week`.
- Ask a grounded course question.

## REST Integration

The main app calls:

- `POST /api/rag/index-week` - uploads current week files to LightRAG when available.
- `POST /api/rag/ask` - calls LightRAG `/query`; falls back locally when unavailable.

The main app does not require LightRAG to be installed in the same Python process.

