import logging
import os
from typing import List
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from rank_bm25 import BM25Okapi
import jieba

logger = logging.getLogger(__name__)


class MilvusIndexConstructionModule:
    def __init__(self, host: str = "localhost", port: int = 19530,
                 collection_name: str = "cooking_knowledge",
                 dimension: int = 768,
                 model_name: str = "BAAI/bge-small-zh-v1.5"):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.dimension = dimension
        self.model_name = model_name
        self.embeddings = None
        self.collection = None
        self._milvus_ok = False
        self._connect()
        self._init_embeddings()
        self.chunk_texts: List[str] = []
        self._bm25_corpus: List = []
        self._bm25_index = None

    def _connect(self):
        try:
            connections.connect(host=self.host, port=str(self.port), timeout=5)
            self._milvus_ok = True
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")
        except Exception as e:
            self._milvus_ok = False
            logger.warning(f"Milvus not available: {e}")
            self.collection = None

    def _init_embeddings(self):
        # Prefer local model cache to avoid HF download issues
        local_path = "/app/model_cache/bge-base-zh-v1.5"
        if os.path.isdir(local_path) and os.path.exists(os.path.join(local_path, "config.json")):
            self.embeddings = HuggingFaceEmbeddings(
                model_name=local_path,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info(f"Embeddings model: {local_path} (local cache)")
        else:
            hf_endpoint = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info(f"Embeddings model: {self.model_name} (remote)")

    def has_collection(self) -> bool:
        if not self._milvus_ok:
            return False
        return utility.has_collection(self.collection_name)

    def build_vector_index(self, chunks: List[Document]) -> bool:
        logger.info(f"Building Milvus index from {len(chunks)} chunks...")

        if self.has_collection():
            utility.drop_collection(self.collection_name)

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            FieldSchema(name="recipe_name", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="node_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="parent_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=20),
        ]

        schema = CollectionSchema(fields, "ChefMate cooking knowledge")
        self.collection = Collection(self.collection_name, schema)

        texts = [c.page_content for c in chunks]
        logger.info(f"Computing embeddings for {len(texts)} texts...")
        vectors = self.embeddings.embed_documents(texts)
        self.chunk_texts = texts

        insert_data = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            insert_data.append({
                "chunk_id": chunk.metadata.get("chunk_id", f"chunk_{i}"),
                "text": chunk.page_content[:65535],
                "embedding": vector,
                "recipe_name": chunk.metadata.get("recipe_name", "")[:100],
                "node_id": chunk.metadata.get("node_id", "")[:100],
                "parent_id": chunk.metadata.get("parent_id", "")[:100],
                "category": chunk.metadata.get("category", "")[:50],
                "doc_type": chunk.metadata.get("doc_type", "chunk")[:20],
            })

        self.collection.insert(insert_data)
        self.collection.flush()

        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        self.collection.create_index("embedding", index_params)
        self.collection.load()
        logger.info(f"Milvus index built: {self.collection.num_entities} entities")

        self._bm25_corpus = chunks
        tokenized = [list(jieba.cut(c.page_content)) for c in chunks]
        self._bm25_index = BM25Okapi(tokenized)
        logger.info(f"BM25 index built: {len(chunks)} docs")

        return True

    def load_collection(self) -> bool:
        if not self.has_collection():
            return False
        self.collection = Collection(self.collection_name)
        self.collection.load()
        logger.info(f"Loaded existing Milvus collection: {self.collection.num_entities} entities")
        return True

    def rebuild_bm25_from_chunks(self, chunks: List[Document]):
        """Call after load_collection to rebuild BM25 index from chunk data."""
        if not chunks:
            return
        self._bm25_corpus = chunks
        tokenized = [list(jieba.cut(c.page_content)) for c in chunks]
        self._bm25_index = BM25Okapi(tokenized)
        logger.info(f"BM25 index rebuilt from {len(chunks)} chunks")

    def search(self, query_text: str, top_k: int = 10) -> List[Document]:
        if not self.collection:
            return []
        query_vector = self.embeddings.embed_query(query_text)
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        results = self.collection.search(
            [query_vector], "embedding", search_params,
            limit=top_k,
            output_fields=["text", "chunk_id", "recipe_name", "node_id", "parent_id", "category", "doc_type"],
        )
        docs = []
        for hits in results:
            for hit in hits:
                docs.append(Document(
                    page_content=hit.entity.get("text", ""),
                    metadata={
                        "chunk_id": hit.entity.get("chunk_id", ""),
                        "recipe_name": hit.entity.get("recipe_name", ""),
                        "node_id": hit.entity.get("node_id", ""),
                        "parent_id": hit.entity.get("parent_id", ""),
                        "category": hit.entity.get("category", ""),
                        "doc_type": hit.entity.get("doc_type", ""),
                        "vector_score": hit.score,
                        "search_source": "milvus",
                    }
                ))
        return docs

    def hybrid_search(self, query: str, top_k: int = 10) -> List[Document]:
        vec_docs = self.search(query, top_k)

        if not self._bm25_index:
            return vec_docs

        tokenized_query = list(jieba.cut(query))
        scores = self._bm25_index.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        bm25_docs = []
        for idx in top_indices:
            if scores[idx] > 0:
                doc = self._bm25_corpus[idx]
                bm25_docs.append(Document(
                    page_content=doc.page_content,
                    metadata={**doc.metadata, "bm25_score": float(scores[idx]), "search_source": "bm25"}
                ))

        return self._rrf_merge(vec_docs, bm25_docs, top_k)

    def _rrf_merge(self, vec_docs: List[Document], bm25_docs: List[Document], top_k: int, k: int = 60) -> List[Document]:
        rrf_scores = {}
        doc_map = {}

        for rank, doc in enumerate(vec_docs):
            key = doc.metadata.get("chunk_id") or doc.metadata.get("node_id") or str(hash(doc.page_content[:100]))
            rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (k + rank + 1)
            doc_map[key] = doc

        for rank, doc in enumerate(bm25_docs):
            key = doc.metadata.get("chunk_id") or doc.metadata.get("node_id") or str(hash(doc.page_content[:100]))
            rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (k + rank + 1)
            doc_map[key] = doc

        sorted_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)
        result = []
        for key in sorted_keys[:top_k]:
            doc = doc_map[key]
            doc.metadata["rrf_score"] = rrf_scores[key]
            result.append(doc)
        return result

    def get_collection_stats(self) -> dict:
        if not self.collection:
            return {"row_count": 0}
        return {"row_count": self.collection.num_entities}

    def delete_collection(self) -> bool:
        if self.has_collection():
            utility.drop_collection(self.collection_name)
        return True

    def close(self):
        connections.disconnect("default")
