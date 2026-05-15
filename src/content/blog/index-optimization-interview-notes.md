---
title: "RAG 面试速查：索引优化深度解析（句子窗口检索 + 结构化递归检索）"
description: "覆盖句子窗口检索、结构化递归检索、元数据、索引构建本质、子查询引擎、LLM 介入时机等面试高频问题，附完整 RAG 知识地图"
pubDate: 2025-09-06
tags: ["RAG", "索引优化", "LlamaIndex", "句子窗口检索", "结构化索引", "递归检索", "面试"]
lang: "zh"
---

# RAG 面试速查：索引优化深度解析

> 基于 Datawhale all-in-rag 教程，系统梳理索引优化面试高频考点，涵盖句子窗口检索、结构化递归检索、元数据索引等核心技术。

## 目录

- [检索方法的分类体系](#一检索方法的分类体系)
- [句子窗口检索](#二句子窗口检索)
- [结构化递归检索](#三结构化递归检索)
- [元数据索引](#四元数据索引)
- [面试高频问题](#五面试高频问题)

---

## 一、检索方法的分类体系

在讨论具体技术之前，先建立全局分类视角。RAG 的所有优化方法可以分为三个层面：

```
RAG 优化方法
├── ① 索引优化（Index Optimization）—— "怎么存"
│   ├── 分块策略优化：固定 / 递归 / 语义分块
│   ├── 上下文扩展（Context Enrichment）
│   │   ├── 句子窗口检索（Sentence Window Retrieval）
│   │   └── 父子块检索（Parent-Child Chunking）
│   └── 结构化索引（Structured Index）
│       ├── 元数据索引（Metadata Indexing）
│       └── 递归检索（Recursive Retrieval）
│
├── ② 检索优化（Retrieval Optimization）—— "怎么搜"
│   ├── 混合检索（Hybrid Search）：向量 + 关键词 BM25
│   ├── 查询构建（Query Construction）：Text-to-DSL / SQL
│   ├── 查询重写（Query Rewriting）：扩展 / 分解 / 改述查询
│   └── 高级检索技术：多跳、自纠错、CRAG
│
└── ③ 生成优化（Generation Optimization）—— "怎么答"
    ├── 格式化生成、Prompt 工程
    └── 引用溯源
```

**关键区分**：

| 维度 | 索引优化 | 检索优化 |
|------|---------|---------|
| 优化对象 | 存储方式：文档怎么切、怎么存、怎么组织 | 搜索方式：查询怎么处理、怎么找、怎么排序 |
| 发生时机 | 索引构建阶段（一次性完成） | 查询阶段（每次查询都执行） |
| 口诀 | "怎么存" | "怎么搜" |

> **面试话术**：句子窗口检索和结构化递归检索都属于"索引优化"层面，核心动作发生在索引构建阶段，而不是检索阶段。

<hr/>

<div class="callout callout-info">
<strong>📘 背景</strong>
面试中问到"索引优化"相关问题时，建议先画出三层分类体系（索引→检索→生成），再逐层展开。这样既展示了全局视野，又不会遗漏关键的"发生时序"区分——索引优化是一次性的离线工作，检索优化是每次查询都在线的执行。
</div>

---

## 二、句子窗口检索（Sentence Window Retrieval）

### 2.1 一句话定义

> 索引时用单句保证检索精度，生成前用上下文窗口保证回答质量。

### 2.2 解决了什么问题？

传统 RAG 面临的两难：

| 分块策略 | 检索精度 | 生成质量 | 问题 |
|---------|---------|---------|------|
| 小块（单句） | 高 | 差 | 缺乏上下文，LLM 无法连贯作答 |
| 大块（段落） | 低 | 好 | 引入噪音，检索不精准 |
| **句子窗口** | 高 | 好 | 两者兼顾 |

### 2.3 核心流程

```
索引阶段 ──→ 检索阶段 ──→ 后处理阶段 ──→ 生成阶段
```

| 阶段 | 做什么 | 关键点 |
|------|--------|--------|
| 索引 | 文档切分为单句，每个句子存为一个 Node；同时把前后各 N 句作为"窗口"存入 metadata | 窗口文本不参与向量化，只存 metadata |
| 检索 | 用户问题向量化，在单句索引上做相似度搜索 | 精准定位核心句子 |
| 后处理 | `MetadataReplacementPostProcessor` 用 metadata 中的窗口文本替换原来的单句 | 送入 LLM 前"膨胀"上下文 |
| 生成 | 包含丰富上下文的节点送入 LLM 生成回答 | 质量大幅提升 |

### 2.4 代码实现

```python
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.node_parser import SentenceWindowNodeParser
from llama_index.core.postprocessor import MetadataReplacementPostProcessor

# 1. 加载文档
documents = SimpleDirectoryReader(
    input_files=["data/IPCC_AR6_WGII_Chapter03.pdf"]
).load_data()

# 2. 创建句子窗口解析器
node_parser = SentenceWindowNodeParser.from_defaults(
    window_size=3,
    original_metadata_metadata_key="original_text",
    window_metadata_key="window_text",
)

# 3. 创建索引
index = VectorStoreIndex.from_documents(
    documents,
    node_parser=node_parser,
)

# 4. 创建查询引擎（关键：后处理替换）
query_engine = index.as_query_engine(
    similarity_top_k=5,
    node_postprocessors=[
        MetadataReplacementPostProcessor(target_metadata_key="window_text")
    ]
)

# 5. 查询
response = query_engine.query("气候变化对海洋生态系统有什么影响？")
```

<hr/>

<div class="callout callout-tip">
<strong>💡 技巧</strong>
<code>window_size</code> 是句子窗口检索的关键参数。经验值：技术文档 3-5，论文摘要 2-3，长篇报告 5-7。过大的窗口会引入噪音，过小的窗口上下文不足。面试时可以主动提及这个参数的调优经验。
</div>

---

## 三、结构化递归检索（Structured Recursive Retrieval）

### 3.1 一句话定义

> 用文档自身的结构（目录、章节）组织索引，先定位到相关章节，再在章节内做精细检索。

### 3.2 解决了什么问题？

大规模知识库的检索效率问题：

| 方案 | 检索范围 | 效率 | 精度 |
|------|---------|------|------|
| **暴力搜索** | 全部文档 | 低 | 中 |
| **结构化递归** | 先定位章节，再搜索 | 高 | 高 |

### 3.3 核心流程

```
用户查询
    ↓
第一层检索：定位到最相关的章节/文档
    ↓
第二层检索：在章节内做精细搜索
    ↓
合并结果 → LLM 生成答案
```

### 3.4 代码实现

```python
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.node_parser import HierarchicalNodeParser
from llama_index.core.retrievers import AutoMergingRetriever

# 1. 加载文档
documents = SimpleDirectoryReader("data/").load_data()

# 2. 创建层级解析器
node_parser = HierarchicalNodeParser.from_defaults(
    chunk_sizes=[2048, 512, 128]  # 三级：大块 → 中块 → 小块
)

# 3. 创建索引
index = VectorStoreIndex.from_documents(
    documents,
    node_parser=node_parser,
)

# 4. 创建自动合并检索器
retriever = AutoMergingRetriever(
    index.as_retriever(similarity_top_k=5),
    index.storage_context,
    verbose=True,
)

# 5. 查询
nodes = retriever.retrieve("什么是句子窗口检索？")
```

---

## 四、元数据索引（Metadata Indexing）

### 4.1 一句话定义

> 为每个文档块添加结构化元数据（来源、时间、类型），支持过滤查询。

### 4.2 解决了什么问题？

混合查询需求：

```
用户查询："2025年技术部的架构方案"

纯向量搜索：只能理解"架构方案"的语义
元数据索引：可以同时过滤"2025年"和"技术部"
```

### 4.3 代码实现

```python
from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores import MetadataFilters, FilterCondition

# 1. 创建带元数据的文档
documents = [...]  # 每个文档都有 metadata

# 2. 创建索引
index = VectorStoreIndex.from_documents(documents)

# 3. 带过滤的查询
filters = MetadataFilters(
    filters=[
        {"key": "year", "value": "2025"},
        {"key": "department", "value": "技术部"},
    ],
    condition=FilterCondition.AND
)

query_engine = index.as_query_engine(filters=filters)
response = query_engine.query("最新的架构方案是什么？")
```

---

## 五、面试高频问题

### Q1：句子窗口检索和普通检索有什么区别？

**答**：普通检索直接把检索到的文本块送给 LLM，可能缺乏上下文。句子窗口检索在索引时只存单句（保证检索精度），但同时把前后 N 句存入 metadata。检索到单句后，用 metadata 中的窗口文本替换单句，送给 LLM 一个上下文丰富的文本。

### Q2：结构化索引和向量索引有什么区别？

**答**：向量索引基于语义相似度搜索，结构化索引基于元数据过滤。两者互补：先用结构化索引缩小范围（如只搜2025年的文档），再用向量索引做语义搜索。

### Q3：什么时候用句子窗口，什么时候用父子块？

**答**：句子窗口适合长文档、需要连续上下文的场景（如论文、报告）。父子块适合结构化文档、需要层次化检索的场景（如技术文档、知识库）。

### Q4：索引优化和检索优化哪个更重要？

**答**：索引优化更重要。索引优化是一次性的（离线完成），检索优化是每次查询都执行的（在线）。好的索引设计可以让检索更高效、更精准。

<hr/>

<div class="callout callout-info">
<strong>📘 背景</strong>
结构化递归检索和句子窗口检索的核心区别：前者利用文档本身的目录结构（自上而下），后者利用句子周围的语义上下文（自下而上）。两者可以组合使用——先用递归检索定位章节，再用句子窗口检索提升上下文质量。
</div>

### Q5：如何评估索引优化的效果？

**答**：三个指标：
1. **检索精度**：Top-K 结果中有多少是真正相关的
2. **上下文质量**：送给 LLM 的文本是否包含足够信息
3. **最终答案质量**：LLM 生成的答案是否准确、完整

---

## 结语

索引优化是 RAG 系统的核心竞争力。理解"怎么存"比理解"怎么搜"更重要，因为好的索引设计可以让后续的检索和生成事半功倍。建议面试前重点掌握句子窗口检索和结构化索引的原理和代码实现。

> **关键要点**：索引优化是一次性的，检索优化是每次执行的。为检索精确性而索引小块，为上下文丰富性而检索大块。
