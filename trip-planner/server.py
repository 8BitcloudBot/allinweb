"""智能旅行助手 — FastAPI 服务（本地开发）。

SSE 端点 /api/chat/stream 与 ChefMate 保持一致的事件格式：
  event: context  -> 增强信息（目的地/POI数量等）
  event: token    -> 行程文本片段（增量）
  event: done     -> 结束
  event: error    -> 错误

本地启动：uvicorn server:app --port 8000 --reload
前端（Astro dev）通过 /api 代理转发到 http://localhost:8000
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent import TripPlannerAgent
from config import DEFAULT_CONFIG as CFG

app = FastAPI(title="TripPlanner API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://vincentbuilds.fun",
        "https://www.vincentbuilds.fun",
        "http://localhost:4321",
        "http://localhost:3000",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class ChatRequest(Request):
    pass


@app.post("/api/chat")
async def chat(req: Request):
    """非流式兜底接口。"""
    body = await req.json()
    query = (body.get("query") or "").strip()
    if not query:
        return {"answer": "请告诉我你的旅行计划，例如：我想去成都玩3天，喜欢美食和自然风光。"}
    agent = TripPlannerAgent()
    chunks = []
    async for item in agent.stream_plan(query):
        if item["type"] == "token":
            chunks.append(item["data"])
    return {"answer": "".join(chunks)}


@app.post("/api/chat/stream")
async def chat_stream(req: Request):
    body = await req.json()
    query = (body.get("query") or "").strip()

    if not query:
        async def empty():
            yield "event: token\ndata: " + json.dumps(
                "请告诉我你的旅行计划，例如：我想去成都玩3天，喜欢美食和自然风光。",
                ensure_ascii=False) + "\n\n"
            yield "event: done\ndata: {}\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    agent = TripPlannerAgent()

    async def event_stream():
        try:
            async for item in agent.stream_plan(query):
                if item["type"] == "context":
                    yield f"event: context\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
                elif item["type"] == "token":
                    yield f"event: token\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
                elif item["type"] == "error":
                    yield f"event: error\ndata: {json.dumps({'error': item['data']})}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "system": "trip-planner",
        "version": "0.1.0",
        "amap": CFG.amap_enabled,
        "tavily": CFG.tavily_enabled,
    }


if __name__ == "__main__":
    import uvicorn
    # 默认 8003，避免与 V1(8000)/V2(8001) 冲突；可用 TRIPPLAN_PORT 覆盖
    port = int(os.getenv("TRIPPLAN_PORT", "8003"))
    uvicorn.run(app, host="0.0.0.0", port=port)
