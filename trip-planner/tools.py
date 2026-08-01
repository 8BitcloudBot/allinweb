"""高德地图 REST API 与 Tavily 联网搜索的轻量封装。

所有调用均为可选能力：未配置对应 API key 时，相关方法直接返回空结果，
Agent 会优雅降级为纯 LLM 行程规划，不影响主流程。
"""
from __future__ import annotations

import httpx

from config import DEFAULT_CONFIG as CFG

TIMEOUT = 15.0


async def amap_text_search(keyword: str, city: str | None = None) -> list[dict]:
    """高德 POI 关键字搜索，返回精简 POI 列表。"""
    if not CFG.amap_enabled:
        return []
    params = {
        "key": CFG.amap_api_key,
        "keywords": keyword,
        "offset": 8,
        "extensions": "all",
    }
    if city:
        params["city"] = city
        params["citylimit"] = "true"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{CFG.amap_base_url}/v3/place/text", params=params)
            data = r.json()
        if data.get("status") != "1":
            return []
        pois = []
        for p in data.get("pois", []):
            pois.append({
                "name": p.get("name"),
                "type": p.get("type"),
                "address": p.get("address"),
                "rating": (p.get("biz_ext") or {}).get("rating"),
                "location": p.get("location"),
            })
        return pois
    except Exception as exc:  # noqa: BLE001
        print(f"[amap_text_search] 失败: {exc}")
        return []


async def amap_weather(adcode: str | None = None, city: str | None = None) -> dict | None:
    """高德天气预报（需城市 adcode 或名称）。"""
    if not CFG.amap_enabled:
        return None
    params = {"key": CFG.amap_api_key, "extensions": "all"}
    if adcode:
        params["city"] = adcode
    elif city:
        params["city"] = city
    else:
        return None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{CFG.amap_base_url}/v3/weather/weatherInfo", params=params)
            data = r.json()
        if data.get("status") != "1":
            return None
        return data
    except Exception as exc:  # noqa: BLE001
        print(f"[amap_weather] 失败: {exc}")
        return None


async def tavily_search(query: str, max_results: int = 5) -> list[dict]:
    """Tavily 联网搜索，返回标题/链接/摘要。"""
    if not CFG.tavily_enabled:
        return []
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": CFG.tavily_api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
            )
            data = r.json()
        return data.get("results", [])
    except Exception as exc:  # noqa: BLE001
        print(f"[tavily_search] 失败: {exc}")
        return []
