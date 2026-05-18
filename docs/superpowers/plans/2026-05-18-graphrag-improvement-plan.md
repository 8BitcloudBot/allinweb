# ChefMate GraphRAG 改进方案

> 基于 `2026-05-18-graphrag-dumbness-analysis.md` 的 10 个根因
> 生成时间：2026-05-18

---

## 改进 1：GraphRAG 结果结构化

**现状：** `_paths_to_documents()` 将路径压成一行文字，节点属性全部丢失
**方案：** 新增 `_path_to_readable()` 生成语义化描述，metadata 保留完整结构化 JSON
**文件：** `retrieval/graph_rag.py`
**工时：** 40 行，30 分钟 | **优先级：** P0

---

## 改进 2：Subgraph 返回多条 Document

**现状：** 整个子图压缩为 1 个统计摘要
**方案：** 遍历 connected_nodes/relationships 各生成独立 Document
**文件：** `retrieval/graph_rag.py`
**工时：** 50 行，30 分钟 | **优先级：** P0

---

## 改进 3：补全 BM25 混合检索

**现状：** `hybrid_search()` 是无 BM25 的纯向量搜索
**方案：** 集成 rank_bm25 + jieba 分词，RRF 融合向量+BM25 结果
**文件：** `retrieval/hybrid.py`
**工时：** 80 行，45 分钟 | **优先级：** P0

---

## 改进 4：减少 LLM 调用次数

**现状：** 每次查询 2-3 次 LLM 调用，延迟 6-7s
**方案：** 扩大 `_FAST_ROUTE_RULES` 规则覆盖，命中规则直接跳过 LLM 分析
**文件：** `retrieval/query_router.py`
**工时：** 30 行，20 分钟 | **优先级：** P1

---

## 改进 5：修复置信度计算

**现状：** graph path relevance_score 可能 > 1，无裁剪
**方案：** `min(max(s, 0), 1)` 裁剪所有分数
**文件：** `shared/metrics.py`
**工时：** 15 行，10 分钟 | **优先级：** P1

---

## 改进 6：对话上下文注入

**现状：** 对话历史未参与查询理解和回答生成
**方案：** server.py 拼接 context 到 query，generator prompt 注入对话背景
**文件：** `server.py`, `generation/generator.py`, `shared/conversation.py`
**工时：** 40 行，30 分钟 | **优先级：** P1

---

## 改进 7：Prompt 全中文化

**现状：** generator prompt 中英混杂
**方案：** 4 个 `_generate_*` 方法的 prompt 全部重写为中文
**文件：** `generation/generator.py`
**工时：** 100 行，15 分钟 | **优先级：** P1

---

## 改进 8：Combined 策略 RRF 融合

**现状：** 简单拼接 + 哈希去重
**方案：** 使用 RRF (k=60) 融合 traditional + graph_rag 结果
**文件：** `retrieval/query_router.py`
**工时：** 25 行，15 分钟 | **优先级：** P1

---

## 改进 9：接入 AnswerValidator

**现状：** validator 已初始化但从未调用
**方案：** 在 `/api/graphchat` 回答生成后调用 validate，追加幻觉警告
**文件：** `server.py`
**工时：** 10 行，10 分钟 | **优先级：** P1

---

## 改进 10：Graph Schema 增强

**现状：** 只有 3 种关系类型
**方案：** Step 1 自动构建 SIMILAR_TO（共享食材≥3），Step 2 人工规则 SUBSTITUTE_FOR
**文件：** `scripts/build_graph.py`, `graph/schema.py`
**工时：** 90 行，50 分钟 | **优先级：** P2

---

## 目标指标

| 指标 | 当前 | 目标 |
|------|------|------|
| 简单查询延迟 | ~4.5s | ≤3.5s |
| 图谱查询延迟 | ~6.3s | ≤5s |
| 推荐查询召回率 | ~50% | ≥80% |
| 图谱推理有效率 | ~30% | ≥70% |
| 回答语言一致性 | ~60% 中文 | 100% 中文 |
| 幻觉率 | 未测量 | ≤5% |
| 置信度异常 | 存在 | 0 |
