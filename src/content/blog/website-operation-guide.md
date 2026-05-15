---
title: "个人网站运维指南：从开发到部署的完整流程"
description: "详细的个人网站运维指南，包含本地开发、双线路部署、服务器管理、安全维护以及 uv 虚拟环境操作命令。"
pubDate: 2025-09-15
lang: "zh"
tags: ["网站运维", "Astro", "Nginx", "GitHub Pages", "uv"]
---

# 个人网站运维指南

> 详细的个人网站运维指南，包含本地开发、双线路部署、服务器管理、安全维护以及 uv 虚拟环境操作命令。

## 目录

- [项目概览](#一项目概览)
- [本地开发](#二本地开发)
- [部署方案](#三部署方案)
- [服务器管理](#四服务器管理)
- [安全维护](#五安全维护)

---

## 一、项目概览

### 网站信息

- **域名**：
  - 自定义域名：<https://vincentbuilds.fun>
  - GitHub Pages：<https://8bitcloudbot.github.io/portfolio/>
- **技术栈**：
  - Astro 6.x（静态站点生成器）
  - React 19（交互组件）
  - Tailwind CSS 4.x（样式系统）
  - MDX（博客内容）
  - Nginx（服务器端静态文件托管）
  - GitHub Actions（CI/CD 自动部署）
  - uv（Python 虚拟环境管理）

### 目录结构

```
WebPage/
├── public/             # 静态资源
│   ├── photos/         # 照片/壁纸
│   └── favicon.svg     # 网站图标
├── src/
│   ├── components/     # 可复用组件
│   │   ├── icons/      # 图标组件
│   │   ├── layout/     # 布局组件
│   │   ├── blog/       # 博客相关组件
│   │   ├── projects/   # 项目相关组件
│   │   └── ui/         # UI 组件
│   ├── content/        # 内容集合
│   │   ├── blog/       # 博客文章
│   │   └── projects/   # 项目文档
│   ├── layouts/        # 页面布局
│   ├── pages/          # 页面组件
│   ├── styles/         # 全局样式
│   └── config.ts       # 站点配置
├── docs/               # 文档
│   └── plans/          # 计划文档
├── .github/            # GitHub 配置
│   └── workflows/      # CI/CD 工作流
├── astro.config.mjs    # Astro 配置
├── package.json        # 项目依赖
└── OPERATIONS_GUIDE.md # 操作指南

<hr/>

<div class="callout callout-info">
<strong>📘 背景</strong>
本项目采用 GitHub Actions 自动部署到 GitHub Pages，同时手动部署到阿里云服务器。这种双线路策略确保海外和国内用户都能快速访问。自动化部署的关键是 <code>npm run build</code> 产出 <code>./dist</code> 目录，后续所有部署流程都基于这个产物。
</div>

## 二、本地开发

### 日常开发流程

```bash
cd /Users/wxhu/Documents/OpenCode/WebPage

# 启动开发服务器
npm run dev
# 访问 http://localhost:4321/portfolio/

# 构建生产版本
npm run build

# 预览生产版本
npm run preview
```

### 常用命令

| 命令 | 说明 |
|------|------|
| `npm run dev` | 启动开发服务器 |
| `npm run build` | 构建生产版本 |
| `npm run preview` | 预览生产版本 |
| `npm run lint` | 代码检查 |
| `npm run format` | 代码格式化 |

<hr/>

<div class="callout callout-tip">
<strong>💡 技巧</strong>
日常开发建议始终在 <code>npm run dev</code> 模式下工作，Astro 的 HMR（热模块替换）会在保存文件时秒级刷新浏览器。生产构建前先跑 <code>npm run build && npm run preview</code> 验证产物，避免部署后发现异常。此外，善用 <kbd>Ctrl</kbd> + <kbd>C</kbd> 停服后重新 <code>npm run dev</code> 可以应对偶尔的缓存问题。
</div>

---

## 三、部署方案

### 3.1 双线路部署

**为什么需要双线路部署？**

| 线路 | 优势 | 劣势 | 适用场景 |
|------|------|------|---------|
| **GitHub Pages** | 免费、稳定、自动部署 | 国内访问慢 | 海外用户 |
| **阿里云服务器** | 国内访问快、可配置 CDN | 需要付费、需要运维 | 国内用户 |

### 3.2 GitHub Pages 部署

**配置步骤**：

1. 在 GitHub 仓库设置中启用 GitHub Pages
2. 选择 GitHub Actions 作为部署源
3. 创建 `.github/workflows/deploy.yml`：

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install dependencies
        run: npm ci
      - name: Build
        run: npm run build
      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./dist

  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

### 3.3 阿里云服务器部署

**配置步骤**：

1. 安装 Nginx：

```bash
sudo apt update
sudo apt install nginx -y
```

2. 配置 Nginx：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /var/www/your-site/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

3. 部署脚本：

```bash
#!/bin/bash
# deploy.sh

# 构建
npm run build

# 上传到服务器
scp -r ./dist/* user@your-server:/var/www/your-site/

# 重启 Nginx
ssh user@your-server "sudo systemctl restart nginx"
```

---

## 四、服务器管理

### 4.1 常用命令

| 命令 | 说明 |
|------|------|
| `sudo systemctl start nginx` | 启动 Nginx |
| `sudo systemctl stop nginx` | 停止 Nginx |
| `sudo systemctl restart nginx` | 重启 Nginx |
| `sudo systemctl status nginx` | 查看 Nginx 状态 |
| `sudo nginx -t` | 测试 Nginx 配置 |
| `sudo tail -f /var/log/nginx/access.log` | 查看访问日志 |

### 4.2 监控和日志

```bash
# 查看服务器资源使用情况
htop

# 查看磁盘使用情况
df -h

# 查看内存使用情况
free -h

# 查看 Nginx 错误日志
sudo tail -f /var/log/nginx/error.log
```

---

## 五、安全维护

### 5.1 SSL 证书配置

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx -y

# 获取 SSL 证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

### 5.2 防火墙配置

```bash
# 启用防火墙
sudo ufw enable

# 允许 SSH
sudo ufw allow ssh

# 允许 HTTP/HTTPS
sudo ufw allow 80
sudo ufw allow 443

# 查看防火墙状态
sudo ufw status
```

### 5.3 安全清单

- [ ] 启用 HTTPS
- [ ] 配置防火墙
- [ ] 定期更新系统
- [ ] 定期备份数据
- [ ] 监控服务器状态
- [ ] 检查日志异常

<hr/>

<div class="callout callout-warning">
<strong>⚠️ 注意</strong>
安全维护中最容易被忽略的是 SSL 证书自动续期。Certbot 默认配置了 systemd timer，但仍然建议每月手动执行一次 <code>certbot renew --dry-run</code> 确认续期机制正常。证书过期后用户访问会显示"不安全"警告，对个人网站信誉影响很大。
</div>

---

## 结语

个人网站运维并不复杂，关键是要有清晰的流程和自动化工具。双线路部署可以同时满足海外和国内用户的需求，自动化部署可以大大降低运维成本。

> **关键要点**：双线路部署是个人网站的最佳实践。自动化部署后运维很简单，关键是要有清晰的流程和工具。
