import re
import json
import logging
from typing import List, Generator
from openai import OpenAI
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class GenerationIntegrationModule:
    def __init__(self, config):
        self.config = config
        self.client = OpenAI(
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
        )

    def generate_adaptive_answer(self, query: str, docs: List[Document]) -> str:
        if not docs:
            return "😅 没有找到相关的烹饪信息，换个关键词试试？"

        route = docs[0].metadata.get("route_strategy", "hybrid_traditional")
        messages = self._build_messages(query, docs, route)

        try:
            response = self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=messages,
                temperature=0.3, max_tokens=2048,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return docs[0].page_content[:500] if docs else ""

    def _build_messages(self, query: str, docs: List[Document], route: str) -> list:
        if route == "graph_rag":
            return self._build_graph_messages(query, docs)
        elif _is_list_query(query):
            return self._build_list_messages(query, docs)
        elif _is_detail_query(query):
            return self._build_detail_messages(query, docs)
        else:
            return self._build_general_messages(query, docs)

    def _build_list_messages(self, query: str, docs: List[Document]) -> list:
        valid_names = list({d.metadata.get("recipe_name", "") for d in docs if d.metadata.get("recipe_name")})[:15]
        context = "\n\n".join(
            f"菜名: {d.metadata.get('recipe_name', '')}\n{d.page_content[:500]}"
            for d in docs[:5]
        )
        prompt = f"""你是专业烹饪助手。根据知识库内容推荐菜品。

知识库内容:
{context}

可选菜品: {', '.join(valid_names)}

用户需求: {query}

输出格式要求:
- 每道菜用 emoji 🍳 开头
- 菜名和推荐理由之间用 — 分隔
- 每道菜之间空一行
- 最后可加一句总结
- 如果知识库无相关菜品，如实说明

示例:
🍳 糖醋排骨 — 酸甜开胃，老少皆宜，制作简单

🍳 红烧肉 — 肥而不腻，入口即化，经典家常菜

你推荐的菜品都在上面的可选菜品列表中，不要编造菜名。
"""
        return [{"role": "user", "content": prompt}]

    def _build_detail_messages(self, query: str, docs: List[Document]) -> list:
        context = "\n\n".join(d.page_content[:1000] for d in docs[:3])
        prompt = f"""你是专业烹饪助手。根据菜谱内容回答用户问题。

菜谱资料:
{context}

用户问题: {query}

输出格式要求:
- 用 emoji 区分不同段落
- 段落之间空一行，保持呼吸感
- 食材和步骤用列表呈现（- 开头）
- 不要加粗、不要用 ## 标题，保持简洁自然

示例格式:

🥘 菜品简介
简要介绍这道菜的特点

🛒 所需食材
- 食材1 用量
- 食材2 用量

👨‍🍳 制作步骤
1. 第一步说明
2. 第二步说明

💡 制作贴士
- 小技巧1
- 小技巧2

如果菜谱库中未收录这道菜，请说"暂未收录此菜品"，不要编造。
"""
        return [{"role": "user", "content": prompt}]

    def _build_general_messages(self, query: str, docs: List[Document]) -> list:
        # Check if docs are actually useful
        has_useful_content = any(len(d.page_content) > 50 for d in docs[:3])
        
        if has_useful_content:
            context = "\n\n".join(d.page_content[:800] for d in docs[:5])
            prompt = f"""你是专业烹饪助手。根据菜谱知识回答用户问题。

知识来源:
{context}

用户问题: {query}

输出格式要求:
- 段落之间空一行
- 列表项用 - 开头
- 如有多个要点，分点列出
- 不要加粗、不要用 ## 标题
- 如果信息不足以准确回答，如实说明
"""
        else:
            prompt = f"""你是专业烹饪助手。菜谱库中没有找到与该问题直接相关的内容。

用户问题: {query}

输出格式要求:
- 基于你的通用烹饪知识回答，并在开头说明"菜谱库中暂无相关信息，以下为通用建议："
- 段落之间空一行
- 列表项用 - 开头
- 不要编造菜谱库中的菜品
"""
        return [{"role": "user", "content": prompt}]

    def _build_graph_messages(self, query: str, docs: List[Document]) -> list:
        ctx_parts = []
        for i, d in enumerate(docs[:8]):
            meta = d.metadata
            stype = meta.get("search_type", "")
            if stype == "graph_path":
                ctx_parts.append(f"[路径 {i+1} 深度={meta.get('path_length','?')}] {d.page_content}")
            elif stype in ("subgraph_summary",):
                ctx_parts.append(f"[子图统计] {d.page_content}")
            elif stype == "subgraph_node":
                ctx_parts.append(f"[图谱节点] {d.page_content}")
            else:
                ctx_parts.append(f"[来源] {d.page_content}")
        context_str = "\n".join(ctx_parts)

        prompt = f"""你是基于知识图谱的烹饪助手。通过图检索获得了以下信息。

图谱检索结果:
{context_str}

用户问题: {query}

输出格式要求:
- 段落之间空一行，保持呼吸感
- 列表项用 emoji + 文字，如 🥘 菜名、🧄 食材、🏷️ 分类
- 多个发现分点列出，用数字序号（1. 2. 3.）
- 不要加粗、不要用 ## 标题
- 如果图谱无结果，如实说明，并建议用户换个方式提问

示例格式:

通过图谱检索，发现了以下关联:

1. 🥘 大盘鸡 使用了 🧄 土豆、🧄 大蒜、🧄 大葱
2. 🥘 照烧鸡腿饭 与大盘鸡共享 3 种食材

💡 可以继续追问某道菜的具体做法
"""
        return [{"role": "user", "content": prompt}]

    def _generate_list_answer(self, query: str, docs: List[Document]) -> str:
        valid_names = list({d.metadata.get("recipe_name", "") for d in docs if d.metadata.get("recipe_name")})[:15]
        context = "\n\n".join(
            f"Dish: {d.metadata.get('recipe_name', '')}\n{d.page_content[:500]}"
            for d in docs[:5]
        )
        prompt = f"""你是专业烹饪助手。根据知识库内容回答用户问题。

知识范围: {context}
有效菜品: {', '.join(valid_names)}

用户问题: {query}

要求:
- 仅从有效菜品列表中推荐
- 返回 JSON 格式: {{"dishes": [{{"name": "菜名", "reason": "推荐理由"}}]}}
- 如果知识库无相关菜品，返回: {{"dishes": []}}
- 绝对不要编造菜名
"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=1024,
            )
            text = response.choices[0].message.content.strip()
            text = text[text.find("{"):text.rfind("}") + 1]
            data = json.loads(text)
            dishes = data.get("dishes", [])
            if not dishes:
                return "No matching dishes found."
            return "\n".join(
                f"**{d['name']}** — {d['reason']}"
                for d in dishes if d.get("name") in valid_names
            ) or f"Recommended: {', '.join(valid_names[:5])}"
        except Exception as e:
            logger.error(f"List generation failed: {e}")
            return f"Recommended: {', '.join(valid_names[:5])}"

    def _generate_detail_answer(self, query: str, docs: List[Document]) -> str:
        context = "\n\n".join(d.page_content[:1000] for d in docs[:3])
        prompt = f"""你是专业烹饪助手。根据以下菜谱内容回答用户问题。

