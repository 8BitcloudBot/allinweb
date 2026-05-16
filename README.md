# AllInWeb

Monorepo combining **ChefMate RAG** (智能食谱问答系统) + **Personal Portfolio** (个人网站) in a single unified project.

**Live**: [vincentbuilds.fun](https://vincentbuilds.fun) · **ChefMate**: [vincentbuilds.fun/chefmate](https://vincentbuilds.fun/chefmate)

---

## Architecture

```
AllInWeb/
├── src/              # Astro frontend (portfolio + chefmate page)
├── chefmate/         # FastAPI backend (RAG system)
│   ├── server.py     # API entry point
│   ├── generator.py  # LLM prompts (DeepSeek V4)
│   ├── retriever.py  # Hybrid search (FAISS + BM25 + RRF)
│   ├── loader.py     # Recipe data loading & chunking
│   ├── indexer.py    # FAISS vector index
│   ├── metrics.py    # RAG quality metrics
│   ├── validator.py  # Answer hallucination detection
│   ├── query_analyzer.py  # Query constraint extraction
│   ├── conversation.py    # Multi-turn context
│   └── security.py   # Rate limiting & validation
├── data/             # 362 Chinese recipes (Markdown)
├── config.py         # Central configuration
├── main.py           # RecipeRAGSystem orchestrator
└── deploy.sh         # One-command deploy to Alibaba Cloud
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Astro v6, Tailwind CSS v4, React |
| Backend | FastAPI (Python 3.12) |
| LLM | DeepSeek V4 (deepseek-chat) |
| Embeddings | BAAI/bge-small-zh-v1.5 (384d) |
| Vector DB | FAISS (IVF + Flat) |
| Keyword Search | BM25 (rank-bm25) |
| Fusion | RRF (Reciprocal Rank Fusion) |
| Deployment | Docker + Nginx + GitHub Actions |
| Package Manager | npm (frontend) + uv (backend) |

## Quick Start

### Prerequisites

- Node.js >= 22
- Python 3.12 (via uv)
- DEEPSEEK_API_KEY in `.env`

```bash
# Clone
git clone git@github.com:8BitcloudBot/allinweb.git
cd allinweb

# Backend
cp .env.example .env   # Add your DEEPSEEK_API_KEY
uv sync
uv run uvicorn chefmate.server:app --host 0.0.0.0 --port 8000

# Frontend (in another terminal)
npm install
npm run dev             # http://localhost:4321
```

### Test API

```bash
curl http://localhost:8000/api/health

curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"宫保鸡丁怎么做"}'
```

## Deployment

### One-command deploy to Alibaba Cloud

```bash
./deploy.sh
```

This syncs frontend + backend to the server, rebuilds Docker, and reloads Nginx.

### Three-way sync (local → GitHub → Alibaba Cloud → local)

```bash
# Push all changes to GitHub
git push origin main

# Then sync from GitHub to Alibaba Cloud (auto via CI)
# Or pull from GitHub to local
git pull origin main
```

### Vector Index Isolation

Each environment maintains its own FAISS index to prevent cross-contamination:

| Environment | Index Path | Build Trigger |
|------------|-----------|---------------|
| Local Dev | `vector_index/` | First `uv run` |
| GitHub CI | `vector_index/` (fresh) | `docker compose build` |
| Alibaba Cloud | `/var/www/vincentbuilds-api/vector_index/` | Docker startup |

**Important**: Never copy `vector_index/` between environments. Each builds independently from the recipe data.

## Project Structure Details

### RAG Pipeline

```
User Query → Query Router (LLM) → Query Rewrite → Hybrid Search
    ├── FAISS (vector similarity)
    └── BM25 (keyword matching)
    └── RRF Fusion
→ Parent Document Retrieval → Context Budgeting → LLM Generation
→ Answer Validation → Metrics Computation
```

### API Endpoints

| Method | Path | Rate Limit |
|--------|------|------------|
| POST | `/api/chat` | 10/min/IP |
| POST | `/api/chat/stream` | SSE streaming |
| GET | `/api/health` | Unlimited |
| GET | `/api/history` | 30/min/IP |
| POST | `/api/feedback` | 20/min/IP |

### Security

- API Key stored server-side only (`.env`, chmod 600)
- Backend port 8000 bound to `127.0.0.1` only
- CORS restricted to `vincentbuilds.fun`
- Rate limiting via slowapi (10 req/min/IP)
- SSL via Nginx + Let's Encrypt
- Query validation via Pydantic

## License

MIT © Vincent Hu
