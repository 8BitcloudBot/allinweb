import time
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class MetricsResult:
    latency_seconds: float = 0.0
    retrieval_count: int = 0
    confidence_score: float = 0.0
    route_strategy: str = ""
    graph_metrics: Dict[str, Any] = field(default_factory=dict)
    source_breakdown: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def compute(cls, docs: List, analysis, start_time: float) -> "MetricsResult":
        latency = time.time() - start_time
        if not docs:
            return cls(latency_seconds=latency)

        raw_scores = [d.metadata.get("relevance_score", d.metadata.get("vector_score", 0)) for d in docs]
        scores = [min(max(s, 0), 1) for s in raw_scores]
        confidence = sum(scores) / max(len(scores), 1)

        source_breakdown = {}
        for doc in docs:
            src = doc.metadata.get("search_source", doc.metadata.get("search_type", "unknown"))
            source_breakdown[src] = source_breakdown.get(src, 0) + 1

        # When graph_rag falls back to hybrid, keep search_source as graph_rag
        # so the frontend canvas displays correctly
        primary_source = docs[0].metadata.get("search_source", "unknown") if docs else ""
        route_strat = analysis.recommended_strategy.value if analysis else ""
        if route_strat == "graph_rag" and primary_source in ("milvus", "bm25"):
            primary_source = "graph_rag"

        graph_metrics = {
            "node_count": sum(d.metadata.get("node_count", 0) for d in docs),
            "relationship_count": sum(d.metadata.get("relationship_count", 0) for d in docs),
            "traversal_depth": max((d.metadata.get("path_length", 0) for d in docs), default=0),
            "search_source": primary_source,
        }

        return cls(
            latency_seconds=latency,
            retrieval_count=len(docs),
            confidence_score=confidence,
            route_strategy=analysis.recommended_strategy.value if analysis else "",
            graph_metrics=graph_metrics,
            source_breakdown=source_breakdown,
        )
