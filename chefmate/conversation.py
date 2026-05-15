"""
会话上下文管理器

支持多轮对话，理解指代关系，维护对话连贯性。
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class ConversationTurn:
    """对话轮次"""
    role: str  # "user" 或 "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)  # 菜品名、意图等


@dataclass
class ResolvedQuery:
    """解析后的查询"""
    original: str  # 原始查询
    resolved: str  # 解析后的完整查询
    references_resolved: bool = False  # 是否有指代被解析
    referenced_entities: List[str] = field(default_factory=list)  # 被引用的实体


class ConversationManager:
    """对话管理器"""
    
    def __init__(self, max_history: int = 5):
        self.max_history = max_history
        self.history: List[ConversationTurn] = []
        self.current_dishes: List[str] = []
        self.current_topic: str = ""
        self.last_recommended: List[str] = []  # 上次推荐的全部菜名
    
    def add_turn(self, role: str, content: str, metadata: Optional[Dict] = None):
        """添加对话轮次"""
        turn = ConversationTurn(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.history.append(turn)
        
        if role == "assistant" and metadata:
            recommended = metadata.get("recommended_dishes", [])
            if recommended:
                self.last_recommended = recommended
            dish_name = metadata.get("dish_name")
            if dish_name and dish_name not in self.current_dishes:
                self.current_dishes.append(dish_name)
                if len(self.current_dishes) > 3:
                    self.current_dishes.pop(0)
        
        if len(self.history) > self.max_history * 2:
            self.history = self.history[-(self.max_history * 2):]
    
    def resolve_references(self, query: str) -> ResolvedQuery:
        """
        解析查询中的指代词
        
        处理：
        - "那个菜"、"这道菜" → 最近讨论的菜品
        - "它"、"这个" → 上下文中的实体
        - "刚才那个" → 明确的指代
        - "怎么做"、"配料"、"难不难"、"有什么" → 延续话题
        """
        if not self.current_dishes:
            return ResolvedQuery(original=query, resolved=query)
        
        last_dish = self.current_dishes[-1]
        resolved = query
        references_found = []
        
        reference_patterns = [
            (r'那个菜|这道菜|刚才那个|它|这个|那一个', last_dish),
            (r'它的|这个的', last_dish),
        ]
        
        for pattern, replacement in reference_patterns:
            if re.search(pattern, resolved):
                resolved = re.sub(pattern, replacement, resolved)
                references_found.append(replacement)
        
        # 话题延续：查询中无具体菜名但包含动作词
        topic_words = ['怎么做', '做法', '如何制作', '食材', '原料', '配料',
                       '难不难', '难度', '简单', '步骤', '方法', '怎么炒',
                       '有没有', '有哪些', '还有什么', '类似的']
        if not references_found:
            query_clean = re.sub(r'[？?！!。.,，\s]', '', resolved)
            for tw in topic_words:
                if tw in resolved and not self._has_dish_name(resolved):
                    resolved = f'{last_dish}{resolved}'
                    references_found.append(last_dish)
                    break
        
        # 短查询指代补全
        if len(query) <= 6 and any(w in query for w in ['它', '这个', '那个']):
            if '怎么做' in query or '做法' in query:
                resolved = f'{last_dish}怎么做'
                references_found.append(last_dish)
            elif '食材' in query or '原料' in query:
                resolved = f'{last_dish}的食材'
                references_found.append(last_dish)
        
        return ResolvedQuery(
            original=query,
            resolved=resolved,
            references_resolved=len(references_found) > 0,
            referenced_entities=references_found
        )
    
    def _has_dish_name(self, text: str) -> bool:
        """检查文本中是否已包含有效菜名"""
        for dish in self.current_dishes:
            if dish in text:
                return True
        return False
    
    def get_context_summary(self) -> str:
        """获取对话上下文摘要（用于注入到 prompt）"""
        if not self.history:
            return ""
        
        summary_parts = []
        
        if self.current_dishes:
            summary_parts.append(f"当前讨论的菜品：{', '.join(self.current_dishes)}")
        
        if self.last_recommended:
            summary_parts.append(f"上次已推荐菜品（不要再次推荐）：{', '.join(self.last_recommended)}")
        
        recent_topics = []
        for turn in self.history[-4:]:
            if turn.role == "user":
                topic = turn.content[:50] + "..." if len(turn.content) > 50 else turn.content
                recent_topics.append(topic)
        
        if recent_topics:
            summary_parts.append("最近用户问：" + "；".join(recent_topics))
        
        return "\n".join(summary_parts) if summary_parts else ""
    
    def clear(self):
        """清空对话历史"""
        self.history.clear()
        self.current_dishes.clear()
        self.last_recommended.clear()
        self.current_topic = ""
    
    def get_history_text(self, max_turns: int = 3) -> str:
        """获取历史对话文本（用于生成上下文）"""
        if not self.history:
            return ""
        
        recent = self.history[-(max_turns * 2):]
        lines = []
        for turn in recent:
            role = "用户" if turn.role == "user" else "助手"
            content = turn.content[:100] + "..." if len(turn.content) > 100 else turn.content
            lines.append(f"{role}: {content}")
        
        return "\n".join(lines)
