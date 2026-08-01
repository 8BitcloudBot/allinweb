import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 本模块会在 server.py / build_graph.py 调用 load_dotenv() 之前被 import，
# 因此必须自己先加载同目录 .env（NEO4J_PASSWORD 等在此），否则 dataclass
# 字段默认值取不到，导致图检索不可用。
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# 本地开发：兼容仓库内 docs/key.md（含 LLM_API_KEY 等）
_key_file = os.getenv("KEY_FILE", str(Path(__file__).parent.parent / "docs" / "key.md"))
if Path(_key_file).exists():
    for _line in Path(_key_file).read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and "=" in _line and not _line.startswith("#"):
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())


@dataclass
class GraphRAGConfig:
    neo4j_uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    neo4j_user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", ""))
    neo4j_database: str = field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))

    milvus_host: str = field(default_factory=lambda: os.getenv("MILVUS_HOST", "localhost"))
    milvus_port: int = field(default_factory=lambda: int(os.getenv("MILVUS_PORT", "19530")))
    milvus_collection_name: str = "cooking_knowledge"
    # 维度必须与 embedding_model 一致。本地仅缓存了 bge-small-zh-v1.5(512 维)，
    # bge-base-zh-v1.5(768 维) 无法离线加载且当前网络下载不通，故统一降到 512。
    # 若后续能联网拉取 base 模型，可同时改回 768 + bge-base-zh-v1.5。
    milvus_dimension: int = int(os.getenv("MILVUS_DIMENSION", "512"))

    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    )
    llm_model: str = "deepseek-chat"
    # 与 V1 保持一致：docs/key.md 的 LLM_API_KEY 为本地权威密钥，
    # 优先级高于可能残留在 shell 中的过期 DEEPSEEK_API_KEY。
    deepseek_api_key: str = field(
        default_factory=lambda: os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
    )
    deepseek_base_url: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"))
    )

    top_k: int = 10
    temperature: float = 0.3
    max_tokens: int = 2048

    chunk_size: int = 500
    chunk_overlap: int = 50
    max_graph_depth: int = 2

    data_path: str = "../data"

    daily_quota: int = field(default_factory=lambda: int(os.getenv("DAILY_QUOTA", "200")))
    monthly_quota: int = field(default_factory=lambda: int(os.getenv("MONTHLY_QUOTA", "3000")))

    def __post_init__(self):
        # 缺失依赖时不再直接崩溃，改为警告；lifespan 会优雅降级（服务可启动、health 反映状态）
        if not self.neo4j_password:
            logger.warning("NEO4J_PASSWORD 未设置：Neo4j 图检索将不可用（服务仍可启动）")
        if not self.deepseek_api_key:
            logger.warning("DEEPSEEK_API_KEY / LLM_API_KEY 未设置：生成阶段将失败（请配置 docs/key.md）")

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "GraphRAGConfig":
        return cls(**config_dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "neo4j_uri": self.neo4j_uri,
            "milvus_host": self.milvus_host,
            "milvus_port": self.milvus_port,
            "milvus_collection_name": self.milvus_collection_name,
            "milvus_dimension": self.milvus_dimension,
            "embedding_model": self.embedding_model,
            "llm_model": self.llm_model,
            "top_k": self.top_k,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "max_graph_depth": self.max_graph_depth,
        }


DEFAULT_CONFIG = GraphRAGConfig()
