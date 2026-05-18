from typing import List
from dataclasses import dataclass, field


@dataclass
class ResolvedQuery:
    query: str
    original: str
    context: str = ""
    exclude_dishes: List[str] = field(default_factory=list)


class ConversationManager:
    def __init__(self, max_history: int = 5):
        self.max_history = max_history
        self.history: List[dict] = []
        self.last_recommended: List[str] = []

    def resolve_references(self, query: str) -> ResolvedQuery:
        context_parts = []
        exclude = list(self.last_recommended) if self.last_recommended else []

        # Build context from recent conversation turns
        for turn in self.history[-self.max_history:]:
            if turn["role"] == "user":
                context_parts.append(f"用户问: {turn['content'][:150]}")
            elif turn["role"] == "assistant":
                # Summarize assistant response
                content = turn["content"][:150]
                context_parts.append(f"助手答: {content}")

        return ResolvedQuery(
            query=query,
            original=query,
            context="\n".join(context_parts),
            exclude_dishes=exclude,
        )

    def add_turn(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_history * 2:
            self.history = self.history[-self.max_history * 2:]

    def set_recommended(self, dishes: List[str]):
        self.last_recommended = dishes[:5]
