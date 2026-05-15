import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi


class RetrievalOptimizationModule:
    def __init__(self, vectorstore: FAISS, chunks: List[Document]):
        self.vectorstore = vectorstore
        self.chunks = chunks
        self.vector_retriever = None
        self.bm25_retriever = None
        self._bm25_index: Optional[BM25Okapi] = None
        self._bm25_corpus: List[List[str]] = []
        self.setup_retrievers()

    def setup_retrievers(self):
        corpus_texts = [c.page_content for c in self.chunks]
        self._bm25_corpus = [text.split() for text in corpus_texts]
        self._bm25_index = BM25Okapi(self._bm25_corpus)
        self.bm25_retriever = BM25Retriever.from_documents(self.chunks, k=10)
        self.vector_retriever = self.vectorstore.as_retriever(
            search_type="similarity", search_kwargs={"k": 10}
        )

    def hybrid_search(self, query: str, top_k: int = 3, filters: Optional[Dict[str, Any]] = None) -> List[Document]:
        """混合检索，支持可选的元数据筛选。返回 (docs, rrf_scores)"""
        fetch_k = max(top_k * 3, 15)

        vec_retriever = self.vectorstore.as_retriever(
            search_type="similarity", search_kwargs={"k": fetch_k}
        )
        bm25_retriever = BM25Retriever.from_documents(self.chunks, k=fetch_k)

        vector_docs = vec_retriever.invoke(query)
        bm25_docs = bm25_retriever.invoke(query)

        if filters:
            vector_docs_filtered = self._apply_filters(vector_docs, filters)
            bm25_docs_filtered = self._apply_filters(bm25_docs, filters)
            if not vector_docs_filtered and not bm25_docs_filtered:
                if "min_servings" in filters:
                    vector_docs = self._sort_by_servings(vector_docs, reverse=True)[:top_k]
                    bm25_docs = self._sort_by_servings(bm25_docs, reverse=True)[:top_k]
                else:
                    vector_docs = []
                    bm25_docs = []
            else:
                vector_docs = vector_docs_filtered
                bm25_docs = bm25_docs_filtered

        reranked_docs, rrf_scores = self._rrf_rerank(vector_docs, bm25_docs)
        return reranked_docs[:top_k]
    
    def _apply_filters(self, docs: List[Document], filters: Dict[str, Any]) -> List[Document]:
        """应用元数据筛选"""
        filtered = docs
        
        if "min_servings" in filters:
            min_servings = filters["min_servings"]
            filtered = [
                d for d in filtered 
                if d.metadata.get("servings_max", 0) >= min_servings
            ]
        
        if "category" in filters:
            category = filters["category"]
            filtered = [
                d for d in filtered 
                if d.metadata.get("category") == category
            ]
        
        if "difficulty" in filters:
            difficulty = filters["difficulty"]
            filtered = [
                d for d in filtered 
                if d.metadata.get("difficulty") == difficulty
            ]
        
        return filtered
    
    def _sort_by_servings(self, docs: List[Document], reverse: bool = True) -> List[Document]:
        """按份量排序文档"""
        return sorted(
            docs,
            key=lambda d: d.metadata.get("servings_max", 0),
            reverse=reverse
        )

    def get_scores_for_docs(
        self, query: str, docs: List[Document]
    ) -> Dict[int, Tuple[str, float]]:
        score_k = max(len(docs) * 3, 20)
        vec_scored = self.vectorstore.similarity_search_with_relevance_scores(
            query, k=score_k
        )
        vec_score_map = {}
        for doc, score in vec_scored:
            cid = doc.metadata.get("chunk_id", "")
            vec_score_map[cid] = max(0.0, min(1.0, float(score)))

        raw_bm25 = self._bm25_index.get_scores(query.split())
        bm25_scores_norm = self._normalize_scores(raw_bm25)
        bm25_score_map = {}
        for idx in range(len(self.chunks)):
            cid = self.chunks[idx].metadata.get("chunk_id", "")
            bm25_score_map[cid] = float(bm25_scores_norm[idx])

        chunk_scores: Dict[int, Tuple[str, float]] = {}
        for doc in docs:
            cid = doc.metadata.get("chunk_id", str(id(doc)))
            parent_id = doc.metadata.get("parent_id", "")
            vec = vec_score_map.get(cid, 0.0)
            bm25 = bm25_score_map.get(cid, 0.0)
            chunk_scores[id(doc)] = (parent_id, round(vec, 3), round(bm25, 3), round(max(vec, bm25), 3))

        return chunk_scores

    def metadata_filtered_search(
        self,
        query: str,
        filters: Dict[str, Any],
        top_k: int = 5,
    ) -> List[Document]:
        vector_retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": top_k * 3, "filter": filters},
        )
        results = vector_retriever.invoke(query)
        return results[:top_k]

    @staticmethod
    def _normalize_scores(scores: np.ndarray) -> np.ndarray:
        s_min, s_max = scores.min(), scores.max()
        if s_max - s_min < 1e-8:
            return np.zeros_like(scores)
        return (scores - s_min) / (s_max - s_min)

    @staticmethod
    def _rrf_rerank(
        vector_results: List[Document],
        bm25_results: List[Document],
        k: int = 60,
    ) -> tuple[List[Document], dict[int, float]]:
        rrf_scores = {}

        for rank, doc in enumerate(vector_results):
            doc_id = id(doc)
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank + 1)

        for rank, doc in enumerate(bm25_results):
            doc_id = id(doc)
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank + 1)

        all_docs = {id(doc): doc for doc in vector_results + bm25_results}
        sorted_docs = sorted(
            all_docs.items(),
            key=lambda x: rrf_scores.get(x[0], 0),
            reverse=True,
        )
        return [doc for _, doc in sorted_docs], rrf_scores
