import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = BASE_DIR / "vector_index"

load_dotenv(BASE_DIR / ".env")


class ChefMateConfig:
    data_path: str = str(DATA_DIR)
    index_save_path: str = str(INDEX_DIR)

    embedding_model: str = "BAAI/bge-base-zh-v1.5"

    hf_endpoint: str = os.getenv("HF_ENDPOINT", "")
    hf_token: str = os.getenv("HF_TOKEN", "")

    llm_model: str = "deepseek-chat"
    llm_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    llm_base_url: str = "https://api.deepseek.com/v1"
    temperature: float = 0.3
    max_tokens: int = 2048

    top_k: int = 10
    bm25_k: int = 3

    parent_window_size: int = 1


DEFAULT_CONFIG = ChefMateConfig()
