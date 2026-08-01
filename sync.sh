#!/bin/bash
# AllInWeb 多云同步脚本 (含 TripPlan 旅行助手)
# 用法: ./sync.sh [target]
#   local    → 推送到 GitHub (origin + allinweb)
#   server   → 推送到 GitHub + 部署到阿里云 (V1 + TripPlan + 前端 + nginx)
#   tencent  → 部署 GraphRAG 到腾讯云 (V2)
#   all      → 三端全同步（默认）

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'
log() { echo -e "${GREEN}[sync]${NC} $1"; }
err() { echo -e "${RED}[sync]${NC} $1"; exit 1; }

TARGET="${1:-all}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_CONFIG="$ROOT/.deploy.env"
if [ -f "$DEPLOY_CONFIG" ]; then
    export $(grep -v '^#' "$DEPLOY_CONFIG" | xargs) 2>/dev/null || true
fi

# Aliyun
ALI_HOST="${ALIYUN_SERVER_HOST:-}"
ALI_USER="${ALIYUN_SERVER_USER:-}"
ALI_FRONTEND="${ALIYUN_DEPLOY_PATH:-/var/www/vincentbuilds}"
ALI_BACKEND="/var/www/vincentbuilds-api"
ALI_TRIPPLAN="/var/www/trip-planner"

# Tencent
TC_HOST="${TENCENT_SERVER_HOST:-}"
TC_USER="root"
TC_PATH="/var/www/chefmate-graphrag"

# 本地有效密钥源（不是根 .env，根 .env 含已失效的 DEEPSEEK 密钥）
KEYS_FILE="$ROOT/docs/key.md"

sync_github() {
    log "推送到 GitHub (portfolio)..."
    git push origin main 2>/dev/null || git push https://github.com/8BitcloudBot/portfolio.git main
    log "推送到 GitHub (allinweb)..."
    git push allinweb main 2>/dev/null || true
}

build_frontend() {
    log "构建前端..."
    npm run build
}

# 把本地 docs/key.md 的有效密钥写入远程 .env（覆盖失效密钥）
# 用法: sync_secrets <user@host> <remote_env_path> [extra_fields...]
sync_secrets() {
    local remote="$1"; local envpath="$2"; shift 2
    [ -f "$KEYS_FILE" ] || err "本地密钥文件 $KEYS_FILE 不存在"
    # 从 key.md 解析键值，生成远程 .env 内容
    local tmpenv; tmpenv=$(mktemp)
    grep -E '^[A-Z_]+=' "$KEYS_FILE" >> "$tmpenv"
    # 额外字段（如 MILVUS/NEO4J 等由远程保留的）由调用方通过 $@ 追加
    for kv in "$@"; do echo "$kv" >> "$tmpenv"; done
    scp "$tmpenv" "${remote}:${envpath}"
    ssh "${remote}" "chmod 600 ${envpath}"
    rm -f "$tmpenv"
    log "已写入有效密钥 → ${remote}:${envpath}"
}

sync_aliyun_frontend() {
    log "部署前端 → ${ALI_HOST}:${ALI_FRONTEND}..."
    ssh "${ALI_USER}@${ALI_HOST}" "sudo rm -rf ${ALI_FRONTEND}/* 2>/dev/null"
    tar czf - --no-xattrs -C dist . | ssh "${ALI_USER}@${ALI_HOST}" "sudo tar xzf - -C ${ALI_FRONTEND} && sudo chown -R admin:admin ${ALI_FRONTEND}"
}

sync_aliyun_backend() {
    log "同步 V1 后端源码 → ${ALI_HOST}:${ALI_BACKEND}..."
    ssh "${ALI_USER}@${ALI_HOST}" "sudo mkdir -p ${ALI_BACKEND}"
    tar czf - chefmate/ main.py config.py pyproject.toml uv.lock Dockerfile docker-compose.yml data/ | \
        ssh "${ALI_USER}@${ALI_HOST}" "sudo tar xzf - -C ${ALI_BACKEND}"
    ssh "${ALI_USER}@${ALI_HOST}" "sudo find ${ALI_BACKEND}/data -name '._*' -delete 2>/dev/null; sudo find ${ALI_BACKEND}/data -name '.DS_Store' -delete 2>/dev/null"
    # 写入有效密钥（LLM_API_KEY 等），不使用本地失效的 .env
    sync_secrets "${ALI_USER}@${ALI_HOST}" "${ALI_BACKEND}/.env"
    log "重启 V1 后端 Docker..."
    ssh "${ALI_USER}@${ALI_HOST}" "cd ${ALI_BACKEND} && sudo docker compose up -d --build"
}

