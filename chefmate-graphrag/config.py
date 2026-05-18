import os
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class GraphRAGConfig:
    neo4j_uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    neo4j_user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", ""))
    neo4j_database: str = field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))

    milvus_host: str = field(default_factory=lambda: os.getenv("MILVUS_HOST", "localhost"))
    milvus_port: int = field(default_factory=lambda: int(os.getenv("MILVUS_PORT", "19530")))
    milvus_collection_name: str = "cooking_knowledge"
    milvus_dimension: int = 512

    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    llm_model: str = "deepseek-chat"
    deepseek_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    deepseek_base_url: str = "https://api.deepseek.com/v1"

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
        if not self.neo4j_password:
            raise ValueError("NEO4J_PASSWORD environment variable is not set")
        if not self.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

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
