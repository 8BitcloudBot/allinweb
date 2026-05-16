#!/bin/bash
# AllInWeb 三端同步脚本
# 用法: ./sync.sh [target]
#   local    → 推送到 GitHub (origin + allinweb)
#   server   → 推送到 GitHub + 部署到阿里云
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

HOST="${ALIYUN_SERVER_HOST:-}"
USER="${ALIYUN_SERVER_USER:-}"
FRONTEND_PATH="${ALIYUN_DEPLOY_PATH:-/var/www/vincentbuilds}"
BACKEND_PATH="/var/www/vincentbuilds-api"

sync_github() {
    log "推送到 GitHub (portfolio)..."
    git push origin main

    log "推送到 GitHub (allinweb)..."
    git push allinweb main
}

build_frontend() {
    log "构建前端..."
    npm run build
}

sync_server_frontend() {
    log "部署前端 → ${HOST}:${FRONTEND_PATH}..."
    ssh "$USER@$HOST" "sudo rm -rf ${FRONTEND_PATH}/* 2>/dev/null"
    tar czf - --no-xattrs -C dist . | ssh "$USER@$HOST" "sudo tar xzf - -C ${FRONTEND_PATH} && sudo chown -R admin:admin ${FRONTEND_PATH}"
}

sync_server_backend() {
    log "同步后端源码 → ${HOST}:${BACKEND_PATH}..."
    ssh "$USER@$HOST" "sudo mkdir -p ${BACKEND_PATH}"
    tar czf - chefmate/ main.py config.py pyproject.toml uv.lock Dockerfile docker-compose.yml data/ | \
        ssh "$USER@$HOST" "sudo tar xzf - -C ${BACKEND_PATH}"

    # 清理 macOS 资源叉文件
    ssh "$USER@$HOST" "sudo find ${BACKEND_PATH}/data -name '._*' -delete 2>/dev/null; sudo find ${BACKEND_PATH}/data -name '.DS_Store' -delete 2>/dev/null"

    # 复制 .env（不随 git 分发）
    if [ -f .env ]; then
        scp .env "$USER@$HOST:${BACKEND_PATH}/.env"
        ssh "$USER@$HOST" "sudo chmod 600 ${BACKEND_PATH}/.env"
    fi

    # 向量索引隔离：仅在首次或手动指定时构建
    # 服务端 index 由 Docker 启动时自动判断
    log "重启后端 Docker..."
    ssh "$USER@$HOST" "cd ${BACKEND_PATH} && sudo docker compose up -d --build"

    log "重载 Nginx..."
    ssh "$USER@$HOST" "sudo systemctl reload nginx"
}

case "$TARGET" in
    "local")
        sync_github
        log "本地同步完成 ✅"
        ;;
    "server")
        [ -n "$HOST" ] || err "请设置 ALIYUN_SERVER_HOST (.deploy.env)"
        [ -n "$USER" ] || err "请设置 ALIYUN_SERVER_USER (.deploy.env)"
        build_frontend || err "前端构建失败"
        sync_github
        sync_server_frontend
        sync_server_backend
        log "服务器部署完成 ✅"
        echo "  https://vincentbuilds.fun"
        echo "  https://vincentbuilds.fun/api/health"
        ;;
    "all")
        [ -n "$HOST" ] || err "请设置 ALIYUN_SERVER_HOST (.deploy.env)"
        [ -n "$USER" ] || err "请设置 ALIYUN_SERVER_USER (.deploy.env)"
        build_frontend || err "前端构建失败"
        sync_github
        sync_server_frontend
        sync_server_backend
        log "三端全同步完成 ✅"
        echo "  Local:   git status"
        echo "  GitHub:  https://github.com/8BitcloudBot/allinweb"
        echo "  Server:  https://vincentbuilds.fun"
        ;;
    *)
        echo "用法: ./sync.sh [local|server|all]"
        echo "  local   → 推送到 GitHub"
        echo "  server  → GitHub + 阿里云"
        echo "  all     → 三端全同步（默认）"
        ;;
esac
