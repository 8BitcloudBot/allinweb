# Tencent Cloud 部署计划 — ChefMate GraphRAG 分布式架构

> 将 GraphRAG 后端全栈迁移至腾讯云 2核4G，Aliyun 仅保留 V1 API + Nginx

---

## Phase 1：Tencent 服务器初始化

### 1.1 购买规格

- 型号：2核 4GB 内存，40GB 系统盘
- 地域：上海（与 Aliyun 深圳跨省延迟 15-20ms）
- 镜像：**Ubuntu22.04-Docker26 26.1.3**（Docker CE 预装）
- 安全组开放端口：22 (SSH)、80/443（后续）、8001（Aliyun IP 白名单）

### 1.2 环境搭建

```bash
ssh root@<TENCENT_IP>

# 更新系统
apt update && apt upgrade -y

# 安装依赖
apt install -y curl git python3-pip rsync nginx

# 确认 Docker
docker --version  # 26.x
docker compose version

# 创建 swap（4GB 保底）
dd if=/dev/zero of=/swapfile bs=1M count=4096
chmod 600 /swapfile
mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# 创建目录
mkdir -p /var/www/chefmate-graphrag/{runtime,data}
```

### 1.3 同步代码

```bash
# 从本地 Mac 同步 chefmate-graphrag/ 到腾讯云
rsync -avz --exclude='__pycache__' --exclude='.venv' --exclude='runtime' \
  -e "ssh" \
  ~/Documents/OpenCode/AllInWeb/chefmate-graphrag/ \
  root@<TENCENT_IP>:/var/www/chefmate-graphrag/

# 同步菜谱数据
rsync -avz \
  ~/Documents/OpenCode/AllInWeb/data/ \
  root@<TENCENT_IP>:/var/www/chefmate-graphrag/data/
```

### 1.4 创建 .env

```bash
ssh root@<TENCENT_IP> '
cat > /var/www/chefmate-graphrag/.env << EOF
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=chefmate_tencent_2024
MILVUS_HOST=milvus
MILVUS_PORT=19530
DEEPSEEK_API_KEY=sk-xxx
HF_ENDPOINT=https://hf-mirror.com
DAILY_QUOTA=200
MONTHLY_QUOTA=3000
EOF
chmod 600 /var/www/chefmate-graphrag/.env
'
```

---

## Phase 2：GraphRAG 全栈部署

### 2.1 Docker Compose

部署 `chefmate-graphrag/docker-compose.yml` 用于 Tencent 环境（完整的 Neo4j + Milvus + etcd + minio + API）：

```yaml
services:
  neo4j:
    image: neo4j:5.26-community
    ports:
      - "127.0.0.1:7474:7474"
      - "127.0.0.1:7687:7687"
    environment:
      NEO4J_AUTH: neo4j/chefmate_tencent_2024
      NEO4J_server_memory_heap_initial__size: 512m
      NEO4J_server_memory_heap_max__size: 1G
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

  etcd:
    image: quay.io/coreos/etcd:v3.5.5
    environment:
      ETCD_AUTO_COMPACTION_MODE: revision
      ETCD_AUTO_COMPACTION_RETENTION: "1000"
      ETCD_QUOTA_BACKEND_BYTES: "4294967296"
    volumes:
      - etcd_data:/etcd
    command: etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd

  minio:
    image: minio/minio:RELEASE.2023-03-20T20-16-18Z
    environment:
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
    volumes:
      - minio_data:/minio_data
    command: minio server /minio_data --console-address ":9001"

  milvus:
    image: milvusdb/milvus:v2.5.4
    command: ["milvus", "run", "standalone"]
    ports:
      - "127.0.0.1:19530:19530"
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
      MINIO_ACCESS_KEY_ID: minioadmin
      MINIO_SECRET_ACCESS_KEY: minioadmin
    volumes:
      - milvus_data:/var/lib/milvus
    depends_on:
      - etcd
      - minio

  graphrag-api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "127.0.0.1:8001:8000"
    depends_on:
      - neo4j
      - milvus
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: chefmate_tencent_2024
      MILVUS_HOST: milvus
      MILVUS_PORT: 19530
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY}
      HF_ENDPOINT: https://hf-mirror.com
    volumes:
      - ./runtime:/app/runtime
    restart: unless-stopped

volumes:
  neo4j_data:
  neo4j_logs:
  etcd_data:
  minio_data:
  milvus_data:
```

### 2.2 启动所有容器

```bash
cd /var/www/chefmate-graphrag
docker compose pull   # 拉取 neo4j/milvus/etcd/minio 镜像
docker compose up -d  # 启动全部 5 个服务
```

### 2.3 云端独立构建知识图谱

```bash
# 等待 Neo4j 就绪
sleep 30

# 构建知识图谱（云端独立数据）
docker exec chefmate-graphrag-graphrag-api-1 python3 -u /app/build_remote.py
```

### 2.4 Milvus 向量索引构建

API 容器启动后自动构建（lifespan 逻辑）：
- 从 Neo4j 加载 360 菜谱
- 生成 4112 个文档块
- `BAAI/bge-small-zh-v1.5` 嵌入
- 插入 Milvus（COSINE 索引）

### 2.5 验证

