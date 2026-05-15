from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SourceEvidence:
    dish_name: str
    category: str
    difficulty: str
    match_count: int
    vec_score: float
    bm25_score: float
    best_score: float
    content_preview: str


@dataclass
class QueryInfo:
    original: str
    rewritten: str
    route_type: str


@dataclass
class MetricsResult:
    query: QueryInfo
    sources: List[SourceEvidence]
    confidence: float
    retrieval_count: int
    elapsed_ms: float

    @staticmethod
    def compute(
        query: str,
        rewritten: str,
        route_type: str,
        parent_docs: list,
        chunk_scores: dict,
        elapsed_ms: float = 0,
    ) -> "MetricsResult":
        parent_groups: dict = {}
        all_scores = []
        for (parent_id, vec, bm25, combined) in chunk_scores.values():
            if parent_id not in parent_groups:
                parent_groups[parent_id] = {"scores": [], "vecs": [], "bm25s": [], "matched": 0}
            parent_groups[parent_id]["scores"].append(combined)
            parent_groups[parent_id]["vecs"].append(vec)
            parent_groups[parent_id]["bm25s"].append(bm25)
            parent_groups[parent_id]["matched"] += 1
            all_scores.append(combined)

        sources = []
        for doc in parent_docs:
            pid = doc.metadata.get("parent_id", "")
            group = parent_groups.get(pid, {"scores": [], "vecs": [], "bm25s": [], "matched": 0})
            best = max(group["scores"], default=0.0)

            if best <= 0.0:
                continue

            avg_vec = round(sum(group["vecs"]) / max(len(group["vecs"]), 1), 3)
            avg_bm25 = round(sum(group["bm25s"]) / max(len(group["bm25s"]), 1), 3)

            content_lines = doc.page_content.strip().split("\n")
            preview = "\n".join(content_lines[:3]) if content_lines else ""

            sources.append(SourceEvidence(
                dish_name=doc.metadata.get("dish_name", "未知"),
                category=doc.metadata.get("category", "未分类"),
                difficulty=doc.metadata.get("difficulty", "未知"),
                match_count=group["matched"],
                vec_score=avg_vec,
                bm25_score=avg_bm25,
                best_score=round(best, 3),
                content_preview=preview,
            ))

        top_score = max(all_scores, default=0.0)
        mean_score = sum(all_scores) / max(len(all_scores), 1)

        sources.sort(key=lambda s: s.best_score, reverse=True)

        confidence = round(
            min(1.0, top_score * 0.5 + mean_score * 0.3 + min(len(sources) / 3, 0.5) * 0.4),
            2,
        )

        return MetricsResult(
            query=QueryInfo(
                original=query,
                rewritten=rewritten,
                route_type=route_type,
            ),
            sources=sources,
            confidence=confidence,
            retrieval_count=len(all_scores),
            elapsed_ms=round(elapsed_ms, 1),
        )

    def summary(self) -> str:
        lines = []
        lines.append("─" * 50)
        lines.append(f"  查询路由: {self.query.route_type}")
        lines.append(
            f"  改写结果: {self.query.rewritten[:60]}{'...' if len(self.query.rewritten) > 60 else ''}"
        )
        lines.append(f"  检索耗时: {self.elapsed_ms}ms")
        bar_fill = int(self.confidence * 10)
        lines.append(
            f"  置信度:   {'█' * bar_fill}{'░' * (10 - bar_fill)} {self.confidence}"
        )
        lines.append(f"  证据来源: {len(self.sources)} 个菜谱")
        lines.append("─" * 50)

        for i, src in enumerate(self.sources):
            score_bar = "▓" * int(src.best_score * 10)
            lines.append(
                f"  [{i + 1}] {src.dish_name} ({src.category} / {src.difficulty})"
            )
            lines.append(
                f"      命中 {src.match_count} 个子块  |  "
                f"相关性: {score_bar:<10} {src.best_score}"
            )
        lines.append("─" * 50)
        return "\n".join(lines)
