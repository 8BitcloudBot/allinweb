#!/bin/bash
# 双端一键部署：前端 (Nginx) + 后端 (Docker)
# 用法: ./deploy.sh

set -e

DEPLOY_CONFIG="$(dirname "$0")/.deploy.env"
if [ -f "$DEPLOY_CONFIG" ]; then
    export $(grep -v '^#' "$DEPLOY_CONFIG" | xargs) 2>/dev/null || true
fi

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'
log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

HOST="${ALIYUN_SERVER_HOST:-}"
USER="${ALIYUN_SERVER_USER:-}"
FRONTEND_PATH="${ALIYUN_DEPLOY_PATH:-/var/www/vincentbuilds}"
BACKEND_PATH="/var/www/vincentbuilds-api"

[ -n "$HOST" ] || err "请设置 ALIYUN_SERVER_HOST (.deploy.env)"
[ -n "$USER" ] || err "请设置 ALIYUN_SERVER_USER (.deploy.env)"

log "1/4 构建前端..."
npm run build

log "2/4 部署前端 → ${HOST}:${FRONTEND_PATH}..."
tar czf - --no-xattrs -C dist . | ssh "$USER@$HOST" "tar xzf - -C $FRONTEND_PATH"

log "3/4 同步后端源码 → ${HOST}:${BACKEND_PATH}..."
ssh "$USER@$HOST" "mkdir -p $BACKEND_PATH"
rsync -avz --delete --exclude 'node_modules' --exclude '.venv' --exclude '__pycache__' --exclude '.git' --exclude 'dist' \
    chefmate/ main.py config.py pyproject.toml uv.lock Dockerfile docker-compose.yml .env \
    data/ vector_index/ \
    "$USER@$HOST:$BACKEND_PATH/"

log "4/4 重启后端 Docker..."
ssh "$USER@$HOST" "cd $BACKEND_PATH && docker compose up -d --build && sudo systemctl reload nginx"

echo ""
log "部署完成 ✅"
echo " 前端: https://vincentbuilds.fun"
echo " API:  https://vincentbuilds.fun/api/health"
