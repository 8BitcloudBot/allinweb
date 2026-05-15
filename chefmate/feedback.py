"""
用户反馈收集器

收集用户对回答质量的反馈，用于持续优化。
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from dataclasses import dataclass, field, asdict


@dataclass
class FeedbackRecord:
    """反馈记录"""
    query: str
    answer: str
    rating: str  # "positive" 或 "negative"
    feedback_text: Optional[str] = None
    route_type: str = "general"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)


class FeedbackCollector:
    """反馈收集器"""
    
    def __init__(self, feedback_dir: str = "./feedback"):
        self.feedback_dir = Path(feedback_dir)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self.current_session: List[FeedbackRecord] = []
    
    def collect_feedback(
        self,
        query: str,
        answer: str,
        rating: str,
        feedback_text: str = "",
        route_type: str = "general",
        metadata: Optional[Dict] = None
    ) -> FeedbackRecord:
        """收集用户反馈"""
        record = FeedbackRecord(
            query=query,
            answer=answer[:500],  # 截断过长的答案
            rating=rating,
            feedback_text=feedback_text if feedback_text else None,
            route_type=route_type,
            metadata=metadata or {}
        )
        
        self.current_session.append(record)
        self._save_feedback(record)
        return record
    
    def _save_feedback(self, record: FeedbackRecord):
        """保存反馈到文件"""
        # 按日期分文件存储
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = self.feedback_dir / f"feedback_{date_str}.jsonl"
        
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    
    def get_feedback_stats(self, days: int = 7) -> Dict:
        """获取反馈统计信息"""
        stats = {
            "total": 0,
            "positive": 0,
            "negative": 0,
            "by_route_type": {},
            "satisfaction_rate": 0.0
        }
        
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            file_path = self.feedback_dir / f"feedback_{date_str}.jsonl"
            
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            record = json.loads(line.strip())
                            stats["total"] += 1
                            
                            if record.get("rating") == "positive":
                                stats["positive"] += 1
                            else:
                                stats["negative"] += 1
                            
                            route = record.get("route_type", "unknown")
                            if route not in stats["by_route_type"]:
                                stats["by_route_type"][route] = {"total": 0, "positive": 0}
                            stats["by_route_type"][route]["total"] += 1
                            if record.get("rating") == "positive":
                                stats["by_route_type"][route]["positive"] += 1
                        except json.JSONDecodeError:
                            continue
        
        # 计算满意度
        if stats["total"] > 0:
            stats["satisfaction_rate"] = round(stats["positive"] / stats["total"] * 100, 1)
        
        return stats
    
    def get_negative_feedback(self, days: int = 7, limit: int = 10) -> List[Dict]:
        """获取负面反馈（用于分析问题）"""
        negative_feedback = []
        
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            file_path = self.feedback_dir / f"feedback_{date_str}.jsonl"
            
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            record = json.loads(line.strip())
                            if record.get("rating") == "negative":
                                negative_feedback.append(record)
                                if len(negative_feedback) >= limit:
                                    return negative_feedback
                        except json.JSONDecodeError:
                            continue
        
        return negative_feedback

    def get_recent_wrong_queries(self, limit: int = 5) -> List[str]:
        """获取近期负面反馈的查询文本（用于注入纠正上下文）"""
        negative = self.get_negative_feedback(days=7, limit=limit)
        return [f.get("query", "") for f in negative if f.get("query")]
    
    def get_improvement_suggestions(self) -> List[str]:
        """基于反馈生成改进建议"""
        stats = self.get_feedback_stats()
        suggestions = []
        
        if stats["total"] < 5:
            return ["反馈数据不足，建议收集更多用户反馈"]
        
        # 分析满意度
        if stats["satisfaction_rate"] < 60:
            suggestions.append(f"整体满意度较低({stats['satisfaction_rate']}%)，需要全面优化回答质量")
        
        # 分析各路由类型的表现
        for route, route_stats in stats["by_route_type"].items():
            if route_stats["total"] >= 3:
                route_rate = route_stats["positive"] / route_stats["total"] * 100
                if route_rate < 50:
                    suggestions.append(f"路由类型 '{route}' 满意度较低({route_rate:.0f}%)，建议重点优化")
        
        # 分析负面反馈的常见问题
        negative = self.get_negative_feedback()
        if negative:
            common_queries = [f["query"] for f in negative[:3]]
            suggestions.append(f"常见问题查询：{', '.join(common_queries)}")
        
        return suggestions if suggestions else ["当前表现良好，继续收集反馈"]
    
    def export_feedback(self, output_file: str, days: int = 30):
        """导出反馈数据用于分析"""
        all_feedback = []
        
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            file_path = self.feedback_dir / f"feedback_{date_str}.jsonl"
            
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            record = json.loads(line.strip())
                            all_feedback.append(record)
                        except json.JSONDecodeError:
                            continue
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_feedback, f, ensure_ascii=False, indent=2)
        
        return len(all_feedback)
