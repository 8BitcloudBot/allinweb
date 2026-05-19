import json
import logging
import re
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class SearchStrategy(str, Enum):
    HYBRID = "hybrid_traditional"
    GRAPH_RAG = "graph_rag"
    COMBINED = "combined"


@dataclass
class QueryAnalysis:
    query_complexity: float
    relationship_intensity: float
    reasoning_required: bool
    entity_count: int
    recommended_strategy: SearchStrategy
    confidence: float
    reasoning: str


_FAST_ROUTE_RULES = [
    (SearchStrategy.COMBINED, [
        r"用了.*又用了|同时.*含有|既.*又",
        r"哪些.*用了.*又用了|哪些.*同时.*含有",
    ]),
    (SearchStrategy.GRAPH_RAG, [
        r"搭配|配什么|组合|相配",
        r"替代|替换|代替",
        r"区别|对比|比较|营养",
        r"还需要什么|需要哪些\b|用了什么|用什么|用.*做的菜|用.*做.*哪些|什么.*用了|哪些.*用了",
        r"类似|相似|差不多|同类型的",
        r"关系|关联|联系|相关",
    ]),
    (SearchStrategy.HYBRID, [
        r"怎么做|做法|步骤|怎么",
        r"^推荐|推荐几个|推荐一些",
        r"有什么|有哪些\b",
        r"是什么|什么是|什么意思",
    ]),
]


