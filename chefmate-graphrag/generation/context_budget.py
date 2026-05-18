import re
from typing import List
from langchain_core.documents import Document


class ContextBudgetManager:
    def __init__(self, max_tokens: int = 10000):
        self.max_tokens = max_tokens

    def compress_context(self, docs: List[Document]) -> List[Document]:
        sorted_docs = sorted(
            docs,
            key=lambda d: d.metadata.get("relevance_score", d.metadata.get("vector_score", 0)),
            reverse=True,
        )

        compressed = []
        used = 0
        for doc in sorted_docs:
            content = doc.page_content
            if doc.metadata.get("search_type") in ["graph_path", "knowledge_subgraph"]:
                content = content[:300]

            est = self._count_tokens(content)
            if used + est > self.max_tokens:
                if compressed:
                    break
                content = content[:self._tokens_to_chars(self.max_tokens - used)]
                est = self._count_tokens(content)

            compressed.append(Document(page_content=content, metadata=doc.metadata))
            used += est

        return compressed

    def _count_tokens(self, text: str) -> int:
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        english = len(re.findall(r"[a-zA-Z]+", text))
        other = len(text) - chinese - english
        return int(chinese * 1.5 + english * 0.8 + other * 0.3)

    def _tokens_to_chars(self, tokens: int) -> int:
        return int(tokens / 1.2)
