# 生产部署计划审查与优化建议

> 审查对象：`docs/superpowers/plans/2026-05-18-production-deploy.md`
> 审查时间：2026-05-19

---

## 一、路径不一致问题（必须修复）

### 问题 1：rsync 目标路径不一致

原计划中 rsync 目标路径混乱：

| 步骤 | 目标路径 | 问题 |
|------|----------|------|
| 2.3 rsync | `/var/www/chefmate-graphrag/` | 独立目录 |
| 2.2 docker-compose | `./chefmate-graphrag` | 相对于 docker-compose.yml |
| 4.1 CI/CD | `/var/www/vincentbuilds-api/chefmate-graphrag/` | 在 API 目录内 |

三个路径不一致，docker-compose 找不到代码。

**修复**：统一为 `/var/www/vincentbuilds-api/chefmate-graphrag/`，与 V1 的 `chefmate/` 同级。

### 问题 2：build_graph.py 执行环境

原计划：
```bash
cd /var/www/chefmate-graphrag
echo y | uv run python scripts/build_graph.py
```

服务器上没有 `uv`，且本地 venv 的包在服务器上不可用。

**修复**：在 Docker 容器内执行：
```bash
docker exec -it graphrag-api python scripts/build_graph.py
```

### 问题 3：.env 文件命名混乱

原计划创建 `.env.graphrag`，但 docker-compose 的 `${NEO4J_PASSWORD}` 从主 `.env` 读取。

**修复**：将变量追加到主 `.env` 文件：
```bash
cat >> /var/www/vincentbuilds-api/.env << 'EOF'
NEO4J_PASSWORD=<强密码>
DEEPSEEK_API_KEY=<生产key>
EOF
```

---

## 二、docker-compose 优化

### 问题 4：缺少生产可靠性配置

原配置缺少 `restart`、`healthcheck`、`logging`。

**修复**：
```yaml
neo4j:
  image: neo4j:5.26-community
  restart: unless-stopped
  ports:
    - "127.0.0.1:7474:7474"
    - "127.0.0.1:7687:7687"
  environment:
    NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
    NEO4J_server_memory_heap_initial__size: 512m
    NEO4J_server_memory_heap_max__size: 1G
  volumes:
    - neo4j_data:/data
    - neo4j_logs:/logs
  mem_limit: 2g
  healthcheck:
    test: ["CMD-SHELL", "wget -q --spider http://localhost:7474 || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 30s
  logging:
    driver: json-file
    options:
      max-size: "10m"
      max-file: "3"

milvus:
  image: milvusdb/milvus:v2.5.4
  restart: unless-stopped
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
  mem_limit: 4g
  depends_on:
    etcd: { condition: service_started }
    minio: { condition: service_healthy }
  healthcheck:
    test: ["CMD-SHELL", "curl -f http://localhost:9091/healthz || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s

graphrag-api:
  build:
    context: ./chefmate-graphrag
    dockerfile: Dockerfile
  restart: unless-stopped
  ports:
    - "127.0.0.1:8001:8001"
  depends_on:
    neo4j: { condition: service_healthy }
    milvus: { condition: service_healthy }
  environment:
    NEO4J_URI: bolt://neo4j:7687
    NEO4J_USER: neo4j
    NEO4J_PASSWORD: ${NEO4J_PASSWORD}
    MILVUS_HOST: milvus
    MILVUS_PORT: 19530
    DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY}
    HF_ENDPOINT: "https://hf-mirror.com"
  volumes:
    - ./chefmate-graphrag/runtime:/app/runtime
  logging:
    driver: json-file
    options:
      max-size: "10m"
      max-file: "3"
```

### 问题 5：etcd 和 minio 缺少 restart 策略

```yaml
etcd:
  restart: unless-stopped
  ...

minio:
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    interval: 30s
    timeout: 20s
    retries: 3
  ...
```

---

## 三、Nginx 配置优化

### 问题 6：缺少 CORS 和超时配置

原配置缺少 CORS headers 和连接超时。

**修复**：
```nginx
# GraphRAG API
location /api/graphchat {
    proxy_pass http://127.0.0.1:8001/api/graphchat;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_connect_timeout 10s;
    proxy_read_timeout 60s;

    # CORS
    add_header Access-Control-Allow-Origin * always;
    add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Content-Type" always;
    if ($request_method = 'OPTIONS') {
        return 204;
    }
}

location /api/graphchat/stream {
    proxy_pass http://127.0.0.1:8001/api/graphchat/stream;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 120s;
    proxy_connect_timeout 10s;
    chunked_transfer_encoding on;
}

location /api/graphrag/ {
    proxy_pass http://127.0.0.1:8001/api/graphrag/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_connect_timeout 10s;
    proxy_read_timeout 30s;
}
```

---

## 四、CI/CD 优化

### 问题 7：rsync 排除项不完整

原计划排除 `vector_index/`、`runtime/`、`.venv/`，但还应排除：
- `.env`（服务器有独立配置）
- `__pycache__/`
- `.pytest_cache/`
- `*.pyc`