```bash
curl http://127.0.0.1:8001/api/graphrag/health
# → {"status":"ok","errors":{}}

curl -X POST http://127.0.0.1:8001/api/graphchat \
  -H 'Content-Type: application/json' \
  -d '{"query":"鸡肉配什么蔬菜"}'
# → routing: graph_rag, nodes > 0
```

---

## Phase 3：Aliyun Nginx 跨云代理

### 3.1 配置安全组

**Tencent 安全组**：允许 `47.106.38.219`（Aliyun 固定 IP）访问 `8001` 端口。

### 3.2 更新 Aliyun Nginx

将 `/etc/nginx/conf.d/vincentbuilds.conf` 中的 GraphRAG 路由改为指向 Tencent：

```nginx
# GraphRAG API (proxied to Tencent Cloud)
location /api/graphchat {
    proxy_pass http://<TENCENT_IP>:8001/api/graphchat;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_buffering off;
    proxy_read_timeout 120s;
    proxy_connect_timeout 10s;
}

location /api/graphchat/stream {
    proxy_pass http://<TENCENT_IP>:8001/api/graphchat/stream;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 120s;
}

location /api/graphrag/ {
    proxy_pass http://<TENCENT_IP>:8001/api/graphrag/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

执行：
```bash
nginx -t && nginx -s reload
```

### 3.3 验证全链路

```bash
# 从本地测试
curl -sk -X POST https://vincentbuilds.fun/api/graphchat \
  -H 'Content-Type: application/json' \
  -d '{"query":"鸡肉配什么蔬菜"}'
```

---

## Phase 4：CI/CD 更新

### 4.1 GitHub Actions 新增 Tencent 部署 Job

在 `.github/workflows/deploy.yml` 中新增：

```yaml
deploy-tencent:
  runs-on: ubuntu-latest
  needs: build-frontend
  steps:
    - uses: actions/checkout@v4
    - name: Deploy GraphRAG to Tencent
      uses: appleboy/ssh-action@v1
      with:
        host: ${{ secrets.TENCENT_SERVER_HOST }}
        username: root
        key: ${{ secrets.TENCENT_SSH_KEY }}
        script: |
          rsync -avz --exclude='__pycache__' --exclude='.venv' --exclude='runtime' \
            ${{ github.workspace }}/chefmate-graphrag/ /var/www/chefmate-graphrag/
          cd /var/www/chefmate-graphrag
          docker compose up -d --build graphrag-api
```

### 4.2 GitHub Secrets 新增

| Secret | 值 |
|--------|-----|
| `TENCENT_SERVER_HOST` | 腾讯云公网 IP |
| `TENCENT_SSH_KEY` | SSH 私钥内容 |

### 4.3 本地 sync.sh 更新

新增 `tencent` 模式：
```bash
tencent)
    rsync -avz --exclude='__pycache__' --exclude='.venv' --exclude='runtime' \
      chefmate-graphrag/ root@$TENCENT_HOST:/var/www/chefmate-graphrag/
    ssh root@$TENCENT_HOST "cd /var/www/chefmate-graphrag && docker compose up -d --build graphrag-api"
    ;;
```

---

## Phase 5：验证检查清单

| # | 验证项 | 方式 |
|---|--------|------|
| 1 | Tencent Docker 全部容器运行 | `docker ps` |
| 2 | Neo4j 含 360 菜谱 | HTTP API 查询 |
| 3 | Milvus 索引构建完成 | `/api/graphrag/stats` |
| 4 | GraphRAG API 健康 | `/api/graphrag/health` |
| 5 | 图谱查询返回结果 | `curl /api/graphchat "鸡肉配什么蔬菜"` |
| 6 | 混合/推荐查询可用 | `curl /api/graphchat "推荐几个菜"` |
| 7 | Aliyun Nginx 代理 $ | `curl -sk vincentbuilds.fun/api/graphchat` |
| 8 | 前端 GraphRAG 标签可用 | 打开网站，🕸️ 标签发送查询 |
| 9 | V1 API 不受影响 | `curl vincentbuilds.fun/api/chat` |
|10 | CI/CD 自动部署 | push → GitHub Actions → Tencent |

---

## Aliyun 清理后状态

| 指标 | 清理前 | 清理后 |
|------|--------|--------|
| 可用内存 | 91MB | 830MB |
| 磁盘空间 | 18GB/40GB | 25GB/40GB |
| Docker 容器 | 3（含故障） | 1（稳定） |
| Docker 镜像 | 3（11.6GB） | 1（5.55GB） |
| Swap | 2GB | 2GB（持久化） |

**当前 Aliyun 只跑 V1 ChefMate RAG + Nginx，内存充足。**

---

## 资源分布

```
┌─────────────────────────────────────────────────────┐
│              vincentbuilds.fun (Nginx HTTPS)         │
│                                                      │
│  ┌──────────────┐    ┌─────────────────────────────┐ │
│  │ Aliyun 2GB   │    │ Tencent 4GB                 │ │
│  │              │    │                             │ │
│  │ V1 API :8000 │    │ Neo4j :7687    Milvus :19530│ │
│  │ Nginx static │    │ GraphRAG API :8001          │ │
│  │              │    │ etcd :2379    minio :9000   │ │
│  │ /api/  → V1  │◄───│ /api/graphchat → proxy     │ │
│  └──────────────┘    └─────────────────────────────┘ │
│                                                      │
│  前端 static files                                   │
│  /api/graphchat → Tencent IP:8001                    │
└─────────────────────────────────────────────────────┘
```
