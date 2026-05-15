"""
ChefMate 全模块测试
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DEFAULT_CONFIG

PASS = 0
FAIL = 0


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ PASS: {name}")
    else:
        FAIL += 1
        print(f"  ❌ FAIL: {name}  {detail}")


def print_header(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ═══════════════════════════════════════════════
# 测试 1: DataPreparationModule
# ═══════════════════════════════════════════════
print_header("模块 1: DataPreparationModule")

from chefmate.loader import DataPreparationModule

dpm = DataPreparationModule(DEFAULT_CONFIG.data_path)

docs = dpm.load_documents()
test("load_documents() 返回 List[Document]", isinstance(docs, list) and len(docs) > 0,
     f"共 {len(docs)} 个文档")

target = None
for d in docs:
    if "西红柿炒鸡蛋" in d.metadata.get("source", ""):
        target = d
        break

test("能找到'西红柿炒鸡蛋'", target is not None)
if target:
    test("元数据: dish_name", target.metadata.get("dish_name") == "西红柿炒鸡蛋")
    test("元数据: category", target.metadata.get("category") in ("素菜", "荤菜", "汤品", "主食"))
    test("元数据: difficulty", target.metadata.get("difficulty") in ("简单", "中等", "困难", "未标记"))
    test("元数据: parent_id 是 UUID",
         len(target.metadata.get("parent_id", "")) == 36)
    test("元数据: doc_type == 'parent'", target.metadata.get("doc_type") == "parent")

chunks = dpm.chunk_documents()
test("chunk_documents() 返回 List[Document]", isinstance(chunks, list) and len(chunks) > 0,
     f"共 {len(chunks)} 个子块")
test("parent_child_map 非空", len(dpm.parent_child_map) > 0)

if chunks:
    c = chunks[0]
    test("子块有 chunk_id", len(c.metadata.get("chunk_id", "")) == 36)
    test("子块有 parent_id", len(c.metadata.get("parent_id", "")) == 36)
    test("子块 doc_type == 'child'", c.metadata.get("doc_type") == "child")
    test("子块有 chunk_index", isinstance(c.metadata.get("chunk_index"), int))
    test("子块有 chunk_size", isinstance(c.metadata.get("chunk_size"), int))
    test("strip_headers=False (标题保留)",
         c.page_content.strip().startswith("#") or c.page_content.strip().startswith("##"))

target_chunks = [c for c in chunks
                 if c.metadata.get("parent_id") == target.metadata["parent_id"]]
test("西红柿炒鸡蛋被正确分块", len(target_chunks) >= 3,
     f"共 {len(target_chunks)} 个子块")

# 模拟检索去重
mock_results = chunks[:5]
parents = dpm.get_parent_documents(mock_results)
test("get_parent_documents() 去重后 <= 传入数量",
     len(parents) <= len(mock_results))


# ═══════════════════════════════════════════════
# 测试 2: IndexConstructionModule
# ═══════════════════════════════════════════════
print_header("模块 2: IndexConstructionModule")

from chefmate.indexer import IndexConstructionModule

icm = IndexConstructionModule(
    model_name=DEFAULT_CONFIG.embedding_model,
    index_save_path=DEFAULT_CONFIG.index_save_path,
    config=DEFAULT_CONFIG,
)
test("setup_embeddings() 初始化 embeddings", icm.embeddings is not None)

vs = icm.build_vector_index(chunks)
test("build_vector_index() 返回 FAISS", vs is not None and hasattr(vs, "similarity_search"))

test("index_exists() 构建后存在", icm.index_exists() is True)

icm.save_index()
test("save_index() 文件写入",
     (Path(DEFAULT_CONFIG.index_save_path) / "index.faiss").exists() and
     (Path(DEFAULT_CONFIG.index_save_path) / "index.pkl").exists())

# 验证加载
icm2 = IndexConstructionModule(
    model_name=DEFAULT_CONFIG.embedding_model,
    index_save_path=DEFAULT_CONFIG.index_save_path,
    config=DEFAULT_CONFIG,
)
loaded_vs = icm2.load_index()
test("load_index() 返回 FAISS", loaded_vs is not None)
if loaded_vs:
    results = loaded_vs.similarity_search("西红柿", k=2)
    test("similarity_search 返回结果", len(results) > 0,
         f"查询'西红柿'返回 {len(results)} 条")


# ═══════════════════════════════════════════════
# 测试 3: RetrievalOptimizationModule
# ═══════════════════════════════════════════════
print_header("模块 3: RetrievalOptimizationModule")

from chefmate.retriever import RetrievalOptimizationModule

rom = RetrievalOptimizationModule(vs, chunks)
test("setup_retrievers() 初始化检索器", rom.vector_retriever is not None and rom.bm25_retriever is not None)

hybrid_results = rom.hybrid_search("宫保鸡丁", top_k=3)
test("hybrid_search() 返回 Document 列表", isinstance(hybrid_results, list))
test("hybrid_search top_k 生效", len(hybrid_results) <= 3,
     f"实际 {len(hybrid_results)} 条")
if hybrid_results:
    test("hybrid_search 结果含 metadata",
         "dish_name" in hybrid_results[0].metadata)

filtered = rom.metadata_filtered_search(
    "素菜", filters={"category": "素菜"}, top_k=2
)
test("metadata_filtered_search 返回 ≤ top_k",
     len(filtered) <= 2, f"实际 {len(filtered)} 条")
if filtered:
    test("metadata_filtered 分类过滤正确",
         all(d.metadata.get("category") == "素菜" for d in filtered))

vector_results = vs.similarity_search("宫保鸡丁", k=3)
bm25_results = rom.bm25_retriever.invoke("宫保鸡丁")
rrf = RetrievalOptimizationModule._rrf_rerank(vector_results, bm25_results)
test("_rrf_rerank 返回全部去重结果",
     len(rrf) >= max(len(vector_results), len(bm25_results)))


# ═══════════════════════════════════════════════
# 测试 4: GenerationIntegrationModule
# ═══════════════════════════════════════════════
print_header("模块 4: GenerationIntegrationModule")

from chefmate.generator import GenerationIntegrationModule

gim = GenerationIntegrationModule(DEFAULT_CONFIG)
test("__init__ 初始化 client", gim.client is not None and gim.model_name == DEFAULT_CONFIG.llm_model)

route = gim.query_router("推荐两个素菜")
test("query_router('推荐两个素菜') == 'list'", route == "list",
     f"实际返回: {route}")

route = gim.query_router("宫保鸡丁怎么做")
test("query_router('宫保鸡丁怎么做') == 'detail'", route == "detail",
     f"实际返回: {route}")

route = gim.query_router("什么是川菜")
test("query_router('什么是川菜') == 'general'", route == "general",
     f"实际返回: {route}")

rewritten = gim.query_rewrite("宫保鸡丁怎么做")
test("query_rewrite 返回非空字符串", isinstance(rewritten, str) and len(rewritten) > 10,
     f"结果: {rewritten[:50]}...")

# 生成测试
list_answer = gim.generate_list_answer("推荐两个素菜", parents[:2])
test("generate_list_answer 返回非空", isinstance(list_answer, str) and len(list_answer) > 0)

# 使用实际的父文档进行测试
test_query = f"{parents[0].metadata.get('dish_name', '这道菜')}怎么做" if parents else "这道菜怎么做"
detail_answer = gim.generate_step_by_step_answer(test_query, parents[:1])
test("generate_step_by_step_answer 返回非空", isinstance(detail_answer, str) and len(detail_answer) > 0)
test("detail 回答含结构化标记",
     "食材" in detail_answer or "步骤" in detail_answer or "制作" in detail_answer)

general_answer = gim.generate_basic_answer("炒菜需要什么技巧", parents[:2])
test("generate_basic_answer 返回非空", isinstance(general_answer, str) and len(general_answer) > 0)

# 流式测试
stream_chunks = list(gim.generate_stream(test_query, parents[:1], "detail"))
test("generate_stream 产出文本片段", len(stream_chunks) > 0,
     f"共 {len(stream_chunks)} 个片段")


# ═══════════════════════════════════════════════
# 测试 5: RecipeRAGSystem 端到端
# ═══════════════════════════════════════════════
print_header("模块 5: RecipeRAGSystem 端到端")

from main import RecipeRAGSystem

system = RecipeRAGSystem()
test("RecipeRAGSystem 初始化", system.config is not None)

system.initialize_system()
test("initialize_system 初始化所有子模块",
     all([
         system.data_module is not None,
         system.index_module is not None,
         system.generation_module is not None,
     ]))

system.build_knowledge_base()
test("build_knowledge_base 构建检索模块",
     system.retrieval_module is not None)

# 非流式问答
answer = system.ask_question("宫保鸡丁怎么做", stream=False)
test("ask_question (非流式) 返回字符串", isinstance(answer, str) and len(answer) > 50,
     f"长度 {len(answer)}")

# 流式问答
stream_gen = system.ask_question("宫保鸡丁怎么做", stream=True)
collected = list(stream_gen)
test("ask_question (流式) 产出片段", len(collected) > 0,
     f"共 {len(collected)} 个片段")

# list 类型问答
list_answer = system.ask_question("推荐两个素菜", stream=False)
test("list 问答返回列表格式", isinstance(list_answer, str) and len(list_answer) > 0,
     f"结果: {list_answer[:80]}")


# ═══════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════
print_header("测试汇总")
total = PASS + FAIL
print(f"  总计: {total}  |  通过: {PASS}  |  失败: {FAIL}")
print(f"  通过率: {PASS / total * 100:.1f}%")
print(f"{'=' * 60}")

sys.exit(0 if FAIL == 0 else 1)
