#!/bin/bash
# AllInWeb 多云同步脚本
# 用法: ./sync.sh [target]
#   local    → 推送到 GitHub (origin + allinweb)
#   server   → 推送到 GitHub + 部署到阿里云 (V1 + 前端)
#   tencent  → 部署 GraphRAG 到腾讯云
#   all      → 三端全同步（默认）

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'
log() { echo -e "${GREEN}[sync]${NC} $1"; }
err() { echo -e "${RED}[sync]${NC} $1"; exit 1; }

TARGET="${1:-all}"
DEPLOY_CONFIG="$(dirname "$0")/.deploy.env"
if [ -f "$DEPLOY_CONFIG" ]; then
    export $(grep -v '^#' "$DEPLOY_CONFIG" | xargs) 2>/dev/null || true
fi

# Aliyun
ALI_HOST="${ALIYUN_SERVER_HOST:-}"
ALI_USER="${ALIYUN_SERVER_USER:-}"
ALI_FRONTEND="${ALIYUN_DEPLOY_PATH:-/var/www/vincentbuilds}"
ALI_BACKEND="/var/www/vincentbuilds-api"

# Tencent
TC_HOST="${TENCENT_SERVER_HOST:-}"
TC_USER="root"
TC_PATH="/var/www/chefmate-graphrag"

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

sync_aliyun_frontend() {
    log "部署前端 → ${ALI_HOST}:${ALI_FRONTEND}..."
    ssh "${ALI_USER}@${ALI_HOST}" "sudo rm -rf ${ALI_FRONTEND}/* 2>/dev/null"
    tar czf - --no-xattrs -C dist . | ssh "${ALI_USER}@${ALI_HOST}" "sudo tar xzf - -C ${ALI_FRONTEND} && sudo chown -R admin:admin ${ALI_FRONTEND}"
}

sync_aliyun_backend() {
    log "同步后端源码 → ${ALI_HOST}:${ALI_BACKEND}..."
    ssh "${ALI_USER}@${ALI_HOST}" "sudo mkdir -p ${ALI_BACKEND}"
    tar czf - chefmate/ main.py config.py pyproject.toml uv.lock Dockerfile docker-compose.yml data/ | \
        ssh "${ALI_USER}@${ALI_HOST}" "sudo tar xzf - -C ${ALI_BACKEND}"
    ssh "${ALI_USER}@${ALI_HOST}" "sudo find ${ALI_BACKEND}/data -name '._*' -delete 2>/dev/null; sudo find ${ALI_BACKEND}/data -name '.DS_Store' -delete 2>/dev/null"
    if [ -f .env ]; then
        scp .env "${ALI_USER}@${ALI_HOST}:${ALI_BACKEND}/.env"
        ssh "${ALI_USER}@${ALI_HOST}" "sudo chmod 600 ${ALI_BACKEND}/.env"
    fi
    log "重启后端 Docker..."
    ssh "${ALI_USER}@${ALI_HOST}" "cd ${ALI_BACKEND} && sudo docker compose up -d --build"
    log "重载 Nginx..."
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
    log "重建 GraphRAG API 容器..."
    ssh "root@${TC_HOST}" "cd ${TC_PATH} && docker compose up -d --build graphrag-api"
    log "腾讯云部署完成 ✅"
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
        sync_tencent
        log "全端同步完成 ✅"
        echo "  https://vincentbuilds.fun"
        ;;
    *)
        echo "用法: ./sync.sh [local|server|tencent|all]"
        echo "  local    → 推送到 GitHub"
        echo "  server   → GitHub + 阿里云 (V1 + 前端)"
        echo "  tencent  → 腾讯云 (GraphRAG 全栈)"
        echo "  all      → 全端同步（默认）"
        ;;
esac
