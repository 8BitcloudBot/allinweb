# ChefMate GraphRAG 测试报告

> 生成时间：2026-05-19 02:00
> 测试方法：40 条覆盖查询 × 12 个类别
> 服务状态：Neo4j 360 Recipe + 1195 Ingredient + 1733 SIMILAR_TO | Milvus 4112 chunks

---

## 一、测试结果

| 类别 | 查询数 | graph_rag | combined | hybrid | 有效 | 失败 |
|------|--------|-----------|----------|--------|------|------|
| A 简单菜谱 | 5 | 0 | 0 | 5 | 5 | 0 |
| B 推荐列表 | 5 | 0 | 0 | 5 | 5 | 0 |
| C 搭配推理 | 3 | 2 | 0 | 1 | 3 | 0 |
| D 替代推理 | 3 | 3 | 0 | 0 | 3 | 0 |
| E 相似推理 | 2 | 2 | 0 | 0 | 2 | 0 |
| F 组合查询 | 3 | 0 | 2 | 1 | 3 | 0 |
| G 份量场景 | 2 | 0 | 0 | 2 | 2 | 0 |
| H 难度属性 | 3 | 0 | 0 | 3 | 3 | 0 |
| I 营养健康 | 3 | 0 | 0 | 3 | 3 | 0 |
| J 烹饪知识 | 3 | 1 | 0 | 2 | 3 | 0 |
| K 对话上下文 | 3 | 0 | 0 | 3 | 3 | 0 |
| L 边界情况 | 5 | 0 | 0 | 5 | 5 | 0 |
| **合计** | **40** | **8** | **2** | **30** | **40** | **0** |

**整体有效率：100%**（40/40）

---

## 二、修复项清单（已完成）

| # | 问题 | 文件 | 修复内容 |
|---|------|------|----------|
| P0-1 | fast_route 上下文污染 | `query_router.py:61` | 匹配前去除 `[对话上下文]` 后缀 |
| P0-2 | SIMILAR_TO 实体提取不精确 | `graph_rag.py:82` | prompt 约束"使用完整菜名，不要截取" |
| P0-3 | 子图节点属性丢失 | `graph_rag.py:349` | `node.get("properties",{})` → 直接读 dict 顶层 |
| P0-4 | graph_canvas fallback 重置 | `metrics.py:33` | fallback 时保持 search_source 与 route_strategy 一致 |
| P0-5 | SIMILAR_TO 查询因邻居数超限返回空 | `graph_rag.py:236` | 移除 `WHERE size(neighbors) <= 50` 过滤 |
| P1-1 | graph_rag fallback 标记错误 | `query_router.py:130` | fallback 时改 route_strategy 为 HYBRID |
| P1-2 | 对话上下文菜名提取 | `server.py:169` | 从 graph_rag 回答中提取菜名存入 last_recommended |
| P1-3 | graph_rag 空结果提前判断 | `graph_rag.py:266` | 全部 subgraph_empty 时返回空列表触发 fallback |
| P1-4 | 通用烹饪知识 fallback | `generator.py` | 增加无数据时的通用知识回答层 |

---

## 三、关键改进效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 整体有效率 | 65% | **100%** |
| simple/detail 路由正确率 | ~15% | **100%** |
| SIMILAR_TO 查询 | 全部失败 | **全部成功** |
| graph_rag 空结果幻觉 | 频繁 | **消除** |
| 对话上下文指代 | 失败 | **正常** |
| 难度信息显示 | 缺失 | **完整** |

---

## 四、路由分布

| 策略 | 查询数 | 占比 |
|------|--------|------|
| hybrid_traditional | 30 | 75% |
| graph_rag | 8 | 20% |
| combined | 2 | 5% |

简单查询正确走 hybrid（1-3s），图推理查询走 graph_rag（3-5s），组合查询走 combined（4-6s）。
