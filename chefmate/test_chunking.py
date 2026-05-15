"""
分块效果测试 — 以"西红柿炒鸡蛋"为例
"""

from pathlib import Path
from chefmate.loader import DataPreparationModule


def print_separator(char="=", width=60):
    print(f"\n{char * width}\n")


def main():
    data_path = str(Path(__file__).parent.parent / "data")
    module = DataPreparationModule(data_path)

    print_separator("=")
    print("  1. 加载文档")
    print_separator("-")

    module.load_documents()

    target = None
    for doc in module.documents:
        if "红烧茄子" in doc.metadata.get("source", ""):
            target = doc
            break

    if not target:
        print("未找到红烧茄子")
        return

    print(f"  源文件: {target.metadata['source']}")
    print(f"  文档长度: {len(target.page_content)} 字符")
    print(f"  parent_id: {target.metadata['parent_id']}")

    print_separator("=")
    print("  2. 元数据增强结果")
    print_separator("-")

    print(f"  菜品名称: {target.metadata['dish_name']}")
    print(f"  菜品分类: {target.metadata['category']}")
    print(f"  难度等级: {target.metadata['difficulty']}")

    print_separator("=")
    print("  3. 分块结果")
    print_separator("-")

    module.chunk_documents()

    target_chunks = [
        c for c in module.chunks
        if c.metadata.get("parent_id") == target.metadata["parent_id"]
    ]

    print(f"  该文档共切分为 {len(target_chunks)} 个子块\n")

    for i, chunk in enumerate(target_chunks):
        first_line = chunk.page_content.strip().split("\n")[0]
        print(f"  ─── 子块 {i + 1} ───")
        print(f"  chunk_id: {chunk.metadata['chunk_id']}")
        print(f"  parent_id: {chunk.metadata['parent_id']}")
        print(f"  doc_type: {chunk.metadata['doc_type']}")
        print(f"  chunk_index: {chunk.metadata['chunk_index']}")
        print(f"  chunk_size: {chunk.metadata['chunk_size']} 字符")
        print(f"  标题: {first_line.strip()}")
        print(f"\n  内容预览:")
        for line in chunk.page_content.strip().split("\n")[:7]:
            print(f"    {line}")
        if len(chunk.page_content.split("\n")) > 6:
            print(f"    ... (共 {len(chunk.page_content.split(chr(10)))} 行)")
        print()

    print_separator("=")
    print("  4. 父子关系映射")
    print_separator("-")

    print(f"  parent_child_map 条目数: {len(module.parent_child_map)}")
    for chunk in target_chunks:
        child_id = chunk.metadata["chunk_id"]
        parent_id = module.parent_child_map.get(child_id, "")
        title = chunk.metadata.get("header_2", chunk.metadata.get("header_1", "(无标题)"))
        print(f"    child({child_id[:8]}...) → parent({parent_id[:8]}...)  [{title}]")

    print_separator("=")
    print("  5. 模拟检索去重效果")
    print_separator("-")

    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5",
        encode_kwargs={"normalize_embeddings": True},
    )
    vs = FAISS.from_documents(
        module.chunks[:100], embeddings
    )

    query = "西红柿炒鸡蛋的食材"
    results = vs.similarity_search(query, k=5)
    print(f"  查询: \"{query}\"\n")
    print(f"  向量检索到 {len(results)} 个子块:\n")

    for r in results:
        heading = r.page_content.strip().split("\n")[0]
        print(f"  ● [{r.metadata['dish_name']}]  {heading}")

    parent_docs = module.get_parent_documents(results)
    print(f"\n  去重后得到 {len(parent_docs)} 个父文档（同一道菜只输出一次）")

    print_separator("=")
    print("  6. 最终父文档内容（生成阶段传给 LLM）")
    print_separator("-")

    for i, doc in enumerate(parent_docs):
        print(f"  父文档 {i + 1}: {doc.metadata['dish_name']}")
        print(f"  分类: {doc.metadata['category']}  |  难度: {doc.metadata['difficulty']}")
        content = doc.page_content
        print(f"  全文 ({len(content)} 字符):\n")
        for line in content.strip().split("\n")[:15]:
            print(f"    {line}")
        print(f"    ...")
        print()


if __name__ == "__main__":
    main()
