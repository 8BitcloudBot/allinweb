# AllInWeb 运维手册

## 环境概览

| 环境 | 地址 | 用途 |
|------|------|------|
| 本地开发 | `localhost:4321` / `localhost:8000` | 日常开发 |
| GitHub | `github.com/8BitcloudBot/allinweb` | 代码托管 |
| 阿里云生产 | `vincentbuilds.fun` | 对外服务 |

## 目录结构

```
本地: /Users/wxhu/Documents/OpenCode/AllInWeb/
GitHub: 8BitcloudBot/allinweb (代码) + 8BitcloudBot/portfolio (网站)
服务器: 
  前端 /var/www/vincentbuilds/
  后端 /var/www/vincentbuilds-api/
```

## 日常操作

### 本地开发启动

```bash
cd /Users/wxhu/Documents/OpenCode/AllInWeb

# 后端 (启动需 ~20s 初始化模型+索引)
uv run uvicorn chefmate.server:app --host 0.0.0.0 --port 8000

# 前端 (另开终端)
npm run dev
# 浏览器访问 http://localhost:4321/chefmate
```

### 代码发布

```bash
# 方式 1：三端全同步（本地 → GitHub → 阿里云）
./sync.sh all

# 方式 2：仅推送 GitHub（不部署）
./sync.sh local

# 方式 3：GitHub + 阿里云部署（已有本地构建）
./sync.sh server

# 方式 4：仅部署阿里云（不推 GitHub）
./deploy.sh
```

### 发布前检查清单

- [ ] `npm run build` 无报错
- [ ] `uv run python -c "from main import RecipeRAGSystem"` 可以导入
- [ ] `.deploy.env` 中服务器信息正确（`ALIYUN_SERVER_HOST`, `ALIYUN_SERVER_USER`）
- [ ] `.env` 中 `DEEPSEEK_API_KEY` 有效
- [ ] 没有将 `.env` 或 `.deploy.env` 提交到 Git

### 服务器运维

```bash
# SSH 登录
ssh admin@47.106.38.219

# 查看后端容器状态
cd /var/www/vincentbuilds-api && sudo docker compose ps

# 查看后端日志
sudo docker logs vincentbuilds-api-vincentbuilds-1 --tail 50

# 重启后端
cd /var/www/vincentbuilds-api && sudo docker compose up -d --build

# 停止后端
cd /var/www/vincentbuilds-api && sudo docker compose down

# 查看 API 日志
sudo docker logs vincentbuilds-api-vincentbuilds-1 -f

# 重载 Nginx
sudo systemctl reload nginx

# 查看 Nginx 状态
sudo systemctl status nginx
```

### 向量索引维护

各环境 FAISS 索引独立，切勿跨环境复制。

```bash
# 服务器重建索引（删除旧索引后重启容器）
ssh admin@47.106.38.219 "
  cd /var/www/vincentbuilds-api && \
  sudo docker compose down && \
  sudo rm -f vector_index/index.faiss vector_index/index.pkl && \
  sudo docker compose up -d --build
"
# 启动后自动重建，需等待 ~30s
```

### 常见问题

#### 网站没变化

```bash
# 重新构建并部署前端
npm run build
# 然后 ./sync.sh server 或手动部署：
tar czf - --no-xattrs -C dist . | ssh admin@47.106.38.219 "sudo tar xzf - -C /var/www/vincentbuilds && sudo systemctl reload nginx"
```

#### API 返回 502

```bash
# 后端挂了，检查并重启
ssh admin@47.106.38.219 "sudo docker logs vincentbuilds-api-vincentbuilds-1 --tail 20"
ssh admin@47.106.38.219 "cd /var/www/vincentbuilds-api && sudo docker compose up -d"
```

#### 回答质量差、来源为空

```bash
# 大概率是索引问题，重建
ssh admin@47.106.38.219 "
  cd /var/www/vincentbuilds-api && \
  sudo docker compose down && \
  sudo rm -f vector_index/index.faiss vector_index/index.pkl && \
  sudo docker compose up -d --build
"
```

#### 端口 8000 暴露检查

```bash
ssh admin@47.106.38.219 "sudo ss -tlnp | grep 8000"
# 应显示 127.0.0.1:8000（不是 0.0.0.0:8000）
```

#### GitHub Actions 部署失败

1. 检查 GitHub Secrets：`ALIYUN_SSH_KEY`、`ALIYUN_SERVER_HOST`、`ALIYUN_SERVER_USER`
2. 查看 Actions 日志定位错误
3. 常见原因：SSH 密钥不匹配、服务器磁盘满、Docker 构建超时

### 安全维护

```bash
# 检查密钥未泄露到日志
ssh admin@47.106.38.219 "sudo docker logs vincentbuilds-api-vincentbuilds-1 2>&1 | grep -i 'sk-' || echo '安全'"

# 检查 .env 权限
ssh admin@47.106.38.219 "ls -la /var/www/vincentbuilds-api/.env"
# 应为 -rw------- (600)

# 检查异常 API 调用
ssh admin@47.106.38.219 "sudo docker exec vincentbuilds-api-vincentbuilds-1 ls -la /app/runtime/"

# 查看当日调用统计
ssh admin@47.106.38.219 "sudo docker exec vincentbuilds-api-vincentbuilds-1 sqlite3 /app/runtime/chefmate.db 'SELECT COUNT(*) FROM api_calls WHERE date = date(\"now\");'"
```

### 备份

```bash
# 备份菜谱数据
scp -r admin@47.106.38.219:/var/www/vincentbuilds-api/data/ ./data-backup-$(date +%Y%m%d)/

# 备份索引（一般不需要，可重建）
scp admin@47.106.38.219:/var/www/vincentbuilds-api/vector_index/* ./index-backup-$(date +%Y%m%d)/
```

### GitHub 仓库

| 仓库 | 地址 | 用途 |
|------|------|------|
| allinweb | `github.com/8BitcloudBot/allinweb` | 全量代码 + 独立 README |
| portfolio | `github.com/8BitcloudBot/portfolio` | 网站源码（GitHub Actions 部署源）|

两个仓库指向同一份本地代码，`sync.sh` 同时推送。