sync_aliyun_tripplan() {
    log "同步 TripPlan 旅行助手 → ${ALI_HOST}:${ALI_TRIPPLAN}..."
    ssh "${ALI_USER}@${ALI_HOST}" "sudo mkdir -p ${ALI_TRIPPLAN}"
    tar czf - trip-planner/ | ssh "${ALI_USER}@${ALI_HOST}" "sudo tar xzf - -C /var/www && sudo chown -R admin:admin ${ALI_TRIPPLAN}"
    # TripPlan 所需密钥：LLM/AMAP/TAVILY/QWEATHER 已在 key.md 中，直接写入
    sync_secrets "${ALI_USER}@${ALI_HOST}" "${ALI_TRIPPLAN}/.env"
    log "启动 TripPlan 容器 (8003)..."
    ssh "${ALI_USER}@${ALI_HOST}" "cd ${ALI_TRIPPLAN} && sudo docker compose up -d --build"
    log "更新 Nginx: 添加 /api/chat/stream → 8003 路由..."
    ssh "${ALI_USER}@${ALI_HOST}" "sudo bash -c 'grep -q \\\"location /api/chat/stream\\\" /etc/nginx/conf.d/*.conf || cat >> /etc/nginx/conf.d/default.conf <<EOF

    # TripPlan 旅行助手 SSE 流式接口
    location /api/chat/stream {
        proxy_pass http://127.0.0.1:8003;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \\\$http_upgrade;
        proxy_set_header Connection \\\"upgrade\\\";
        proxy_set_header Host \\\$host;
        proxy_set_header X-Real-IP \\\$remote_addr;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
EOF'"
    ssh "${ALI_USER}@${ALI_HOST}" "sudo systemctl reload nginx"
}

sync_tencent() {
    log "同步 GraphRAG 代码 → Tencent ${TC_HOST}..."
    rsync -avz --delete --exclude='__pycache__' --exclude='.venv' --exclude='runtime' --exclude='uv.lock' \
        chefmate-graphrag/ "root@${TC_HOST}:${TC_PATH}/"
    log "同步菜谱数据..."
    rsync -avz --delete data/ "root@${TC_HOST}:${TC_PATH}/data/"
    log "清理 macOS 残留文件..."
    ssh "root@${TC_HOST}" "find ${TC_PATH}/data -name '._*' -delete 2>/dev/null; find ${TC_PATH}/data -name '.DS_Store' -delete 2>/dev/null"
    # 写入有效密钥（LLM_API_KEY + NEO4J/MILVUS 等远程保留字段）
    sync_secrets "root@${TC_HOST}" "${TC_PATH}/.env" \
        "NEO4J_URI=bolt://neo4j:7687" \
        "NEO4J_USER=neo4j" \
        "NEO4J_PASSWORD=12345678" \
        "MILVUS_HOST=milvus" \
        "MILVUS_PORT=19530" \
        "HF_ENDPOINT=https://hf-mirror.com"
    log "重建 GraphRAG API 容器..."
    ssh "root@${TC_HOST}" "cd ${TC_PATH} && docker compose up -d --build graphrag-api"
    log "腾讯云部署完成 ✅"
}

reload_nginx() {
    ssh "${ALI_USER}@${ALI_HOST}" "sudo systemctl reload nginx"
}

case "$TARGET" in
    "local")
        sync_github
        log "本地同步完成 ✅"
        ;;
    "server")
        [ -n "$ALI_HOST" ] || err "请设置 ALIYUN_SERVER_HOST (.deploy.env)"
        [ -n "$ALI_USER" ] || err "请设置 ALIYUN_SERVER_USER (.deploy.env)"
        build_frontend || err "前端构建失败"
        sync_github
        sync_aliyun_frontend
        sync_aliyun_backend
        sync_aliyun_tripplan
        log "阿里云部署完成 ✅"
        echo "  https://vincentbuilds.fun"
        ;;
    "tencent")
        [ -n "$TC_HOST" ] || err "请设置 TENCENT_SERVER_HOST (.deploy.env)"
        sync_tencent
        ;;
    "all")
        [ -n "$ALI_HOST" ] || err "请设置 ALIYUN_SERVER_HOST (.deploy.env)"
        [ -n "$TC_HOST" ] || err "请设置 TENCENT_SERVER_HOST (.deploy.env)"
        build_frontend || err "前端构建失败"
        sync_github
        sync_aliyun_frontend
        sync_aliyun_backend
        sync_aliyun_tripplan
        sync_tencent
        log "全端同步完成 ✅"
        echo "  https://vincentbuilds.fun"
        ;;
    *)
        echo "用法: ./sync.sh [local|server|tencent|all]"
        echo "  local    → 推送到 GitHub"
        echo "  server   → GitHub + 阿里云 (V1 + TripPlan + 前端)"
        echo "  tencent  → 腾讯云 (GraphRAG 全栈)"
        echo "  all      → 全端同步（默认）"
        ;;
esac
