import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent

# 兼容两种密钥来源：
# 1) 仓库内的 docs/key.md（本地开发默认），通过环境变量 KEY_FILE 指定
# 2) 标准 .env 文件
_key_file = os.getenv("KEY_FILE", str(BASE_DIR.parent / "docs" / "key.md"))
if Path(_key_file).exists():
    # 解析 key.md 中 "KEY=VALUE" 行注入环境
    for _line in Path(_key_file).read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and "=" in _line and not _line.startswith("#"):
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

load_dotenv(BASE_DIR / ".env")


class TripPlannerConfig:
    # LLM (DeepSeek)
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-chat")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    temperature: float = 0.7
    max_tokens: int = 4096

    # 高德地图（POI / 路线 / 天气增强，可选）
    amap_api_key: str = os.getenv("AMAP_API_KEY", "")
    amap_base_url: str = os.getenv("AMAP_BASE_URL", "https://restapi.amap.com")

    # Tavily 联网搜索（可选）
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")

    # 和风天气（可选）
    qweather_api_key: str = os.getenv("QWEATHER_API_KEY", "")
    qweather_api_host: str = os.getenv("QWEATHER_API_HOST", "")

    @property
    def amap_enabled(self) -> bool:
        return bool(self.amap_api_key)

    @property
    def tavily_enabled(self) -> bool:
        return bool(self.tavily_api_key)

    @property
    def qweather_enabled(self) -> bool:
        return bool(self.qweather_api_key) and bool(self.qweather_api_host)


DEFAULT_CONFIG = TripPlannerConfig()
