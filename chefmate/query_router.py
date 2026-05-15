"""
增强版查询路由器

支持混合意图识别、过滤条件提取、置信度评估。
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from openai import OpenAI


@dataclass
class QueryAnalysis:
    """查询分析结果"""
    intent: str = "general"  # list, detail, general, mixed
    confidence: float = 0.5
    filters: Dict[str, str] = field(default_factory=dict)  # category, difficulty
    sub_queries: List[str] = field(default_factory=list)  # 混合意图拆分的子查询
    needs_clarification: bool = False
    clarification_question: str = ""
    original_query: str = ""


class EnhancedQueryRouter:
    """增强版查询路由器"""
    
    def __init__(self, client: OpenAI, model_name: str):
        self.client = client
        self.model_name = model_name
        
        # 分类关键词映射
        self.category_keywords = {
            "素菜": ["素菜", "蔬菜", "青菜", "素食"],
            "荤菜": ["荤菜", "肉菜", "猪肉", "牛肉", "鸡肉", "羊肉"],
            "汤品": ["汤", "煲汤", "汤品"],
            "甜品": ["甜品", "甜点", "蛋糕", "饼干"],
            "早餐": ["早餐", "早饭"],
            "主食": ["主食", "米饭", "面条", "馒头", "饺子"],
            "水产": ["鱼", "虾", "蟹", "海鲜", "水产"],
            "饮品": ["饮料", "饮品", "茶", "咖啡", "果汁"],
        }
        
        self.difficulty_keywords = {
            "简单": ["简单", "容易", "新手", "入门", "快手"],
            "中等": ["中等", "一般"],
            "困难": ["困难", "复杂", "高级", "大厨"],
        }
    
    def analyze_query(self, query: str) -> QueryAnalysis:
        """
        分析用户查询，提取意图和过滤条件
        """
        # 尝试使用 LLM 进行高级分析
        try:
            return self._llm_analyze(query)
        except Exception:
            # 回退到规则分析
            return self._rule_based_analyze(query)
    
    def _llm_analyze(self, query: str) -> QueryAnalysis:
        """使用 LLM 分析查询"""
        prompt = f"""分析以下用户查询，返回 JSON 格式结果。

用户查询：{query}

请分析：
1. 主要意图类型：
   - "list": 用户想要菜品推荐列表（如"推荐几个菜"、"有什么素菜"）
   - "detail": 用户想要具体做法（如"怎么做"、"制作步骤"）
   - "general": 一般性问题（如"什么是川菜"、"烹饪技巧"）
   - "mixed": 混合意图（如"推荐3个简单素菜并告诉我怎么做"）

2. 过滤条件（如果有的话）：
   - category: 分类（荤菜/素菜/汤品/甜品/早餐/主食/水产/饮品）
   - difficulty: 难度（简单/中等/困难）

3. 如果是混合意图，拆分为子查询列表

请严格按照以下 JSON 格式返回，不要有其他内容：
{{"intent": "list|detail|general|mixed", "confidence": 0.0-1.0, "filters": {{"category": "...", "difficulty": "..."}}, "sub_queries": ["子查询1", "子查询2"], "needs_clarification": false, "clarification_question": ""}}"""

        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "你是查询分析专家，只返回标准 JSON 格式，不要有其他内容。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=300
        )
        
        content = resp.choices[0].message.content.strip()
        
        # 尝试解析 JSON
        try:
            # 处理可能的 markdown 代码块
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            result = json.loads(content)
            
            return QueryAnalysis(
                intent=result.get("intent", "general"),
                confidence=result.get("confidence", 0.7),
                filters=result.get("filters", {}),
                sub_queries=result.get("sub_queries", []),
                needs_clarification=result.get("needs_clarification", False),
                clarification_question=result.get("clarification_question", ""),
                original_query=query
            )
        except json.JSONDecodeError:
            # JSON 解析失败，使用规则分析
            return self._rule_based_analyze(query)
    
    def _rule_based_analyze(self, query: str) -> QueryAnalysis:
        """基于规则的查询分析（回退方案）"""
        intent = "general"
        confidence = 0.6
        filters = {}
        
        # 意图识别
        list_keywords = ["推荐", "有什么", "几个", "哪些", "什么菜", "想吃"]
        detail_keywords = ["怎么做", "制作", "步骤", "做法", "教我", "如何做"]
        
        if any(kw in query for kw in list_keywords):
            intent = "list"
            confidence = 0.7
        elif any(kw in query for kw in detail_keywords):
            intent = "detail"
            confidence = 0.7
        
        # 检查是否是混合意图
        has_list = any(kw in query for kw in list_keywords)
        has_detail = any(kw in query for kw in detail_keywords)
        if has_list and has_detail:
            intent = "mixed"
            confidence = 0.6
        
        # 提取过滤条件
        for category, keywords in self.category_keywords.items():
            if any(kw in query for kw in keywords):
                filters["category"] = category
                break
        
        for difficulty, keywords in self.difficulty_keywords.items():
            if any(kw in query for kw in keywords):
                filters["difficulty"] = difficulty
                break
        
        # 为混合意图生成子查询
        sub_queries = []
        if intent == "mixed":
            sub_queries = self._split_mixed_query(query)
        
        return QueryAnalysis(
            intent=intent,
            confidence=confidence,
            filters=filters,
            sub_queries=sub_queries,
            needs_clarification=False,
            clarification_question="",
            original_query=query
        )
    
    def _split_mixed_query(self, query: str) -> List[str]:
        """拆分混合意图为子查询"""
        sub_queries = []
        
        # 尝试按常见连接词拆分
        split_patterns = ["并且", "然后", "同时", "并", "再", "还有"]
        
        parts = [query]
        for pattern in split_patterns:
            new_parts = []
            for part in parts:
                new_parts.extend(part.split(pattern))
            parts = new_parts
        
        # 清理空字符串
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) > 1:
            sub_queries = parts
        else:
            # 无法拆分，保留原查询
            sub_queries = [query]
        
        return sub_queries
    
    def get_search_params(self, analysis: QueryAnalysis) -> Dict:
        """根据分析结果获取搜索参数"""
        params = {
            "top_k": 10,
            "use_filtered_search": bool(analysis.filters)
        }
        
        # list 类型需要更多结果
        if analysis.intent == "list":
            params["top_k"] = 15
        
        # 添加过滤器
        if analysis.filters:
            params["filters"] = analysis.filters
        
        return params
