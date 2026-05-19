import os
import pickle
import sys
import time
from pathlib import Path
from typing import Generator, Optional, Union

sys.path.insert(0, str(Path(__file__).parent))

from config import DEFAULT_CONFIG, ChefMateConfig
from chefmate.loader import DataPreparationModule
from chefmate.indexer import IndexConstructionModule
from chefmate.retriever import RetrievalOptimizationModule
from chefmate.generator import GenerationIntegrationModule
from chefmate.metrics import MetricsResult
from chefmate.conversation import ConversationManager
from chefmate.validator import AnswerValidator
from chefmate.feedback import FeedbackCollector
from chefmate.query_analyzer import QueryAnalyzer


PARENT_CHILD_MAP_PATH = Path(DEFAULT_CONFIG.index_save_path) / "parent_child_map.pkl"


def _load_parent_child_map() -> dict:
    if PARENT_CHILD_MAP_PATH.exists():
        with open(PARENT_CHILD_MAP_PATH, "rb") as f:
            return pickle.load(f)
    return {}


def _save_parent_child_map(mapping: dict):
    PARENT_CHILD_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PARENT_CHILD_MAP_PATH, "wb") as f:
        pickle.dump(mapping, f)


class RecipeRAGSystem:
    def __init__(self, config: Optional[ChefMateConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.data_module: Optional[DataPreparationModule] = None
        self.index_module: Optional[IndexConstructionModule] = None
        self.retrieval_module: Optional[RetrievalOptimizationModule] = None
        self.generation_module: Optional[GenerationIntegrationModule] = None
        
        # 新增：会话管理器
        self.conversation = ConversationManager(max_history=5)
        # 新增：答案验证器
        self.validator = AnswerValidator()
        # 新增：反馈收集器
        self.feedback_collector = FeedbackCollector()
        # 新增：查询分析器
        self.query_analyzer = QueryAnalyzer()

        if not Path(self.config.data_path).exists():
            raise FileNotFoundError(
                f"数据路径不存在: {self.config.data_path}"
            )
        if not self.config.llm_api_key:
            raise ValueError("请设置 DEEPSEEK_API_KEY 环境变量")

    def initialize_system(self):
        self.data_module = DataPreparationModule(self.config.data_path)
        self.index_module = IndexConstructionModule(
            model_name=self.config.embedding_model,
            index_save_path=self.config.index_save_path,
            config=self.config,
        )
        self.generation_module = GenerationIntegrationModule(self.config)

    def build_knowledge_base(self):
        vectorstore = self.index_module.load_index()
        if vectorstore is not None:
            self.data_module.load_documents()
            chunks = self.data_module.chunk_documents()
            self.data_module.parent_child_map = _load_parent_child_map()
        else:
            self.data_module.load_documents()
            chunks = self.data_module.chunk_documents()
            vectorstore = self.index_module.build_vector_index(chunks)
            self.index_module.save_index()
            _save_parent_child_map(self.data_module.parent_child_map)

        self.retrieval_module = RetrievalOptimizationModule(
            vectorstore, chunks
        )
        
        # 加载有效菜品名到验证器
        self.validator.load_valid_dishes(self.data_module.documents)

    def _extract_main_dish(self, query: str, answer: str) -> Optional[str]:
        """从查询和答案中提取主要讨论的菜品名"""
        dish = self.validator.extract_dish_from_answer(answer)
        if dish:
            return dish
        dish = self.validator.extract_dish_from_answer(query)
        return dish

    def _inject_feedback(self, query: str, route_type: str) -> str:
        """注入近期负面反馈作为纠正上下文"""
        wrong_queries = self.feedback_collector.get_recent_wrong_queries(limit=5)
        if not wrong_queries:
            return query

        examples = "\n".join(f"- 错误回答: {w[:80]}" for w in wrong_queries[:3])
        return f"{query}\n\n[以下是用户历史不满意的回答，请避免类似错误]\n{examples}"

    def ask_question(
        self, question: str, stream: bool = False, with_metrics: bool = False
    ) -> Union[str, Generator, dict]:
        t0 = time.time()
        
        # 1. 解析指代词（会话上下文）
        resolved = self.conversation.resolve_references(question)
        actual_query = resolved.resolved
        
        # 2. 获取对话上下文摘要
        context_summary = self.conversation.get_context_summary()
        if context_summary:
            actual_query_with_context = f"{actual_query}\n\n[对话上下文]\n{context_summary}"
        else:
            actual_query_with_context = actual_query
        
        # 3. 查询分析（提取约束条件）
        constraints = self.query_analyzer.analyze(actual_query)
        filters = self.query_analyzer.get_filter_params(constraints)
        constraint_prompt = self.query_analyzer.build_constraint_prompt(constraints)
        
        # 4. 查询路由
        route_type = self.generation_module.query_router(actual_query)

        if route_type == "list":
            rewritten_query = actual_query
            top_k = min(self.config.top_k * 2, 20)
        else:
            rewritten_query = self.generation_module.query_rewrite(actual_query)
            top_k = self.config.top_k

        # 5. 检索（支持元数据筛选）
        relevant_chunks = self.retrieval_module.hybrid_search(
            rewritten_query, top_k=top_k, filters=filters if filters else None
        )

        # HyDE fallback: when retrieval returns empty, generate hypothetical document and re-search
        if not relevant_chunks:
            hypothetical = self._hyde_generate(actual_query)
            if hypothetical:
                relevant_chunks = self.retrieval_module.hybrid_search(
                    hypothetical, top_k=top_k
                )

        relevant_docs = self.data_module.get_parent_documents(relevant_chunks)

        elapsed_ms = (time.time() - t0) * 1000

        # 6. 计算指标
        chunk_scores = None
        metrics = None
        if with_metrics:
            chunk_scores = self.retrieval_module.get_scores_for_docs(
                rewritten_query, relevant_chunks
            )
            metrics = MetricsResult.compute(
                query=question,
                rewritten=rewritten_query,
                route_type=route_type,
                parent_docs=relevant_docs,
                chunk_scores=chunk_scores,
                elapsed_ms=elapsed_ms,
            )

        # 7. 构建带约束的查询
        if constraint_prompt:
            query_with_constraints = f"{actual_query_with_context}\n\n[约束条件]\n{constraint_prompt}"
        else:
            query_with_constraints = actual_query_with_context

        # 8. 流式生成
        if stream:
            gen = self.generation_module.generate_stream(
                query_with_constraints, relevant_docs, route_type,
                exclude_dishes=self.conversation.last_recommended
            )
            if with_metrics:
                return {"stream": gen, "metrics": metrics}
            return gen

        # 9. 非流式生成
        # 注入负面反馈作为纠正上下文
        corrected_query = self._inject_feedback(query_with_constraints, route_type)

        if route_type == "list":
            answer = self.generation_module.generate_list_answer(
                corrected_query, relevant_docs,
                exclude_dishes=self.conversation.last_recommended,
                constraints=constraints.__dict__ if constraints else None
            )
        elif route_type == "detail":
            answer = self.generation_module.generate_step_by_step_answer(
                corrected_query, relevant_docs
            )
        else:
            answer = self.generation_module.generate_basic_answer(
                corrected_query, relevant_docs
            )

        # 8. 答案验证（针对 list 类型）
        if route_type == "list":
            validation = self.validator.validate_answer(
                answer, relevant_docs, route_type
            )
            if not validation.is_valid:
                # 添加警告
                answer += f"\n\n⚠️ 注意：{'; '.join(validation.warnings)}"

        # 9. 记录会话
        main_dish = self._extract_main_dish(actual_query, answer)
        all_dishes = self.validator.extract_all_dishes_from_answer(answer)
        self.conversation.add_turn("user", question)
        self.conversation.add_turn(
            "assistant", 
            answer[:200],
            {
                "dish_name": main_dish,
                "recommended_dishes": all_dishes,
                "route_type": route_type,
            }
        )

        if with_metrics:
            return {"answer": answer, "metrics": metrics}
        return answer

    def _hyde_generate(self, query: str) -> str:
        """Generate a hypothetical recipe description for HyDE re-search."""
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=self.config.deepseek_api_key,
                base_url=self.config.deepseek_base_url,
            )
            prompt = f"""你是中餐厨师。用户问了一个问题，请用一段自然流畅的文字描述可能的答案。
不用列表，就一段话，描述相关的菜品名称、主要食材和做法特点。控制在150字以内。

用户问题: {query}"""
            response = client.chat.completions.create(
                model=self.config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5, max_tokens=300,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return ""

    def run_interactive(self):
        print("=" * 60)
        print("ChefMate — 智能食谱问答系统 v2.0")
        print("=" * 60)
        print("新功能：")
        print("  - 支持多轮对话（可以问'那个菜怎么做'）")
        print("  - 智能上下文管理（长菜谱自动压缩）")
        print("  - 答案验证（防止推荐不存在的菜品）")
        print("  - 反馈收集（帮助改进系统）")
        print("=" * 60)

        self.initialize_system()
        self.build_knowledge_base()
        print("系统就绪，请输入您的问题\n")

        while True:
            try:
                query = input("You: ").strip()
                if not query:
                    continue
                if query.lower() in ("exit", "quit", "q"):
                    print("再见！")
                    break
                
                # 特殊命令：查看对话历史
                if query.lower() == "history":
                    history_text = self.conversation.get_history_text()
                    if history_text:
                        print("\n--- 对话历史 ---")
                        print(history_text)
                        print("--- 结束 ---\n")
                    else:
                        print("暂无对话历史\n")
                    continue
                
                # 特殊命令：查看反馈统计
                if query.lower() == "stats":
                    stats = self.feedback_collector.get_feedback_stats()
                    suggestions = self.feedback_collector.get_improvement_suggestions()
                    print("\n--- 反馈统计 ---")
                    print(f"总反馈数: {stats['total']}")
                    print(f"满意度: {stats['satisfaction_rate']}%")
                    print(f"改进建议: {'; '.join(suggestions)}")
                    print("--- 结束 ---\n")
                    continue

                # 正常问答
                result = self.ask_question(
                    query, stream=False, with_metrics=True
                )
                answer = result["answer"]
                metrics: MetricsResult = result["metrics"]

                print(f"\nChefMate: {answer}")
                print(metrics.summary())
                
                # 收集反馈
                print("\n这个回答有帮助吗？(y=有帮助 / n=没帮助 / 直接回车跳过)")
                feedback = input("> ").strip().lower()
                
                if feedback in ("y", "yes", "是", "有帮助"):
                    self.feedback_collector.collect_feedback(
                        query=query,
                        answer=answer,
                        rating="positive",
                        route_type=metrics.query.route_type
                    )
                    print("感谢反馈！\n")
                elif feedback in ("n", "no", "否", "没帮助"):
                    feedback_text = input("请告诉我们哪里不好（可选，直接回车跳过）: ").strip()
                    self.feedback_collector.collect_feedback(
                        query=query,
                        answer=answer,
                        rating="negative",
                        feedback_text=feedback_text,
                        route_type=metrics.query.route_type
                    )
                    print("感谢反馈！我们会努力改进。\n")
                else:
                    print()

            except KeyboardInterrupt:
                print("\n再见！")
                break
            except Exception as e:
                print(f"错误: {e}")
                import traceback
                traceback.print_exc()


def main():
    try:
        system = RecipeRAGSystem()
        system.run_interactive()
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
