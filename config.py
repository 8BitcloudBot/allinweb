import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = BASE_DIR / "vector_index"

# 本地开发：兼容仓库内 docs/key.md（含 LLM_API_KEY 等），与 trip-planner 一致
_key_file = os.getenv("KEY_FILE", str(BASE_DIR / "docs" / "key.md"))
if Path(_key_file).exists():
    for _line in Path(_key_file).read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and "=" in _line and not _line.startswith("#"):
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

load_dotenv(BASE_DIR / ".env")


class ChefMateConfig:
    data_path: str = str(DATA_DIR)
    index_save_path: str = str(INDEX_DIR)

    # 嵌入模型需与 vector_index/index.faiss 维度一致（512 维）。
    # 原为 bge-base-zh-v1.5（768 维且本地未缓存），导致离线加载失败且维度不匹配。
    embedding_model: str = "BAAI/bge-small-zh-v1.5"

    hf_endpoint: str = os.getenv("HF_ENDPOINT", "")
    hf_token: str = os.getenv("HF_TOKEN", "")

    # 固定使用 DeepSeek 官方有效模型；key.md 的 LLM_MODEL(=deepseek-v4-flash) 仅适用于
    # 特定网关，对 api.deepseek.com 返回空响应，故 V1 不读取 LLM_MODEL。
    llm_model: str = "deepseek-chat"
    # docs/key.md 的 LLM_API_KEY 为本地权威密钥；生产环境若无 key.md 则回退 DEEPSEEK_API_KEY
    llm_api_key: str = os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
    llm_base_url: str = os.getenv("DEEPSEEK_BASE_URL", os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"))
    temperature: float = 0.3
    max_tokens: int = 2048

    top_k: int = 10
    bm25_k: int = 3

    parent_window_size: int = 1


DEFAULT_CONFIG = ChefMateConfig()
