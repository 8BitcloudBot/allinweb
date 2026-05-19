import os
import time
import json
import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import DEFAULT_CONFIG
from graph.data_preparation import GraphDataPreparationModule
from retrieval.hybrid import MilvusIndexConstructionModule
from retrieval.graph_rag import GraphRAGRetrieval
from retrieval.query_router import IntelligentQueryRouter
from generation.generator import GenerationIntegrationModule
from generation.context_budget import ContextBudgetManager
from shared.validator import AnswerValidator
from shared.conversation import ConversationManager
from shared.metrics import MetricsResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    stream: bool = False


system = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = DEFAULT_CONFIG
    logger.info("Initializing ChefMate GraphRAG system...")

    errors = {}

    data_module = None
    try:
        data_module = GraphDataPreparationModule(
            config.neo4j_uri, config.neo4j_user,
            config.neo4j_password, config.neo4j_database,
        )
        data_module.load_graph_data()
        data_module.build_recipe_documents()
        chunks = data_module.chunk_documents(config.chunk_size, config.chunk_overlap)
        logger.info(f"Data module ready: {len(chunks)} chunks")
    except Exception as e:
        errors["neo4j_data"] = str(e)
        logger.error(f"Neo4j data init failed: {e}")

    index_module = None
    try:
        index_module = MilvusIndexConstructionModule(
            host=config.milvus_host, port=config.milvus_port,
            collection_name=config.milvus_collection_name,
            dimension=config.milvus_dimension,
            model_name=config.embedding_model,
        )
        if index_module.has_collection():
            logger.info("Loading existing Milvus index...")
            index_module.load_collection()
            # Rebuild BM25 from Neo4j data (not stored in Milvus)
            if data_module and data_module.chunks:
                index_module.rebuild_bm25_from_chunks(data_module.chunks)
        elif data_module and data_module.chunks:
            logger.info("Building new Milvus index...")
            index_module.build_vector_index(data_module.chunks)
    except Exception as e:
        errors["milvus"] = str(e)
        logger.error(f"Milvus init failed: {e}")

    generation_module = GenerationIntegrationModule(config)

    graph_rag_retrieval = None
    try:
        graph_rag_retrieval = GraphRAGRetrieval(config, generation_module.client)
        graph_rag_retrieval.initialize()
    except Exception as e:
        errors["graph_rag"] = str(e)
        logger.error(f"GraphRAG init failed: {e}")

    query_router = IntelligentQueryRouter(
        index_module, graph_rag_retrieval,
        generation_module.client, config,
    )

    validator = AnswerValidator()
    if data_module:
        validator.load_valid_dishes(data_module.get_valid_dish_names())

    conversation = ConversationManager(max_history=5)
    context_budget = ContextBudgetManager(max_tokens=10000)

    system["config"] = config
    system["data_module"] = data_module
    system["index_module"] = index_module
    system["generation"] = generation_module
    system["graph_rag"] = graph_rag_retrieval
    system["query_router"] = query_router
    system["validator"] = validator
    system["conversation"] = conversation
    system["context_budget"] = context_budget
    system["errors"] = errors

    yield

    for mod in [data_module, graph_rag_retrieval, index_module]:
        if mod:
            try:
                mod.close()
            except Exception:
                pass


