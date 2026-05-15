"""
查询分析器

从用户查询中提取约束条件，如份量、分类、难度等。
"""

import re
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from openai import OpenAI


@dataclass
class QueryConstraints:
    """查询约束条件"""
    servings: Optional[int] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    ingredients: List[str] = field(default_factory=list)
    intent: str = "general"  # list, detail, general


class QueryAnalyzer:
    """查询分析器，提取用户的约束条件"""
    
    # 中文数字映射
    CHINESE_NUMBERS = {
        '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
        '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
        '三十': 30, '四十': 40, '五十': 50,
    }
    
    # 份量关键词映射（支持中文数字）
    SERVING_PATTERNS = [
        # 阿拉伯数字
        (r'(\d+)\s*个人', lambda m: int(m.group(1))),
        (r'(\d+)\s*人[吃食份]', lambda m: int(m.group(1))),
        (r'(\d+)\s*人[的量]', lambda m: int(m.group(1))),
        (r'够\s*(\d+)\s*人', lambda m: int(m.group(1))),
        (r'适合\s*(\d+)\s*人', lambda m: int(m.group(1))),
        # 中文数字
        (r'([零一二两三四五六七八九十]+)\s*个人', lambda m: QueryAnalyzer._chinese_to_int(m.group(1))),
        (r'([零一二两三四五六七八九十]+)\s*人[吃食份]', lambda m: QueryAnalyzer._chinese_to_int(m.group(1))),
        (r'([零一二两三四五六七八九十]+)\s*人[的量]', lambda m: QueryAnalyzer._chinese_to_int(m.group(1))),
        (r'够\s*([零一二两三四五六七八九十]+)\s*人', lambda m: QueryAnalyzer._chinese_to_int(m.group(1))),
        (r'适合\s*([零一二两三四五六七八九十]+)\s*人', lambda m: QueryAnalyzer._chinese_to_int(m.group(1))),
    ]
    
    # 分类关键词
    CATEGORY_KEYWORDS = {
        "素菜": ["素菜", "蔬菜", "青菜", "素食"],
        "荤菜": ["荤菜", "肉菜", "猪肉", "牛肉", "鸡肉", "羊肉", "肉"],
        "汤品": ["汤", "煲汤", "汤品"],
        "甜品": ["甜品", "甜点", "蛋糕", "饼干"],
        "早餐": ["早餐", "早饭"],
        "主食": ["主食", "米饭", "面条", "馒头", "饺子"],
        "水产": ["鱼", "虾", "蟹", "海鲜", "水产"],
        "饮品": ["饮料", "饮品", "茶", "咖啡", "果汁"],
    }
    
    # 难度关键词
    DIFFICULTY_KEYWORDS = {
        "简单": ["简单", "容易", "新手", "入门", "快手"],
        "中等": ["中等", "一般"],
        "困难": ["困难", "复杂", "高级", "大厨"],
    }
    
    def __init__(self, client: Optional[OpenAI] = None, model_name: str = "deepseek-chat"):
        self.client = client
        self.model_name = model_name
    
    @staticmethod
    def _chinese_to_int(chinese: str) -> int:
        """将中文数字转换为整数"""
        if chinese in QueryAnalyzer.CHINESE_NUMBERS:
            return QueryAnalyzer.CHINESE_NUMBERS[chinese]
        
        # 处理复合数字（如"二十一"）
        result = 0
        current = 0
        for char in chinese:
            if char in QueryAnalyzer.CHINESE_NUMBERS:
                num = QueryAnalyzer.CHINESE_NUMBERS[char]
                if num == 10:  # "十" 是单位
                    if current == 0:
                        current = 1  # "十" 前面没有数字表示 10
                    result += current * 10
                    current = 0
                else:
                    current = num
            else:
                return 0  # 无法识别的字符
        
        result += current
        return result if result > 0 else 0
    
    def analyze(self, query: str) -> QueryConstraints:
        """分析查询，提取约束条件"""
        constraints = QueryConstraints()
        
        # 提取份量
        constraints.servings = self._extract_servings(query)
        
        # 提取分类
        constraints.category = self._extract_category(query)
        
        # 提取难度
        constraints.difficulty = self._extract_difficulty(query)
        
        # 识别意图
        constraints.intent = self._detect_intent(query)
        
        return constraints
    
    def _extract_servings(self, query: str) -> Optional[int]:
        """提取份量需求"""
        for pattern, extractor in self.SERVING_PATTERNS:
            match = re.search(pattern, query)
            if match:
                try:
                    return extractor(match)
                except (ValueError, IndexError):
                    continue
        return None
    
    def _extract_category(self, query: str) -> Optional[str]:
        """提取分类需求"""
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                return category
        return None
    
    def _extract_difficulty(self, query: str) -> Optional[str]:
        """提取难度需求"""
        for difficulty, keywords in self.DIFFICULTY_KEYWORDS.items():
            if any(kw in query for kw in keywords):
                return difficulty
        return None
    
    def _detect_intent(self, query: str) -> str:
        """检测查询意图"""
        list_keywords = ["推荐", "有什么", "几个", "哪些", "什么菜", "想吃", "来个"]
        detail_keywords = ["怎么做", "制作", "步骤", "做法", "教我", "如何做"]
        
        has_list = any(kw in query for kw in list_keywords)
        has_detail = any(kw in query for kw in detail_keywords)
        
        if has_list and has_detail:
            return "mixed"
        elif has_list:
            return "list"
        elif has_detail:
            return "detail"
        else:
            return "general"
    
    def get_filter_params(self, constraints: QueryConstraints) -> Dict:
        """将约束条件转换为检索过滤参数"""
        filters = {}
        
        if constraints.servings:
            filters["min_servings"] = constraints.servings
        
        if constraints.category:
            filters["category"] = constraints.category
        
        if constraints.difficulty:
            filters["difficulty"] = constraints.difficulty
        
        return filters
    
    def build_constraint_prompt(self, constraints: QueryConstraints) -> str:
        """构建约束提示文本"""
        parts = []
        
        if constraints.servings:
            parts.append(f"⚠️ 重要：用户需要适合 {constraints.servings} 人吃的菜")
            parts.append(f"请优先推荐份量足够 {constraints.servings} 人的菜品")
            parts.append(f"如果菜谱份量不足，请建议用户按比例增加食材用量")
        
        if constraints.category:
            parts.append(f"用户想要的分类：{constraints.category}")
        
        if constraints.difficulty:
            parts.append(f"用户想要的难度：{constraints.difficulty}")
        
        return "\n".join(parts) if parts else ""
