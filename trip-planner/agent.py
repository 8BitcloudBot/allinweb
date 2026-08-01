"""智能旅行助手 Agent。

设计（复用工程现有栈，不依赖 hello-agents / MCP 框架）：
1) 需求解析：从用户输入抽取 目的地 / 天数 / 偏好 / 预算 等结构化字段；
2) 可选增强：有高德 key 时检索 POI，有 Tavily key 时联网搜索攻略/天气；
3) 行程生成：将增强信息交给 DeepSeek，流式输出 Markdown 行程。
"""
from __future__ import annotations

import json
import re

from openai import AsyncOpenAI

from config import DEFAULT_CONFIG as CFG
from tools import amap_text_search, amap_weather, tavily_search

SYSTEM_PROMPT = """你是"智能旅行助手"，一位专业的旅行规划师。
你需要根据用户的需求，生成一份结构清晰、可落地的旅行行程计划（Markdown 格式）。

行程应包含：
- 行程概览（目的地、天数、主题、预算区间）
- 逐日详细安排（上午/下午/晚上，含交通、景点、餐饮建议）
- 实用贴士（交通、住宿区域、必备物品、避坑提示）
- 如信息不足，可基于常识给出合理默认方案，并说明假设。

回答要实用、具体、有当地特色，避免空泛。请使用中文。
"""

PARSE_PROMPT = """请从用户的旅行需求中提取结构化信息，仅返回 JSON：
{
  "destination": "目的地（城市/国家）",
  "days": 整数天数（推断，默认3）,
  "preferences": ["偏好标签，如美食/亲子/自然/历史/购物/夜生活"],
  "budget": "预算描述或空字符串",
  "travelers": "出行人群描述或空字符串",
  "city_for_poi": "用于地图POI检索的城市名（与destination一致或更具体），或空"
}
不要输出多余解释。"""


class TripPlannerAgent:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=CFG.llm_api_key,
            base_url=CFG.llm_base_url,
        )

    async def _parse_need(self, query: str) -> dict:
        try:
            resp = await self.client.chat.completions.create(
                model=CFG.llm_model,
                messages=[
                    {"role": "system", "content": PARSE_PROMPT},
                    {"role": "user", "content": query},
                ],
                temperature=0.2,
                max_tokens=512,
            )
            text = resp.choices[0].message.content or "{}"
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group(0))
        except Exception as exc:  # noqa: BLE001
            print(f"[parse_need] 失败: {exc}")
        return {"destination": query, "days": 3, "preferences": [], "budget": "",
                "travelers": "", "city_for_poi": ""}

    async def gather_context(self, need: dict) -> dict:
        """并行收集增强信息（高德 POI / Tavily 攻略）。"""
        ctx: dict = {"pois": [], "search": [], "weather": None}
        city = need.get("city_for_poi") or need.get("destination", "")

        tasks = []
        if CFG.amap_enabled and city:
            # 按偏好检索 POI
            prefs = need.get("preferences") or ["景点", "美食"]
            kw = "、".join(prefs[:3]) or "景点"
            tasks.append(("pois", amap_text_search(kw, city)))
            tasks.append(("weather", amap_weather(city=city)))
        if CFG.tavily_enabled:
            tasks.append(("search", tavily_search(
                f"{need.get('destination')} 旅行攻略 必去景点 美食推荐", 5)))

        for name, coro in tasks:
            try:
                result = await coro
                ctx[name] = result  # type: ignore[literal-required]
            except Exception:  # noqa: BLE001
                pass
        return ctx

    def _build_user_prompt(self, query: str, need: dict, ctx: dict) -> str:
        parts = [f"用户需求：{query}\n"]
        if need.get("destination"):
            parts.append(f"目的地：{need['destination']}")
        if need.get("days"):
            parts.append(f"天数：{need['days']}")
        if need.get("preferences"):
            parts.append(f"偏好：{', '.join(need['preferences'])}")
        if need.get("budget"):
            parts.append(f"预算：{need['budget']}")
        if need.get("travelers"):
            parts.append(f"人群：{need['travelers']}")

        pois = ctx.get("pois") or []
        if pois:
            parts.append("\n推荐 POI（来自高德地图）：")
            for p in pois[:8]:
                line = f"- {p.get('name')}（{p.get('type')}）"
                if p.get("address"):
                    line += f" 地址：{p['address']}"
                if p.get("rating"):
                    line += f" 评分：{p['rating']}"
                parts.append(line)

        search = ctx.get("search") or []
        if search:
            parts.append("\n联网攻略摘要（来自 Tavily）：")
            for s in search[:5]:
                parts.append(f"- {s.get('title')}：{s.get('content', '')[:160]}")

        parts.append("\n请基于以上信息生成完整行程计划。")
        return "\n".join(parts)

    async def stream_plan(self, query: str):
        """生成行程并以 token 流 yield 文本片段。"""
        need = await self._parse_need(query)
        ctx = await self.gather_context(need)
        user_prompt = self._build_user_prompt(query, need, ctx)

        # 先发送增强信息作为"思考"事件（前端可展示）
        yield {"type": "context", "data": {
            "destination": need.get("destination"),
            "days": need.get("days"),
            "poi_count": len(ctx.get("pois") or []),
            "search_count": len(ctx.get("search") or []),
            "amap": CFG.amap_enabled,
            "tavily": CFG.tavily_enabled,
        }}

        try:
            stream = await self.client.chat.completions.create(
                model=CFG.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=CFG.temperature,
                max_tokens=CFG.max_tokens,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield {"type": "token", "data": delta}
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "data": str(exc)}
