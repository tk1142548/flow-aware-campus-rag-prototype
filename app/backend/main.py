from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


from app.backend.rag_engine import FlowAwareCampusRAG


app = FastAPI(title='Flow-Aware Campus RAG API')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)
engine = FlowAwareCampusRAG()


class QueryRequest(BaseModel):
    query: str
    session_id: str | None = None


@app.get('/')
async def root() -> dict:
    return {'name': 'flow-aware-campus-rag-api', 'status': 'ok'}


@app.get('/api/health')
async def health() -> dict:
    return {
        'status': 'ok',
        'llm_enabled': engine.llm.enabled,
        'llm_blocked_reason': engine.llm.blocked_reason,
    }


@app.post('/api/query')
async def query(payload: QueryRequest) -> dict:
    return engine.run(payload.query, session_id=payload.session_id)
