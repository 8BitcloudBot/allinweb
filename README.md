# AllInWeb

**ChefMate RAG 智能食谱问答系统** + **个人技术网站** 的单一工程整合。

**在线地址**：[vincentbuilds.fun](https://vincentbuilds.fun) · **ChefMate**：[vincentbuilds.fun/chefmate](https://vincentbuilds.fun/chefmate)

---

## 工程结构

```
AllInWeb/
├── src/              # Astro 前端（个人站 + ChefMate 页面）
├── chefmate/         # FastAPI 后端（RAG 系统）
│   ├── server.py     # API 入口
│   ├── generator.py  # LLM Prompt（DeepSeek V4）
│   ├── retriever.py  # 混合检索（FAISS + BM25 + RRF）
│   ├── loader.py     # 菜谱加载与分块
│   ├── indexer.py    # FAISS 向量索引
│   ├── metrics.py    # RAG 质量指标
│   ├── validator.py  # 答案幻觉检测
│   ├── query_analyzer.py  # 查询约束提取
│   ├── conversation.py    # 多轮对话上下文
│   └── security.py   # 限流与输入校验
├── data/             # 362 个中文菜谱（Markdown）
├── config.py         # 集中配置
├── main.py           # RecipeRAGSystem 编排器
├── deploy.sh         # 阿里云一键部署
└── sync.sh           # 三端同步脚本
```

## 技术栈

| 层级 | 技术 |
|-------|-----------|
| 前端 | Astro v6、Tailwind CSS v4 |
| 后端 | FastAPI（Python 3.12）|
| 大模型 | DeepSeek V4（deepseek-chat）|
| 向量化 | BAAI/bge-small-zh-v1.5（384 维）|
| 向量库 | FAISS（IVF + Flat）|
| 关键词检索 | BM25（rank-bm25）|
| 融合排序 | RRF（Reciprocal Rank Fusion）|
| 部署 | Docker + Nginx + GitHub Actions |
| 包管理 | npm（前端）+ uv（后端）|

## 快速开始

### 环境要求

- Node.js ≥ 22
- Python 3.12（通过 uv 管理）
- `.env` 中配置 `DEEPSEEK_API_KEY`

```bash
# 克隆仓库
git clone git@github.com:8BitcloudBot/allinweb.git
cd allinweb

# 后端启动
cp .env.example .env   # 填入你的 DEEPSEEK_API_KEY
uv sync
uv run uvicorn chefmate.server:app --host 0.0.0.0 --port 8000

# 前端启动（另开终端）
npm install
npm run dev             # http://localhost:4321
```

### 测试 API

```bash
curl http://localhost:8000/api/health

curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"宫保鸡丁怎么做"}'
```

## 部署

### 阿里云一键部署

```bash
./deploy.sh
```

同步前端静态文件 + 后端源码到服务器，重建 Docker 容器，重载 Nginx。

### 三端同步

```bash
./sync.sh server   # → GitHub + 阿里云
./sync.sh local    # → 仅推 GitHub
./sync.sh all      # → 三端全同步（默认）
```

### 向量索引隔离

各环境独立维护 FAISS 索引，防止相互污染：

| 环境 | 索引路径 | 构建时机 |
|------------|-----------|---------------|
| 本地开发 | `vector_index/` | 首次 `uv run` |
| GitHub CI | 容器内构建 | `docker compose build` |
| 阿里云 | `/var/www/vincentbuilds-api/vector_index/` | Docker 启动时 |

**注意**：切勿在环境间复制 `vector_index/` 目录。各环境从菜谱数据独立构建。

## RAG 流水线

```
用户查询 → 多轮对话解析 → 约束提取 → 查询路由（LLM）
  → 混合检索（FAISS + BM25 + RRF + 元数据筛选）
  → 父文档还原 → 上下文预算管理
  → LLM 生成（三种 Prompt 模板）
  → 答案验证 → 指标计算 → 流式返回
```

## API 接口

| 方法 | 路径 | 限流 |
|--------|------|------------|
| POST | `/api/chat` | 10 次/分钟/IP |
| POST | `/api/chat/stream` | SSE 流式 |
| GET | `/api/health` | 不限制 |
| GET | `/api/history` | 30 次/分钟/IP |
| POST | `/api/feedback` | 20 次/分钟/IP |

## 安全措施

- API Key 仅存服务端 `.env`（权限 chmod 600）
- 后端端口 8000 仅绑定 `127.0.0.1`，公网不可达
- CORS 仅允许 `vincentbuilds.fun`
- slowapi 限流（10 次/分钟/IP）
- SSL 证书（Let's Encrypt + Nginx）
- Pydantic 输入校验 + XSS 检测

## 开源协议

MIT © Vincent Hu