菜谱资料:
{context}

用户问题: {query}

回答格式要求:
- 使用 Markdown，包含以下章节：
  ## 菜品简介 — 这道菜的背景和特点
  ## 所需食材 — 列出所有原料和大致用量
  ## 制作步骤 — 详细的操作说明
  ## 制作贴士 — 实用的烹饪建议
- 内容只来自提供的菜谱资料，不要编造
- 如果菜谱库中未收录这道菜，请说"暂未收录此菜品"
"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=2048,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            text = docs[0].page_content[:800] if docs else ""
            return f"Recipe overview:\n{text}"

    def _generate_general_answer(self, query: str, docs: List[Document]) -> str:
        context = "\n\n".join(d.page_content[:800] for d in docs[:5])
        prompt = f"""你是专业烹饪助手。根据以下菜谱知识回答用户问题。

知识来源:
{context}

用户问题: {query}

要求: 回答基于提供的知识来源。如果信息不足以准确回答，请如实说明。
"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=2048,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return docs[0].page_content[:500] if docs else ""

    def _generate_graph_answer(self, query: str, docs: List[Document]) -> str:
        ctx_parts = []
        for i, d in enumerate(docs[:5]):
            meta = d.metadata
            if meta.get("search_type") == "graph_path":
                ctx_parts.append(f"[路径 {i+1} 深度={meta.get('path_length','?')}] {d.page_content}")
            elif meta.get("search_type") in ("knowledge_subgraph", "subgraph_summary"):
                ctx_parts.append(f"[子图 节点数={meta.get('node_count','?')}] {d.page_content}")
            elif meta.get("search_type") == "subgraph_node":
                ctx_parts.append(f"[图谱节点] {d.page_content}")
            else:
                ctx_parts.append(f"[来源] {d.page_content}")
        context_str = "\n".join(ctx_parts)

        prompt = f"""你是基于知识图谱的烹饪助手。通过图检索获得了以下知识路径。

图谱检索结果:
{context_str}

用户问题: {query}

回答要求:
- 首先简要总结图谱揭示了什么关键关系
- 使用 ### 标注每个发现组（如 ### 直接关联、### 隐含连接）
- 使用 emoji 增强可读性: 🥘 菜品、🧄 食材、🏷️ 分类
- 如果发现了具体路径，以"**食材A** → 菜品 → **食材B**"格式呈现
- 优先展示图谱中发现的关联，而非一般常识
- 如果图谱无结果，如实说明
"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=2048,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return self._generate_general_answer(query, docs)

    def generate_stream(self, query: str, docs: List[Document]) -> Generator[str, None, None]:
        if not docs:
            yield "😅 没有找到相关的烹饪信息，换个关键词试试？"
            return

        route = docs[0].metadata.get("route_strategy", "hybrid_traditional")
        messages = self._build_messages(query, docs, route)

        try:
            stream = self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=messages,
                temperature=0.3, max_tokens=2048,
                stream=True,
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            logger.error(f"Stream generation failed: {e}")
            yield self.generate_adaptive_answer(query, docs)


def _is_list_query(query: str) -> bool:
    return any(re.search(p, query) for p in [r"哪些|推荐|有什么|列出|列举|几个"])


def _is_detail_query(query: str) -> bool:
    return any(re.search(p, query) for p in [r"怎么做|步骤|做法|方法|怎么|如何"])
