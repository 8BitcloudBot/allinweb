import os
from pathlib import Path
from typing import List, Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document


class IndexConstructionModule:
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        index_save_path: str = "./vector_index",
        config=None,
    ):
        self.model_name = model_name
        self.index_save_path = index_save_path
        self.embeddings = None
        self.vectorstore = None
        self._apply_hf_env(config)
        self.setup_embeddings()

    def _apply_hf_env(self, config=None):
        if config is None:
            return
        if config.hf_endpoint:
            os.environ.setdefault("HF_ENDPOINT", config.hf_endpoint)
        if config.hf_token:
            os.environ.setdefault("HF_TOKEN", config.hf_token)

    def setup_embeddings(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    def build_vector_index(self, chunks: List[Document]) -> FAISS:
        if not chunks:
            raise ValueError("文档块列表不能为空")

        texts = [chunk.page_content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]

        self.vectorstore = FAISS.from_texts(
            texts=texts, embedding=self.embeddings, metadatas=metadatas
        )
        return self.vectorstore

    def save_index(self):
        if not self.vectorstore:
            raise ValueError("请先构建向量索引")

        Path(self.index_save_path).mkdir(parents=True, exist_ok=True)
        self.vectorstore.save_local(self.index_save_path)

    def load_index(self) -> Optional[FAISS]:
        if not Path(self.index_save_path).exists():
            return None

        self.vectorstore = FAISS.load_local(
            self.index_save_path,
            self.embeddings,
            allow_dangerous_deserialization=True,
        )
        return self.vectorstore

    def index_exists(self) -> bool:
        return (Path(self.index_save_path) / "index.faiss").exists()
