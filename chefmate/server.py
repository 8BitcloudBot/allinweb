import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

from config import DEFAULT_CONFIG
from chefmate.security import ChatRequest, check_quota, query_hash
from chefmate.persistence import (
    init_db, save_conversation, get_history, save_feedback, log_api_call,
)
from main import RecipeRAGSystem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chefmate")

system: RecipeRAGSystem | None = None

GREETING_PATTERNS = [
    r"^(你好|您好|hi|hello|hey|嗨|哈[喽罗]).*",
    r"^(谢谢|感谢|多谢|thanks|thank).*",
    r"^(你是谁|你能做什么|你会什么|你是什么|介绍.*自己).*",
    r"^(再见|拜拜|bye|goodbye).*",
    r"^[?!？?！。.]$",
    r"^(有人吗|在吗|在不在).*",
]

GREETING_REPLIES = {
    "greeting": "👨‍🍳 你好！我是 ChefMate，你的智能食谱助手。\n\n你可以这样问我：\n- **宫保鸡丁怎么做** — 获取详细步骤\n- **推荐两个素菜** — 获得菜品推荐\n- **川菜有什么特点** — 了解菜系知识\n\n试试看吧！",
    "thanks": "不客气！有问题随时问我 👨‍🍳",
    "about": "我是 ChefMate 🧑‍🍳，一个基于 RAG 技术的智能食谱问答系统。\n\n我能帮你：\n- 🔍 查找具体菜谱的制作方法\n- 📋 推荐符合你需求的菜品\n- 📖 解答烹饪相关的问题\n\n我的知识来自 360+ 道真实菜谱，使用 DeepSeek V4 和 FAISS 向量检索来找到最合适的答案。",
    "bye": "再见！随时回来做菜 👋",
    "ping": "在的！有什么菜想学吗？👨‍🍳",
}

ROUTE_LABELS = {"list": "列表推荐", "detail": "详细指导", "general": "通用问答"}


def detect_greeting(query: str) -> str | None:
    q = query.strip().lower()
    for pattern in GREETING_PATTERNS:
        if re.match(pattern, q):
            if any(w in q for w in ("谢谢", "感谢", "多谢", "thanks", "thank")):
                return "thanks"
            if any(w in q for w in ("你是谁", "你能做什么", "你会什么", "你是什么", "介绍")):
                return "about"
            if any(w in q for w in ("再见", "拜拜", "bye", "goodbye")):
                return "bye"
            if any(w in q for w in ("在吗", "在不在", "有人吗")):
                return "ping"
            return "greeting"
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global system
    logger.info("正在初始化 ChefMate RAG 系统...")
    t0 = time.time()
    system = RecipeRAGSystem()
    system.initialize_system()
    system.build_knowledge_base()
    init_db()
    logger.info(f"系统就绪，耗时 {time.time() - t0:.1f}s")
    yield


app = FastAPI(title="ChefMate API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://vincentbuilds.fun",
        "https://www.vincentbuilds.fun",
        "http://localhost:4321",
        "http://localhost:3000",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat(body: ChatRequest, request: Request):
    check_quota(request)
    t0 = time.time()

    greeting_type = detect_greeting(body.query)
    if greeting_type:
        answer = GREETING_REPLIES.get(greeting_type, GREETING_REPLIES["greeting"])
        return {
            "conversation_id": str(uuid.uuid4()),
            "answer": answer,
        }

    try:
        result = system.ask_question(body.query, stream=False, with_metrics=True)
        elapsed_ms = (time.time() - t0) * 1000
        metrics = result["metrics"]

        conv_id = str(uuid.uuid4())
        save_conversation(
            conv_id=conv_id,
            query=body.query,
            answer=result["answer"],
            rewritten_query=metrics.query.rewritten,
            route_type=metrics.query.route_type,
            confidence=metrics.confidence,
            sources_json=json.dumps(
                [{"dish_name": s.dish_name, "category": s.category,
                  "difficulty": s.difficulty, "best_score": s.best_score,
                  "vec_score": s.vec_score, "bm25_score": s.bm25_score,
                  "match_count": s.match_count}
                 for s in metrics.sources]
            ),
            retrieval_count=metrics.retrieval_count,
            elapsed_ms=elapsed_ms,
        )

        log_api_call(
            ip=request.client.host if request.client else "unknown",
            query_hash=query_hash(body.query),
            route_type=metrics.query.route_type,
            elapsed_ms=elapsed_ms,
        )

        return {
            "conversation_id": conv_id,
            "answer": result["answer"],
            "metrics": {
                "query": {
                    "original": metrics.query.original,
                    "rewritten": metrics.query.rewritten,
                    "route_type": ROUTE_LABELS.get(metrics.query.route_type, metrics.query.route_type),
                },
                "sources": [
                    {"dish_name": s.dish_name, "category": s.category,
                     "difficulty": s.difficulty, "match_count": s.match_count,
                     "vec_score": s.vec_score, "bm25_score": s.bm25_score,
                     "best_score": s.best_score, "content_preview": s.content_preview}
                    for s in metrics.sources
                ],
                "confidence": metrics.confidence,
                "retrieval_count": metrics.retrieval_count,
                "elapsed_ms": metrics.elapsed_ms,
            },
        }
    except Exception as e:
        logger.exception("问答失败")
        raise HTTPException(500, str(e))


@app.post("/api/chat/stream")
async def chat_stream(body: ChatRequest, request: Request):
    check_quota(request)
    t0 = time.time()

    async def event_stream():
        try:
            result = system.ask_question(body.query, stream=True, with_metrics=True)
            stream_gen = result["stream"] if isinstance(result, dict) else result
            metrics = result.get("metrics") if isinstance(result, dict) else None

            for token in stream_gen:
                yield f"event: token\ndata: {json.dumps(token, ensure_ascii=False)}\n\n"

            if metrics:
                yield f"event: metrics\ndata: {json.dumps({
                    'confidence': metrics.confidence,
                    'sources': [
                        {'dish_name': s.dish_name, 'category': s.category,
                         'best_score': s.best_score}
                        for s in metrics.sources
                    ],
                    'elapsed_ms': metrics.elapsed_ms,
                }, ensure_ascii=False)}\n\n"

            yield "event: done\ndata: {}\n\n"

        except Exception as e:
            logger.exception("流式问答失败")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/history")
async def history(request: Request):
    check_quota(request)
    return get_history()


@app.post("/api/feedback")
async def feedback(body: dict, request: Request):
    conv_id = body.get("conversation_id", "")
    fb = body.get("feedback", 0)
    if not conv_id or fb not in (-1, 0, 1):
        raise HTTPException(400, "参数无效")
    ok = save_feedback(conv_id, fb)
    if not ok:
        raise HTTPException(404, "对话不存在")
    return {"ok": True}


@app.get("/api/health")
async def health():
    return {"status": "ok", "system": "chefmate", "version": "0.1.0"}
