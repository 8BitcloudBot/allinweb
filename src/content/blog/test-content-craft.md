---
title: "内容编排实验：表格、代码块与标注卡片"
description: "演示增强后的排版系统——代码块语言标签、标注卡片（info/warning/tip）、表格条纹、键盘键帽样式。"
pubDate: 2026-05-15
tags: ["排版", "CSS", "设计", "实验"]
lang: "zh"
readingTime: 3
---

这是一篇用来测试排版系统的实验文章。下面的每个区块都展示了不同的内容编排能力。

## 代码块增强

代码块现在会自动在右上角显示语言标签，采用更舒适的背景色和行高：

```python
def hybrid_search(query: str, top_k: int = 3):
    vector_results = vectorstore.similarity_search(query, k=top_k)
    bm25_results = bm25_retriever.invoke(query)
    return rrf_merge(vector_results, bm25_results)[:top_k]
```

```javascript
// 语言标签会自动识别
const metrics = {
  confidence: 0.87,
  sources: ['宫保鸡丁', '水煮牛肉'],
  elapsed: 2141
};

function renderBar(score) {
  const filled = '█'.repeat(Math.round(score * 10));
  const empty = '░'.repeat(10 - Math.round(score * 10));
  return `${filled}${empty} ${score}`;
}
```

```bash
# 部署命令
docker compose up -d --build
docker compose logs -f chefmate
```

<div class="callout callout-info">
<strong>💡 关于语言标签</strong>
代码块右上角自动显示语言名称（如 Python、JavaScript、Bash）。这是通过 Shiki 渲染时注入的 `data-language` 属性实现的，CSS 伪元素 `::before` 将其展示为标签。
</div>

## 标注卡片系统

三种标注卡片，适用于不同的信息层级需求。

<div class="callout callout-info">
<strong>📘 Info</strong>
信息提示——适合补充说明、背景介绍、技术细节。背景为淡紫色，左侧紫色边框。
</div>

<div class="callout callout-warning">
<strong>⚠️ Warning</strong>
警告提示——适合注意事项、常见陷阱、需要特别关注的点。背景为淡橙色，左侧橙色边框。
</div>

<div class="callout callout-tip">
<strong>✅ Tip</strong>
技巧提示——适合最佳实践、优化建议、效率技巧。背景为淡绿色，左侧绿色边框。
</div>

## 表格增强

表格现在有交替行背景色、大写表头、圆角容器。

| 指标 | 纯向量检索 | 混合检索 (向量+BM25) | 提升 |
|------|-----------|-------------------|------|
| Recall@3 | 0.72 | 0.89 | +23.6% |
| Precision@3 | 0.68 | 0.81 | +19.1% |
| 平均检索耗时 | 45ms | 52ms | +15% |
| 冷门菜名匹配 | 低 | 高 | 显著 |

<div class="callout callout-tip">
<strong>关键结论</strong>
混合检索在 Recall 和 Precision 上都有显著提升，尤其在冷门菜名（如"柱候牛腩"、"蛏抱蛋"）的匹配上，BM25 的关键词能力弥补了向量模型的不足。
</div>

## 键盘键帽样式

适用于快捷键文档：

- 保存文件：<kbd>Ctrl</kbd> + <kbd>S</kbd>
- 搜索：<kbd>Ctrl</kbd> + <kbd>K</kbd>
- 打开终端：<kbd>Ctrl</kbd> + <kbd>`</kbd>
- 切换面板：<kbd>Cmd</kbd> + <kbd>Shift</kbd> + <kbd>P</kbd>

## 引用块

> 好的排版不会引起注意，它只是让内容更容易被阅读。
>
> 排版的目标不是装饰，而是清晰。

## 水平分割线

分割线使用了渐变效果，不再是纯色直线。

## 列表样式

列表标记（marker）使用了 Notion 紫色，带半透明效果。

### 无序列表

- 数据准备：文档加载与按标题分块
- 向量索引：bge-small-zh-v1.5 嵌入 + FAISS 持久化
- 混合检索：向量语义匹配 + BM25 关键词 + RRF 融合
- LLM 生成：查询路由 → 查询改写 → 三种 Prompt 模板

### 有序列表

1. 首次构建索引（下载模型 ~30s）
2. 启动 FastAPI 服务
3. 浏览器访问 `/chefmate/`
4. 输入问题，获得带 RAG 指标的回答
