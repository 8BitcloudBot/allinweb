import hashlib
import os
from datetime import date

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from .persistence import count_calls_today, count_calls_this_month, log_api_call

DAILY_QUOTA = int(os.getenv("DAILY_QUOTA", "200"))
MONTHLY_QUOTA = int(os.getenv("MONTHLY_QUOTA", "3000"))


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if len(set(v)) <= 1 and len(v) >= 3:
            raise ValueError("查询内容无效")
        if "<script" in v.lower() or "<img" in v.lower():
            raise ValueError("非法内容")
        return v.strip()


def check_quota(request: Request):
    today = date.today()
    daily_count = count_calls_today()
    if daily_count >= DAILY_QUOTA:
        log_api_call(
            ip=request.client.host if request.client else "unknown",
            query_hash="",
            route_type="",
            elapsed_ms=0,
            error="DAILY_QUOTA_EXCEEDED",
        )
        raise HTTPException(429, f"今日配额已用完 ({daily_count}/{DAILY_QUOTA})，明天再来吧 👨‍🍳")

    monthly_count = count_calls_this_month()
    if monthly_count >= MONTHLY_QUOTA:
        raise HTTPException(429, f"月配额已用完 ({monthly_count}/{MONTHLY_QUOTA})")

    if monthly_count > MONTHLY_QUOTA * 0.8:
        import logging
        logging.warning(f"月配额已使用 {monthly_count}/{MONTHLY_QUOTA} (80%)")


def query_hash(query: str) -> str:
    return hashlib.md5(query.encode()).hexdigest()
