---
title: "RAG 学习笔记：文本分块的四种武器，哪种最锋利？"
description: "深入学习 LangChain 中的四种文本分割器，通过实际运行对比和 LLM 分析，找出最适合你场景的分块策略。"
pubDate: 2025-07-20
tags: ["RAG", "LangChain", "文本分块", "Python", "AI"]
lang: "zh"
---

# RAG 学习笔记：文本分块的四种武器，哪种最锋利？

> 深入学习 LangChain 中的四种文本分割器，通过实际运行对比和 LLM 分析，找出最适合你场景的分块策略。

## 目录

- [为什么需要分块](#一为什么需要分块)
- [环境准备](#二环境准备)
- [四种分割器详解](#三四种分割器详解)
- [对比分析](#四对比分析)
- [选型建议](#五选型建议)

---

## 一、为什么需要分块？

### 三大核心原因

| 原因 | 说明 | 影响 |
|------|------|------|
| **嵌入模型限制** | 如 bge-small-zh 最多 512 token | 超出会被截断，丢失信息 |
| **LLM 上下文窗口有限** | 如 4096 token | 无法将整篇文档塞入 Prompt |
| **检索粒度要求** | 需要精准召回 | 避免"大海捞针"，提升准确率 |

### 直观理解

想象你要在一本 500 页的书里找答案。如果整本书作为一个搜索单元，效率极低。但如果按章节、段落拆分成小块，搜索就会精准得多。

**分块就是做这件事：把长文档拆成语义连贯的小片段。**

<hr/>

<div class="callout callout-info">
<strong>📘 背景</strong>
chunk_size 的选择直接影响 RAG 的检索质量。过小（< 100 字符）导致每个块缺乏语义完整性，过大（> 1000 字符）则会引入噪音并降低检索精度。经验值是 200-500 字符，配合 chunk_overlap=10%-20% 来防止语义断裂。
</div>

---

## 二、环境准备

### 技术栈

```
Python 3.12
├── LangChain (文本分割框架)
├── langchain-huggingface (嵌入模型)
├── langchain-openai (LLM 调用)
└── python-dotenv (环境变量管理)
```

### 关键依赖

```python
from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
```

### 国内网络适配

```python
# HuggingFace 镜像设置，解决国内访问问题
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
```

---

## 三、四种分块方法详解

### 方法一：CharacterTextSplitter —— 简单粗暴的"一刀切"

**原理**：用固定的分隔符将文本拆成片段，按目标大小合并。

#### 参数配置

| 参数 | 值 | 说明 |
|------|-----|------|
| `chunk_size` | 200 | 每个块的目标字符数（软限制） |
| `chunk_overlap` | 10 | 相邻块重叠字符数，防止语义断裂 |
| `separator` | `"\n\n"` | 分隔符，默认为双换行（段落分隔） |

#### 代码示例

```python
text_splitter = CharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=10,
    separator="\n\n"
)
chunks = text_splitter.split_documents(documents)
```

#### 运行结果

```
加载完成：1 个文档，2343 字符
Created a chunk of size 201, which is longer than the specified 200
分块完成：14 个块
```

### 方法二：RecursiveCharacterTextSplitter —— 智能递归的"俄罗斯套娃"

**原理**：按分隔符优先级递归拆分，尽量保持语义完整。

#### 分隔符优先级

```python
separators = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
```

#### 代码示例

```python
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=10,
    separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
)
chunks = text_splitter.split_documents(documents)
```

#### 运行结果

```
分块完成：16 个块
平均块大小：146 字符
```

### 方法三：SemanticChunker —— 语义感知的"智能裁缝"

**原理**：基于 Embedding 相似度自动找到语义断点。

#### 代码示例

```python
from langchain_experimental.text_splitter import SemanticChunker

embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-zh-v1.5",
    model_kwargs={'device': 'cpu'}
)

semantic_chunker = SemanticChunker(
    embeddings,
    breakpoint_threshold_type="percentile",
    breakpoint_threshold_amount=75
)
chunks = semantic_chunker.split_documents(documents)
```

#### 运行结果

```
分块完成：8 个块
平均块大小：293 字符
```

<hr/>

<div class="callout callout-tip">
<strong>💡 技巧</strong>
SemanticChunker 虽然语义质量最高，但计算成本也最高（需要为每个候选断点计算 Embedding 相似度）。对于大规模文档，建议先用 RecursiveCharacterTextSplitter 做粗分，再对每个粗分块内部用 SemanticChunker 细分——这种"两阶段"策略可以兼顾效率和质量。
</div>

### 方法四：MarkdownHeaderTextSplitter —— 结构化文档的"专属武器"

**原理**：按 Markdown 标题层级拆分，保持文档结构。

#### 代码示例

```python
headers_to_split_on = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
]

markdown_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on
)
chunks = markdown_splitter.split_text(markdown_text)
```

#### 运行结果

```
分块完成：12 个块
每个块包含标题元数据
```

---

## 四、对比分析

### 4.1 性能对比

| 分割器 | 块数量 | 平均块大小 | 语义完整性 | 适用场景 |
|--------|--------|-----------|-----------|---------|
| **CharacterTextSplitter** | 14 | 167 字符 | ⭐⭐ | 简单文本、快速原型 |
| **RecursiveCharacterTextSplitter** | 16 | 146 字符 | ⭐⭐⭐ | 通用场景、中文文档 |
| **SemanticChunker** | 8 | 293 字符 | ⭐⭐⭐⭐⭐ | 语义要求高、长文档 |
| **MarkdownHeaderTextSplitter** | 12 | 195 字符 | ⭐⭐⭐⭐ | Markdown 文档 |

### 4.2 LLM 分析结论

通过调用 LLM 进行专业分析，得出以下结论：

1. **RecursiveCharacterTextSplitter** 是最推荐的通用方案
2. **SemanticChunker** 在语义完整性上表现最好，但计算成本高
3. **MarkdownHeaderTextSplitter** 适合结构化文档
4. **CharacterTextSplitter** 适合快速原型验证

---

## 五、选型建议

### 5.1 决策树

```
文档类型是什么？
├─ Markdown 文档
│  └─ MarkdownHeaderTextSplitter
├─ 长文档、语义要求高
│  └─ SemanticChunker
├─ 通用场景
│  └─ RecursiveCharacterTextSplitter
└─ 快速原型
   └─ CharacterTextSplitter
```

### 5.2 最佳实践

| 实践 | 说明 | 重要性 |
|------|------|--------|
| **保持语义完整** | 避免在句子中间断开 | ⭐⭐⭐⭐⭐ |
| **设置合适的 overlap** | 防止上下文丢失 | ⭐⭐⭐⭐ |
| **根据文档类型选择** | 不同文档用不同策略 | ⭐⭐⭐⭐ |
| **测试不同 chunk_size** | 找到最优大小 | ⭐⭐⭐ |

---

## 结语

文本分块是 RAG 系统的第一步，也是最关键的一步。选择合适的分块策略，比优化 Embedding 模型更能提升检索效果。建议读者在实践中多尝试不同的方法，找到最适合自己场景的方案。

> **关键要点**：没有最好的分块策略，只有最适合的分块策略。根据文档类型和业务场景选择，保持语义完整性是第一优先级。