class IntelligentQueryRouter:
    def __init__(self, traditional_retrieval, graph_rag_retrieval, llm_client, config):
        self.traditional = traditional_retrieval
        self.graph_rag = graph_rag_retrieval
        self.llm_client = llm_client
        self.config = config
        self.route_stats = {
            "hybrid_count": 0, "graph_rag_count": 0,
            "combined_count": 0, "total_queries": 0,
        }

    def fast_route(self, query: str) -> Optional[SearchStrategy]:
        # Strip conversation context before matching
        clean = re.sub(r'\n*\[对话上下文\].*$', '', query, flags=re.DOTALL).strip()
        for strategy, patterns in _FAST_ROUTE_RULES:
            for pattern in patterns:
                if re.search(pattern, clean):
                    return strategy

        # Follow-up detection: short queries ending with 呢/吗 that likely
        # reference a previous topic (e.g. "鸡肉和鱼肉呢？")
        if len(clean) <= 15 and re.search(r'[呢吗？?]$', clean):
            # Short follow-up — let LLM decide with context
            return None

        return None  # None = need LLM analysis, not default to HYBRID

    def analyze_query(self, query: str) -> QueryAnalysis:
        fast = self.fast_route(query)
        if fast is not None:
            return QueryAnalysis(
                query_complexity=0.5, relationship_intensity=0.5 if fast != SearchStrategy.HYBRID else 0.2,
                reasoning_required=fast != SearchStrategy.HYBRID, entity_count=2,
                recommended_strategy=fast, confidence=0.7,
                reasoning="rule-based fast route",
            )

        # Extract conversation context if present
        ctx_match = re.search(r'\[对话上下文\]\s*(.*?)$', query, re.DOTALL)
        context_section = ""
        clean_query = query
        if ctx_match:
            context_section = ctx_match.group(1).strip()
            clean_query = query[:ctx_match.start()].strip()

        prompt = f"""分析这个烹饪查询，确定最佳检索策略。

当前查询: {clean_query}
{f'对话上下文:\n{context_section}' if context_section else ''}

判断维度:
1. query_complexity (0-1): 简单查找=0.1, 中等关系=0.5, 复杂推理=0.9
2. relationship_intensity (0-1): 单一实体=0.1, 实体关系=0.5, 复杂网络=0.9
3. reasoning_required: 是否需要多跳推理
4. entity_count: 涉及的实体数量

策略选择:
- hybrid_traditional: 简单菜谱查找、推荐列表、步骤查询
- graph_rag: 食材搭配、替代关系、相似菜品、营养对比
- combined: 需要同时使用两种方式的复杂查询

特别注意:
- 如果当前查询很短且以"呢？""吗？"结尾，它很可能是对上一轮对话的追问
- 参考对话上下文判断追问的意图，例如上下文讨论"营养区别"，当前查询"鸡肉和鱼肉呢？"就是在问这两种肉的营养区别
- 追问应该沿用上一轮的策略（如上一轮用了 graph_rag，追问也应用 graph_rag）

返回纯JSON:
{{"query_complexity":0.5,"relationship_intensity":0.5,"reasoning_required":false,"entity_count":1,"recommended_strategy":"hybrid_traditional","confidence":0.8,"reasoning":"简要原因"}}"""
        try:
            response = self.llm_client.chat.completions.create(
                model=self.config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=600,
            )
            text = response.choices[0].message.content.strip()
            text = text[text.find("{"):text.rfind("}") + 1]
            result = json.loads(text)
            return QueryAnalysis(
                query_complexity=result.get("query_complexity", 0.5),
                relationship_intensity=result.get("relationship_intensity", 0.5),
                reasoning_required=result.get("reasoning_required", False),
                entity_count=result.get("entity_count", 1),
                recommended_strategy=SearchStrategy(result.get("recommended_strategy", "hybrid_traditional")),
                confidence=result.get("confidence", 0.5),
                reasoning=result.get("reasoning", ""),
            )
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return QueryAnalysis(
                query_complexity=0.3, relationship_intensity=0.2,
                reasoning_required=False, entity_count=1,
                recommended_strategy=SearchStrategy.HYBRID, confidence=0.5, reasoning="fallback",
            )

    def route_query(self, query: str, top_k: int = 10) -> Tuple[List[Document], QueryAnalysis]:
        analysis = self.analyze_query(query)
        self._update_stats(analysis.recommended_strategy)
        logger.info(f"Routing: {analysis.recommended_strategy.value} (complexity={analysis.query_complexity:.2f})")

        hybrid_ok = self.traditional and getattr(self.traditional, '_milvus_ok', False)

        docs = []
        try:
            if analysis.recommended_strategy == SearchStrategy.HYBRID:
                docs = self.traditional.hybrid_search(query, top_k) if hybrid_ok else []
            elif analysis.recommended_strategy == SearchStrategy.GRAPH_RAG:
                docs = self.graph_rag.graph_rag_search(query, top_k)
                if not docs and hybrid_ok:
                    logger.info("GraphRAG returned empty, falling back to hybrid")
                    docs = self.traditional.hybrid_search(query, top_k)
            else:
                docs = self._combined_search(query, top_k)
                if not docs and hybrid_ok:
                    docs = self.traditional.hybrid_search(query, top_k)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            docs = []

        for doc in docs:
            doc.metadata["route_strategy"] = analysis.recommended_strategy.value
            doc.metadata["query_complexity"] = analysis.query_complexity
            doc.metadata["route_confidence"] = analysis.confidence

        return docs, analysis

    def _combined_search(self, query: str, top_k: int) -> List[Document]:
        trad_docs = self.traditional.hybrid_search(query, top_k) if self.traditional else []
        graph_docs = self.graph_rag.graph_rag_search(query, top_k) if self.graph_rag else []

        rrf_scores = {}
        doc_map = {}
        K = 60

        for rank, doc in enumerate(trad_docs):
            key = doc.metadata.get("chunk_id") or doc.metadata.get("node_id") or str(hash(doc.page_content[:100]))
            rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (K + rank + 1)
            doc_map[key] = doc

        for rank, doc in enumerate(graph_docs):
            key = doc.metadata.get("chunk_id") or doc.metadata.get("node_id") or str(hash(doc.page_content[:100]))
            rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (K + rank + 1)
            doc_map[key] = doc

        sorted_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)
        result = []
        for key in sorted_keys[:top_k]:
            doc = doc_map[key]
            doc.metadata["rrf_score"] = rrf_scores[key]
            result.append(doc)
        return result

    def _update_stats(self, strategy: SearchStrategy):
        self.route_stats["total_queries"] += 1
        if strategy == SearchStrategy.HYBRID:
            self.route_stats["hybrid_count"] += 1
        elif strategy == SearchStrategy.GRAPH_RAG:
            self.route_stats["graph_rag_count"] += 1
        else:
            self.route_stats["combined_count"] += 1

    def get_route_statistics(self) -> dict:
        total = self.route_stats["total_queries"]
        if total == 0:
            return self.route_stats
        return {
            **self.route_stats,
            "hybrid_ratio": self.route_stats["hybrid_count"] / total,
            "graph_rag_ratio": self.route_stats["graph_rag_count"] / total,
            "combined_ratio": self.route_stats["combined_count"] / total,
        }