**修复**：
```bash
rsync -avz \
  --exclude '.venv/' \
  --exclude 'runtime/' \
  --exclude 'vector_index/' \
  --exclude '.env' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '*.pyc' \
  chefmate-graphrag/ \
  root@vincentbuilds.fun:/var/www/vincentbuilds-api/chefmate-graphrag/
```

### 问题 8：CI/CD 中 build_graph.py 需要在容器内执行

```yaml
- name: Deploy Backend (ChefMate-GraphRAG)
  uses: appleboy/ssh-action@v1
  with:
    host: ${{ secrets.ALIYUN_SERVER_HOST }}
    username: ${{ secrets.ALIYUN_SERVER_USER }}
    key: ${{ secrets.ALIYUN_SSH_KEY }}
    script: |
      cd /var/www/vincentbuilds-api
      rsync -avz \
        --exclude '.venv/' --exclude 'runtime/' --exclude '.env' \
        --exclude '__pycache__/' --exclude '*.pyc' \
        ${{ github.workspace }}/chefmate-graphrag/ \
        ./chefmate-graphrag/
      docker compose up -d --build graphrag-api
      # 在容器内构建知识图谱（首次部署或数据更新时）
      docker exec graphrag-api python scripts/build_graph.py || true
```

---

## 五、数据安全

### 问题 9：缺少数据备份策略

Neo4j 和 Milvus 数据存储在 Docker volumes 中，无备份。

**修复**：添加备份脚本 `scripts/backup.sh`：
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/chefmate"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR

# Neo4j 备份
docker exec neo4j neo4j-admin database dump neo4j --to-path=/backups
docker cp neo4j:/backups/neo4j.dump $BACKUP_DIR/neo4j_$DATE.dump

# Milvus 备份（通过 etcd 快照）
docker exec etcd etcdctl snapshot save /backups/etcd_$DATE.db
docker cp etcd:/backups/etcd_$DATE.db $BACKUP_DIR/

# 清理 7 天前的备份
find $BACKUP_DIR -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR"
```

添加 crontab：
```bash
0 3 * * * /var/www/vincentbuilds-api/scripts/backup.sh >> /var/log/chefmate-backup.log 2>&1
```

---

## 六、文档数据更新

### 问题 10：mdx 文章数据过时

原计划中的知识图谱统计数据：
```
- 1056 个 Ingredient 节点
- 6138 个关系
```

实际最新数据（修复 extractor 后）：
```
- 1195 个 Ingredient 节点
- 6612 个关系
```

**修复**：更新 mdx 文章中的数据。

---

## 七、.gitignore 更新

确保以下条目在 `.gitignore` 中：

```
chefmate-graphrag/.env
chefmate-graphrag/.venv/
chefmate-graphrag/runtime/
chefmate-graphrag/__pycache__/
chefmate-graphrag/**/__pycache__/
chefmate-graphrag/.pytest_cache/
chefmate-graphrag/vector_index/
```

---

## 八、优化后的执行顺序

```
Phase 1: 本地代码更新
  1.1 更新标签为「在线可用」
  1.2 API URL 改为相对路径（包括 stream 端点）
  1.3 更新 mdx 文章数据（1195 ingredients, 6612 relations）
  1.4 清理 .env 中的明文密钥
  1.5 更新 .gitignore
  1.6 git commit + push

Phase 2: 服务器部署
  2.1 创建统一目录 /var/www/vincentbuilds-api/chefmate-graphrag/
  2.2 更新 docker-compose.yml（增加 restart、healthcheck、logging）
  2.3 rsync 代码（排除 .env、.venv、runtime、__pycache__）
  2.4 创建/更新服务器 .env（追加 NEO4J_PASSWORD、DEEPSEEK_API_KEY）
  2.5 docker compose up -d --build
  2.6 docker exec 内执行 build_graph.py
  2.7 验证 /api/graphrag/health

Phase 3: Nginx
  3.1 添加路由（含 CORS、超时、stream 支持）
  3.2 nginx -t && nginx -s reload

Phase 4: CI/CD
  4.1 更新 deploy.yml（统一路径、容器内建图）
  4.2 添加备份脚本和 crontab

Phase 5: 验证
  5.1 前端标签显示「在线可用」
  5.2 查询返回正确结果
  5.3 指标面板更新
  5.4 健康检查通过
  5.5 备份脚本执行成功
```

---

## 九、风险提示

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 服务器内存不足 | 容器 OOM | 4 容器总计需 ~8G，确认 ECS 规格 |
| Neo4j 数据丢失 | 知识图谱重建耗时 | 定期备份 + volume 持久化 |
| DeepSeek API 限流 | 查询失败 | 配置 DAILY_QUOTA + 降级策略 |
| Milvus 索引损坏 | 向量检索失效 | 从 Neo4j 数据重建索引 |
| 网络超时 | SSE 流中断 | Nginx proxy_read_timeout 120s |
