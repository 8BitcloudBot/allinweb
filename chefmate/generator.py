import json
import re
from typing import List, Optional, Dict

from openai import OpenAI
from langchain_core.documents import Document

from .context_budget import ContextBudgetManager


def _valid_dish_names(context_docs: List[Document]) -> list[str]:
    names = []
    for doc in context_docs:
        name = doc.metadata.get("dish_name", "未知菜品")
        if name not in names:
            names.append(name)
    return names


class GenerationIntegrationModule:
    def __init__(self, config):
        self.model_name = config.llm_model
        self.temperature = config.temperature
        self.max_tokens = getattr(config, "max_tokens", 2048)
        self.client = OpenAI(
            api_key=config.llm_api_key, base_url=config.llm_base_url
        )
        # 上下文预算管理器
        self.context_manager = ContextBudgetManager(max_tokens=10000)

    def query_router(self, query: str) -> str:
        prompt = (
            "将用户问题分类为以下三种之一（只输出分类词）：\n"
            "list   - 用户想要菜品列表或推荐，或按场景/食材/口味推荐菜\n"
            "         如：推荐几个素菜、有什么川菜、夏天适合吃什么、下饭菜、用鸡蛋能做什么\n"
            "detail - 用户想要制作方法或步骤\n"
            "         如：宫保鸡丁怎么做、需要什么食材、怎么炒\n"
            "general - 知识问答、技巧、营养、食材替代、闲聊等\n"
            "         如：什么是川菜、没有淀粉用什么代替、炒菜技巧\n\n"
            f"用户问题: {query}\n分类:"
        )
        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return resp.choices[0].message.content.strip()

    def query_rewrite(self, query: str, dish_hints: list[str] | None = None) -> str:
        hints_block = ""
        if dish_hints:
            hints_block = f"\n已知菜谱库包含相关菜品: {', '.join(dish_hints[:15])}\n"

        prompt = (
            "你是菜谱检索优化助手。将用户查询改写为最适合向量检索的中文关键词查询。\n"
            "规则：\n"
            "- 模糊查询（如'做菜''好吃的'）→ 添加具体食材、菜系、口味等关键词\n"
            "- 明确查询（如'宫保鸡丁'）→ 保持原名并补充同义词（如'宫保鸡丁 川菜 花生鸡丁'）\n"
            "- 输出纯关键词字符串，不要加解释\n"
            f"{hints_block}"
            f"原始查询: {query}\n改写:"
        )
        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()

    def _prepare_context(
        self, 
        context_docs: List[Document], 
        score_map: Optional[Dict[str, float]] = None
    ) -> str:
        """准备上下文文本，使用预算管理器压缩"""
        return self.context_manager.compress_context(
            docs=context_docs,
            query="",  # 查询已在 prompt 中
            score_map=score_map
        )

    def generate_list_answer(
        self, query: str, context_docs: List[Document], 
        score_map: Optional[Dict[str, float]] = None,
        exclude_dishes: Optional[List[str]] = None,
        constraints: Optional[Dict] = None
    ) -> str:
        valid_names = _valid_dish_names(context_docs)
        if exclude_dishes:
            exclude_set = set(exclude_dishes)
            valid_names = [n for n in valid_names if n not in exclude_set]
        context_text = self._prepare_context(context_docs, score_map)

        exclude_block = ""
        if exclude_dishes:
            exclude_block = f"\n以下菜品已经推荐过，本次绝对不要推荐：{', '.join(exclude_dishes)}\n"

        # 构建约束提示
        constraint_block = ""
        if constraints:
            if constraints.get("servings"):
                servings = constraints["servings"]
                constraint_block = f"""
⚠️ 重要约束：
- 用户需要适合 {servings} 人吃的菜
- 请优先推荐份量足够 {servings} 人的菜品
- 如果菜谱份量不足，请在推荐理由中说明需要按比例增加食材用量
"""

        prompt = (
            "你是专业美食推荐师。用户的需求和可推荐的菜品如下。\n\n"
            f"用户需求: {query}\n"
            f"{constraint_block}\n"
            f"可推荐菜品（仅限以下菜品，不可增减）:\n"
            + "\n".join(f"- {n}" for n in valid_names) + "\n\n"
            + exclude_block +
            f"菜品详情:\n{context_text}\n\n"
            "要求：\n"
            "1. 只从上面「可推荐菜品」列表中选取，一个都不能超出\n"
            "2. 推荐后为每道菜写一句简短的推荐理由（基于菜谱内容）\n"
            "3. 如果用户提到了人数/份量，请在推荐理由中说明是否适合该人数\n"
            "4. 输出纯 JSON，格式如下：\n"
            '{"dishes": [{"name": "菜名", "reason": "推荐理由"}]}\n'
        )
        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": "你是专业美食推荐师。你只能推荐用户明确提供的菜品列表中的菜，禁止编造。输出纯 JSON。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        raw = resp.choices[0].message.content

        dishes = self._parse_list_output(raw, valid_names)
        if not dishes:
            return f"根据菜谱库推荐以下菜品：\n\n" + "\n".join(f"- {n}" for n in valid_names[:10])

        lines = []
        for d in dishes:
            name = d.get("name", "")
            if name not in valid_names:
                continue
            reason = d.get("reason", "")
            lines.append(f"- **{name}** — {reason}" if reason else f"- **{name}**")

        header = f"为你推荐以下菜品：\n\n"
        return header + "\n".join(lines)

    def _parse_list_output(self, raw: str, valid_names: list[str]) -> list[dict]:
        try:
            json_match = re.search(r'\{[\s\S]*"dishes"[\s\S]*\}', raw)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("dishes", [])
        except (json.JSONDecodeError, KeyError):
            pass
        results = []
        for name in valid_names:
            if name in raw:
                results.append({"name": name, "reason": ""})
        return results

    def generate_step_by_step_answer(
        self, query: str, context_docs: List[Document],
        score_map: Optional[Dict[str, float]] = None
    ) -> str:
        context_text = self._prepare_context(context_docs, score_map)
        
        prompt = (
            "你是一位经验丰富的厨师。请根据以下菜谱资料，为用户提供制作指导。\n\n"
            "请按以下结构组织回答：\n"
            "## 菜品简介\n"
            "## 所需食材\n"
            "## 制作步骤\n"
            "## 制作贴士\n\n"
            "要求：\n"
            "- 严格基于菜谱内容回答，不要提及'根据菜谱信息'或统计菜谱数量\n"
            "- 如果用户问的菜不在资料中，坦诚说明'该菜品暂未收录'，不要编造做法\n"
            "- 用 Markdown 格式，食材和步骤用列表呈现\n\n"
            f"菜谱资料:\n{context_text}\n\n"
            f"用户问题: {query}"
        )
        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": "你是专业厨师。严格基于菜谱资料回答。资料中没有的菜，直接告知'暂未收录'，绝不编造步骤。不要提及'根据资料'或统计数量。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
        )
        return resp.choices[0].message.content

    def generate_basic_answer(
        self, query: str, context_docs: List[Document],
        score_map: Optional[Dict[str, float]] = None
    ) -> str:
        context_text = self._prepare_context(context_docs, score_map)
        
        prompt = (
            "根据以下菜谱资料回答用户问题，用简洁易懂的语言，Markdown 格式。\n"
            "如果资料中有相关内容但不完全匹配，可以根据菜谱常识推断和补充。\n\n"
            f"{context_text}\n\n用户问题: {query}"
        )
        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": "你是烹饪知识助手。请结合菜谱资料和烹饪常识回答。即使资料没有直接提及，也尝试从已有菜谱中提取相关信息给出建议。不要提及'根据资料'或统计数量。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
        )
        return resp.choices[0].message.content

    def generate_stream(
        self, query: str, context_docs: List[Document], route_type: str,
        score_map: Optional[Dict[str, float]] = None,
        exclude_dishes: Optional[List[str]] = None
    ):
        context_text = self._prepare_context(context_docs, score_map)
        valid_names = _valid_dish_names(context_docs) if route_type == "list" else []
        if exclude_dishes and route_type == "list":
            exclude_set = set(exclude_dishes)
            valid_names = [n for n in valid_names if n not in exclude_set]

        system_prompts = {
            "list": "你是专业美食推荐师。只能推荐可推荐列表中列出的菜品，禁止编造。输出纯 JSON 数组。",
            "detail": "你是专业厨师。严格基于菜谱资料回答。资料中没有的菜，告知'暂未收录'，绝不编造。不要提及'根据资料'或统计数量。",
            "general": "你是烹饪知识助手。请结合菜谱资料和烹饪常识回答。即使资料没有直接提及，也尝试从已有菜谱中提取相关信息给出建议。不要提及'根据资料'或统计数量。",
        }

        user_prompts = {
            "list": (
                "可推荐菜品（仅限以下，不可增减）:\n"
                + "\n".join(f"- {n}" for n in valid_names) + "\n\n"
                + (f"以下菜品已经推荐过，本次绝对不要推荐：{', '.join(exclude_dishes)}\n\n" if exclude_dishes else "")
                + f"菜品详情:\n{context_text}\n\n"
                + f"用户需求: {query}\n\n"
                + "输出 JSON 格式: {\"dishes\": [{\"name\": \"菜名\", \"reason\": \"理由\"}]}"
            ),
            "detail": (
                "你是专业厨师。请根据以下菜谱资料提供制作指导。\n\n"
                "按以下结构组织：\n"
                "## 菜品简介\n## 所需食材\n## 制作步骤\n## 制作贴士\n\n"
                "要求：\n"
                "- 严格基于菜谱内容回答\n"
                "- 不存在的菜告知'暂未收录'，绝不编造\n"
                "- Markdown 格式，食材和步骤用列表\n\n"
                f"菜谱资料:\n{context_text}\n\n"
                f"用户问题: {query}"
            ),
            "general": f"根据以下菜谱资料回答用户问题。如果资料中没有直接答案，请从已知菜谱中提取相关的菜品或技巧来回答。用简洁易懂的语言，Markdown 格式：\n\n{context_text}\n\n用户问题: {query}",
        }

        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": system_prompts.get(
                        route_type, "你是一个智能助手。"
                    ),
                },
                {
                    "role": "user",
                    "content": user_prompts.get(
                        route_type, context_text + "\n\n问题: " + query
                    ),
                },
            ],
            temperature=self.temperature,
            stream=True,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content
