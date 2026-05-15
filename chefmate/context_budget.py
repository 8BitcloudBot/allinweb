"""
上下文预算管理器

根据 token 限制动态调整上下文内容，确保关键信息不被淹没。
解决 LLM "迷失在中间" 的问题。
"""

from typing import List, Dict, Optional
from langchain_core.documents import Document


class ContextBudgetManager:
    """上下文预算管理器"""
    
    def __init__(self, max_tokens: int = 10000):
        self.max_tokens = max_tokens
    
    def compress_context(
        self, 
        docs: List[Document], 
        query: str,
        score_map: Optional[Dict[str, float]] = None
    ) -> str:
        """
        智能压缩上下文
        
        策略：
        1. 按相关性分数排序文档
        2. 优先保留高分内容
        3. 对长文档提取关键段落（食材、步骤）
        4. 确保总 token 数不超过预算
        """
        if not docs:
            return ""
        
        if score_map:
            sorted_docs = sorted(
                docs, 
                key=lambda d: score_map.get(d.metadata.get("chunk_id", ""), 0),
                reverse=True
            )
        else:
            sorted_docs = docs
        
        result_parts = []
        total_tokens = 0
        
        for doc in sorted_docs:
            content = doc.page_content
            doc_tokens = self._count_tokens(content)
            
            if total_tokens + doc_tokens > self.max_tokens:
                key_content = self._extract_key_sections(content)
                key_tokens = self._count_tokens(key_content)
                
                if total_tokens + key_tokens <= self.max_tokens:
                    result_parts.append(key_content)
                    total_tokens += key_tokens
                else:
                    break
            else:
                result_parts.append(content)
                total_tokens += doc_tokens
        
        return "\n---\n".join(result_parts)
    
    def _extract_key_sections(self, content: str) -> str:
        """提取菜谱关键部分：标题、食材、步骤、贴士"""
        lines = content.split("\n")
        key_lines = []
        in_important_section = False
        
        IMPORTANT_KEYWORDS = [
            "必备原料", "计算", "操作",
            "## 食材", "## 步骤", "## 做法", "## 制作",
            "附加内容", "## 贴士", "## 提示", "## 注意",
            "烹饪难度", "预估时间", "营养",
        ]
        
        for line in lines:
            if any(keyword in line for keyword in IMPORTANT_KEYWORDS):
                in_important_section = True
            elif line.startswith("## ") and in_important_section:
                if line.startswith("### ") and in_important_section:
                    in_important_section = True
                else:
                    in_important_section = False
            
            if in_important_section or line.startswith("#"):
                key_lines.append(line)
        
        return "\n".join(key_lines) if key_lines else content[:800]
    
    def _count_tokens(self, text: str) -> int:
        """使用 DeepSeek tokenizer 估算 token 数"""
        if not text:
            return 0
        
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fa5')
        english_words = len([w for w in text.split() if any(c.isascii() for c in w)])
        other_chars = len(text) - chinese_chars - sum(
            len(w) for w in text.split() if any(c.isascii() for c in w)
        )
        
        tokens = int(chinese_chars * 1.5 + english_words * 0.8 + other_chars * 0.3)
        return max(tokens, 1)
    
    def truncate_to_budget(self, text: str) -> str:
        """截断文本到预算限制"""
        if self._count_tokens(text) <= self.max_tokens:
            return text
        
        # 二分查找合适的截断点
        left, right = 0, len(text)
        while left < right:
            mid = (left + right + 1) // 2
            if self._count_tokens(text[:mid]) <= self.max_tokens:
                left = mid
            else:
                right = mid - 1
        
        return text[:left] + "\n...(内容已截断)"
