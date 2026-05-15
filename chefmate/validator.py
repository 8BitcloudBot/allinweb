"""
答案-证据一致性验证器

确保生成的答案中的菜品确实存在于检索到的证据中，防止幻觉。
"""

import re
from difflib import get_close_matches
from dataclasses import dataclass, field
from typing import List, Set, Optional
from langchain_core.documents import Document


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    hallucinated_dishes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    confidence: float = 0.5


class AnswerValidator:
    """答案验证器"""
    
    def __init__(self):
        # 从菜谱库加载有效菜品名（初始化时加载）
        self.valid_dishes: Set[str] = set()
        # 常见的烹饪动词模式（使用非贪婪匹配）
        self.cooking_patterns = [
            r'[\u4e00-\u9fa5]{2,6}?(?:炒|炖|蒸|煮|煎|炸|烤|拌|烧|焖|爆|溜|醋溜|红烧|清蒸|干煸|水煮)[\u4e00-\u9fa5]{1,4}',
            r'[\u4e00-\u9fa5]{2,4}(?:汤|羹|粥|饭|面|饼|糕|酥|酪)',
        ]
    
    def load_valid_dishes(self, documents: List[Document]):
        """从文档列表加载有效菜品名"""
        for doc in documents:
            dish_name = doc.metadata.get("dish_name")
            if dish_name:
                self.valid_dishes.add(dish_name)
    
    def validate_answer(
        self, 
        answer: str, 
        context_docs: List[Document],
        route_type: str = "general"
    ) -> ValidationResult:
        """
        验证答案与证据的一致性
        
        检查项：
        1. 答案中提到的菜品是否在证据中存在
        2. list 类型回答是否仅包含库中菜品
        """
        if not answer:
            return ValidationResult(is_valid=True, confidence=0.5)
        
        warnings = []
        hallucinated = []
        
        # 提取答案中的菜名
        mentioned_dishes = self._extract_dish_names(answer)
        
        # 获取证据中的菜名
        evidence_dishes = {
            doc.metadata.get("dish_name") 
            for doc in context_docs
            if doc.metadata.get("dish_name")
        }
        
        # 检查是否有虚构菜品
        for dish in mentioned_dishes:
            if dish not in evidence_dishes and dish not in self.valid_dishes:
                hallucinated.append(dish)
        
        # 对于 list 类型，更严格检查
        if route_type == "list" and hallucinated:
            warnings.append(f"推荐了不存在的菜品: {', '.join(hallucinated)}")
        
        # 计算验证置信度
        if not mentioned_dishes:
            confidence = 0.5  # 没有提到具体菜品
        elif hallucinated:
            confidence = 0.3  # 有虚构内容
        else:
            confidence = 0.9  # 所有菜品都有证据支持
        
        return ValidationResult(
            is_valid=len(hallucinated) == 0,
            hallucinated_dishes=hallucinated,
            warnings=warnings,
            confidence=confidence
        )
    
    def _extract_dish_names(self, text: str) -> List[str]:
        found_dishes = []
        for dish in self.valid_dishes:
            if dish in text:
                found_dishes.append(dish)
        return list(set(found_dishes))

    def extract_dish_from_answer(self, answer: str) -> Optional[str]:
        mentioned = self._extract_dish_names(answer)
        return mentioned[0] if mentioned else None

    def extract_all_dishes_from_answer(self, answer: str) -> list[str]:
        """提取答案中所有匹配的有效菜名"""
        return self._extract_dish_names(answer)

    def fuzzy_match_unknown(self, text: str) -> dict[str, str]:
        """对文本中未精准匹配的疑似菜名做模糊匹配，返回 {疑似菜名: 最接近的有效菜名}"""
        results = {}
        if not self.valid_dishes:
            return results
        dish_list = list(self.valid_dishes)
        for word in re.findall(r'[\u4e00-\u9fa5]{2,8}', text):
            if word not in self.valid_dishes:
                matches = get_close_matches(word, dish_list, n=1, cutoff=0.75)
                if matches:
                    results[word] = matches[0]
        return results