app = FastAPI(title="ChefMate GraphRAG", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://vincentbuilds.fun", "http://localhost:4321", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/graphchat")
async def graph_chat(req: ChatRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(400, "Empty query")

    # Greeting detection
    greeting_patterns = [r'^(你好|hi|hello|嗨|在吗|谢谢|多谢|再见|早上好|晚上好)[！!。.]?$']
    for p in greeting_patterns:
        if __import__('re').match(p, query, __import__('re').IGNORECASE):
            return {
                "answer": '你好！我是 **ChefMate GraphRAG**，基于知识图谱的智能烹饪助手。\n\n我可以帮你：\n- 查找菜谱做法（「宫保鸡丁怎么做」）\n- 发现食材搭配（「鸡肉配什么蔬菜」）\n- 寻找相似菜品（「有没有红烧肉的类似菜」）\n- 多条件查询（「哪些菜用了土豆又用了猪肉」）',
                "routing_info": {"strategy": "greeting", "query_complexity": 0, "relationship_intensity": 0, "confidence": 1, "reasoning": "greeting"},
                "metrics": {"latency_seconds": 0, "retrieval_count": 0, "confidence_score": 1, "route_strategy": "greeting", "source_breakdown": {}},
                "graph_metrics": {"node_count": 0, "relationship_count": 0, "traversal_depth": 0, "search_source": "greeting"},
            }

    conversation = system.get("conversation")
    resolved = conversation.resolve_references(query) if conversation else None

    router = system.get("query_router")
    if not router:
        raise HTTPException(503, "Query router not available")

    start_time = time.time()

    actual_query = resolved.query if resolved else query
    dialogue_context = resolved.context if resolved else ""
    if dialogue_context:
        actual_query = f"{actual_query}\n\n[对话上下文]\n{dialogue_context}"
    docs, analysis = router.route_query(actual_query)

    # HyDE fallback: when all strategies return empty, use hypothetical document embedding
    if not docs and system.get("index_module"):
        logger.info("All strategies returned empty, trying HyDE...")
        hypothetical = system["generation"].generate_hypothetical_recipe(actual_query)
        if hypothetical:
            hyde_docs = system["index_module"].hybrid_search(hypothetical, top_k=10)
            if hyde_docs:
                docs = hyde_docs
                logger.info(f"HyDE recovered {len(docs)} documents")

    compressed = system["context_budget"].compress_context(docs)
    answer = system["generation"].generate_adaptive_answer(actual_query, compressed)

    validator = system.get("validator")
    if validator and answer:
        evidence_names = [d.metadata.get("recipe_name", "") for d in compressed]
        evidence_names = [n for n in evidence_names if n]
        validation = validator.validate_answer(answer, evidence_names)
        if not validation.is_valid and validation.hallucinated_dishes:
            answer += f"\n\n> ⚠️ 以下菜名在菜谱库中未找到：{', '.join(validation.hallucinated_dishes[:5])}"

    metrics = MetricsResult.compute(docs, analysis, start_time)

    if conversation:
        conversation.add_turn("user", query)
        conversation.add_turn("assistant", answer)
        if docs:
            # Extract dish names from docs metadata
            dishes = [d.metadata.get("recipe_name", "") for d in docs if d.metadata.get("recipe_name")]
            # Also extract from answer text if docs have no recipe_name
            if not dishes and validator:
                mentioned = validator._extract_dish_names(answer)
                dishes = mentioned[:5]
            if dishes:
                conversation.set_recommended(dishes)

    return {
        "answer": answer,
        "routing_info": {
            "strategy": analysis.recommended_strategy.value if analysis else "",
            "query_complexity": analysis.query_complexity if analysis else 0,
            "relationship_intensity": analysis.relationship_intensity if analysis else 0,
            "confidence": analysis.confidence if analysis else 0,
            "reasoning": analysis.reasoning if analysis else "",
        },
        "metrics": {
            "latency_seconds": round(metrics.latency_seconds, 3),
            "retrieval_count": metrics.retrieval_count,
            "confidence_score": round(metrics.confidence_score, 3),
            "route_strategy": metrics.route_strategy,
            "source_breakdown": metrics.source_breakdown,
        },
        "graph_metrics": metrics.graph_metrics,
    }


@app.post("/api/graphchat/stream")
async def graph_chat_stream(req: ChatRequest):
    query = req.query.strip()
    if not query:
        return StreamingResponse(
            _emit_error("Empty query"),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        _stream_answer(query),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_answer(query: str) -> AsyncGenerator[str, None]:
    try:
        conversation = system.get("conversation")
        resolved = conversation.resolve_references(query) if conversation else None
        actual_query = resolved.query if resolved else query
        dialogue_context = resolved.context if resolved else ""
        if dialogue_context:
            actual_query = f"{actual_query}\n\n[对话上下文]\n{dialogue_context}"

        yield f"event: routing\ndata: {json.dumps({'query': actual_query}, ensure_ascii=False)}\n\n"

        router = system.get("query_router")
        if not router:
            yield f"event: error\ndata: {json.dumps({'error': 'router unavailable'}, ensure_ascii=False)}\n\n"
            return

        start_time = time.time()
        docs, analysis = router.route_query(actual_query)

        # HyDE fallback in streaming
        if not docs and system.get("index_module"):
            hypothetical = system["generation"].generate_hypothetical_recipe(actual_query)
            if hypothetical:
                docs = system["index_module"].hybrid_search(hypothetical, top_k=10)
                if docs:
                    yield f"event: hyde\ndata: {json.dumps({'recovered': len(docs)}, ensure_ascii=False)}\n\n"

        compressed = system["context_budget"].compress_context(docs)

        yield f"event: routing_decision\ndata: {json.dumps({'strategy': analysis.recommended_strategy.value if analysis else '', 'complexity': analysis.query_complexity if analysis else 0, 'confidence': analysis.confidence if analysis else 0}, ensure_ascii=False)}\n\n"

        answer_parts = []
        gen = system["generation"].generate_stream(actual_query, compressed)
        for chunk_text in gen:
            answer_parts.append(chunk_text)
            yield f"event: token\ndata: {json.dumps({'text': chunk_text}, ensure_ascii=False)}\n\n"

        full_answer = "".join(answer_parts)

        validator = system.get("validator")
        if validator and full_answer:
            evidence_names = [d.metadata.get("recipe_name", "") for d in compressed]
            evidence_names = [n for n in evidence_names if n]
            validation = validator.validate_answer(full_answer, evidence_names)
            if not validation.is_valid and validation.hallucinated_dishes:
                warning = f"\n\n> ⚠️ 以下菜名在菜谱库中未找到：{', '.join(validation.hallucinated_dishes[:5])}"
                yield f"event: token\ndata: {json.dumps({'text': warning}, ensure_ascii=False)}\n\n"

        metrics = MetricsResult.compute(docs, analysis, start_time)
        yield f"event: metrics\ndata: {json.dumps({'latency_seconds': round(metrics.latency_seconds, 3), 'retrieval_count': metrics.retrieval_count, 'confidence_score': round(metrics.confidence_score, 3), 'route_strategy': metrics.route_strategy, 'source_breakdown': metrics.source_breakdown}, ensure_ascii=False)}\n\n"
        yield f"event: graph_metrics\ndata: {json.dumps(metrics.graph_metrics, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json.dumps({})}\n\n"

        if conversation:
            conversation.add_turn("user", query)
            conversation.add_turn("assistant", "stream")
            if docs:
                dishes = [d.metadata.get("recipe_name", "") for d in docs if d.metadata.get("recipe_name")]
                if not dishes and validator:
                    mentioned = validator._extract_dish_names(full_answer)
                    dishes = mentioned[:5]
                if dishes:
                    conversation.set_recommended(dishes)

    except Exception as e:
        logger.error(f"Stream error: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"


async def _emit_error(msg: str) -> AsyncGenerator[str, None]:
    yield f"event: error\ndata: {json.dumps({'error': msg}, ensure_ascii=False)}\n\n"


@app.get("/api/graphrag/stats")
async def graphrag_stats():
    data = system.get("data_module")
    router = system.get("query_router")
    index = system.get("index_module")

    return {
        "graph": data.get_statistics() if data else {},
        "routing": router.get_route_statistics() if router else {},
        "milvus": index.get_collection_stats() if index else {},
        "errors": system.get("errors", {}),
    }


@app.get("/api/graphrag/health")
async def health():
    return {"status": "ok", "errors": system.get("errors", {})}
