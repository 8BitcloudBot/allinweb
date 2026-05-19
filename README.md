# AllInWeb

**ChefMate RAG V1 + GraphRAG V2** — 智能食谱问答系统 + **个人技术网站** 的单一工程整合。

**在线地址**：[vincentbuilds.fun](https://vincentbuilds.fun)
- ChefMate RAG V1：[vincentbuilds.fun/chefmate](https://vincentbuilds.fun/chefmate)
- ChefMate GraphRAG V2：[vincentbuilds.fun/chefmate/#graphrag](https://vincentbuilds.fun/chefmate/#graphrag)

---

## 工程结构

```
AllInWeb/
├── src/                     # Astro 前端（个人站 + ChefMate V1/V2 页面）
├── chefmate/                # V1 FastAPI 后端（RAG 系统）
│   ├── server.py            # API 入口
│   ├── generator.py         # LLM Prompt（DeepSeek V4）
│   ├── retriever.py         # 混合检索（FAISS + BM25 + 加权 RRF）
│   ├── loader.py            # 菜谱加载与分块
│   ├── indexer.py           # FAISS 向量索引
│   ├── metrics.py           # RAG 质量指标
│   ├── validator.py         # 答案幻觉检测
│   ├── query_analyzer.py    # 查询约束提取
│   ├── query_router.py      # 查询路由
│   ├── conversation.py      # 多轮对话上下文
│   └── security.py          # 限流与输入校验
├── chefmate-graphrag/       # V2 GraphRAG 后端
│   ├── server.py            # FastAPI 入口（/api/graphchat）
│   ├── retrieval/
│   │   ├── hybrid.py        # Milvus + BM25 + 加权 RRF
│   │   ├── graph_rag.py     # Neo4j 多跳推理 + 子图提取
│   │   └── query_router.py  # 三策略智能路由
│   ├── generation/
│   │   └── generator.py     # 四种 Prompt 模板 + HyDE
│   └── shared/
│       └── context_budget.py
├── data/                    # 360 个中文菜谱
├── config.py                # V1 集中配置
├── main.py                  # RecipeRAGSystem 编排器
├── benchmark.py             # 综合测试套件（27 条）
├── deploy.sh                # 前端部署
└── sync.sh                  # 多端同步（阿里云 + 腾讯云）
```

## 跨云分布式架构

```
用户 → vincentbuilds.fun (Aliyun Nginx)
         ├── /api/*       → Aliyun 2C1G  (ChefMate RAG V1)
         └── /api/graphchat → Tencent 4C4G (GraphRAG V2: Neo4j + Milvus + API)
```

| 云服务 | 规格 | 承载 |
|--------|------|------|
| 阿里云 | 2C1G 40G | Nginx + V1 API + 前端静态文件 |
| 腾讯云 | 4C4G 40G | Neo4j + Milvus + etcd + MinIO + GraphRAG API |

## 技术栈

| 层级 | V1 (RAG) | V2 (GraphRAG) |
|------|----------|---------------|
| 前端 | Astro v6 + Tailwind CSS v4 | 同上 |
| 后端 | FastAPI (Python 3.12) | FastAPI (Python 3.12) |
| 大模型 | DeepSeek V4 | DeepSeek V4 |
| 向量化 | BAAI/bge-**base**-zh-v1.5 (768 维) | BAAI/bge-**base**-zh-v1.5 (768 维) |
| 向量库 | FAISS (IVF + Flat) | Milvus 2.5 |
| 图数据库 | — | Neo4j 5.26 |
| 关键词 | BM25 (rank-bm25) | BM25 (rank-bm25) |
| 融合排序 | 加权 RRF | 加权 RRF |
| 查询增强 | HyDE 兜底 | HyDE 兜底 |
| 路由 | LLM 路由 | 三策略智能路由 (规则 + LLM) |
| 模型分发 | HuggingFace | ModelScope (国内镜像) |
| 部署 | Docker + Nginx | Docker Compose (5 容器) |

## V1 vs V2

| 维度 | V1 (ChefMate-RAG) | V2 (ChefMate-GraphRAG) |
|------|-------------------|------------------------|
| 检索方式 | FAISS + BM25 | Milvus + BM25 + 图检索 |
| 知识图谱 | — | Neo4j (360 Recipe, 1195 Ingredient, 12664 关系) |
| 推理能力 | 文本匹配 | 多跳推理 + 子图提取 |
| 查询路由 | LLM 简单分类 | 三策略 (规则引擎 + LLM 兜底) |
| 降级策略 | — | 图 RAG → 组合 → 传统混合 |
| 召回增强 | — | HyDE 生成假想文档兜底 |

## 快速开始

### 环境要求

- Node.js ≥ 22
- Python 3.12
- Docker + Docker Compose (V2)
- `.env` 中配置 `DEEPSEEK_API_KEY`

### V1 后端

```bash
cp .env.example .env
uv sync
uv run uvicorn chefmate.server:app --host 0.0.0.0 --port 8000
```

### V2 后端 (需要 Docker)

```bash
cd chefmate-graphrag
cp .env.example .env   # 填入 DEEPSEEK_API_KEY 和 NEO4J_PASSWORD
docker compose up -d    # 启动 Neo4j + Milvus + etcd + MinIO + API
curl http://localhost:8001/api/graphrag/health
```

### 前端

```bash
npm install
npm run dev             # http://localhost:4321
```

### 测试

```bash
# V1 API
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"宫保鸡丁怎么做"}'

# V2 GraphRAG
curl -X POST http://localhost:8001/api/graphchat \
  -H "Content-Type: application/json" \
  -d '{"query":"鸡肉配什么蔬菜好"}'

# Benchmark
python3 benchmark.py
```

## 部署

### 前端部署

```bash
./deploy.sh             # 构建 + 推送到阿里云 Nginx
```

### 多端同步

```bash
./sync.sh server        # → GitHub + 阿里云
./sync.sh tencent       # → GitHub + 腾讯云
./sync.sh all           # → 三端全同步
```

## API 接口

| 版本 | 方法 | 路径 | 说明 |
|------|------|------|------|
| V1 | POST | `/api/chat` | RAG 问答 |
| V1 | POST | `/api/chat/stream` | SSE 流式 |
| V1 | GET | `/api/health` | 健康检查 |
| V2 | POST | `/api/graphchat` | GraphRAG 问答 |
| V2 | POST | `/api/graphchat/stream` | SSE 流式 |
| V2 | GET | `/api/graphrag/health` | 健康检查 |

## 安全措施

- API Key 仅存服务端 `.env`（不在代码中暴露）
- 腾讯云端口仅允许阿里云 IP 白名单访问
- UFW + fail2ban + SSH 密钥认证（腾讯云）
- CORS 仅允许 `vincentbuilds.fun`
- slowapi 限流
- SSL 证书（Let's Encrypt + Nginx）
- Pydantic 输入校验

## 相关仓库

- [ChefMate-RAG](https://github.com/8BitcloudBot/ChefMate-RAG) — V1 独立仓库
- [ChefMate-GraphRAG](https://github.com/8BitcloudBot/ChefMate-GraphRAG) — V2 独立仓库

## 开源协议

MIT © Vincent Hu
