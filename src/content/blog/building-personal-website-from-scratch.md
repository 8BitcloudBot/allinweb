---
title: "从零搭建个人网站全记录：规划、环境、部署一条龙"
pubDate: 2025-07-01
description: "记录我从零开始搭建个人技术博客与作品集网站的完整过程，包括技术选型、环境准备、部署方案对比、GitHub Pages 配置、阿里云服务器搭建，以及踩过的每一个坑。"
tags: ["个人网站", "Astro", "GitHub Pages", "阿里云", "部署", "Nginx"]
lang: "zh"
---

# 从零搭建个人网站全记录：规划、环境、部署一条龙

> 记录从零搭建个人技术博客与作品集网站的完整过程，涵盖需求分析、技术选型、环境搭建、部署上线，以及踩过的每一个坑。

## 目录

- [需求分析](#一需求分析我要做什么样的网站)
- [技术选型](#二技术选型)
- [环境准备](#三环境准备)
- [GitHub Pages 部署](#四github-pages-部署)
- [阿里云服务器部署](#五阿里云服务器部署)
- [踩坑记录](#六踩坑记录)

---

## 一、需求分析：我要做什么样的网站？

### 网站定位

经过讨论，确定了网站的核心定位：**技术博客 + 作品集展示**。目标受众是面试官和技术社区的朋友，需要能快速了解我的技术能力和项目经验。

### 核心页面规划

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 首页 | 个人介绍 + 精选作品 + 最新文章 |
| `/blog` | 博客列表 | 支持标签/分类筛选 |
| `/blog/[slug]` | 博客详情 | MDX 渲染，支持嵌入组件 |
| `/projects` | 作品集 | 项目卡片展示 |
| `/projects/[slug]` | 作品详情 | 项目介绍 + 技术栈 + 链接 |
| `/about` | 关于我 | 详细自我介绍 |
| `/uses` | 使用的工具 | 技术栈和工具展示 |

### 内容管理方式

选择 **Markdown 文件 + Git** 管理内容，理由：

- 简单可控，无需数据库
- Git 版本管理，可追溯
- 写文章就是写代码，开发者友好
- 后续可扩展接入 CMS

<hr/>

<div class="callout callout-tip">
<strong>💡 技巧</strong>
Markdown + Git 的内容管理方式不仅是个人博客的最佳实践，也是团队协作的基础。每个 PR 就是一次内容审核，每次 commit 都有完整历史记录，回滚和分支管理让内容发布变得可控。
</div>

---

## 二、技术选型

### 框架选择：Astro + React

| 候选方案 | 优势 | 劣势 | 结论 |
|----------|------|------|------|
| **Astro + React** | 内容优先、岛屿架构、MDX 支持、首屏极快 | 交互部分需加载 React JS | ✅ 选择 |
| Next.js | 生态成熟、SSR/SSG 都支持 | 博客场景不如 Astro 轻量 | ❌ |
| VitePress / Nuxt | Vue 生态 | 个人更熟悉 React | ❌ |
| 纯静态 HTML | 最简单 | 扩展性差 | ❌ |

**选择 Astro 的核心理由：**

- 天生为内容型网站设计，博客/作品集是它的主场
- 岛屿架构：只有交互部分加载 JS，其余纯 HTML，首屏极快
- MDX 支持：博客文章中可以直接嵌入 React 组件
- GitHub Star 49k+，2025 年静态站点框架中增速最快

### 样式方案：Tailwind CSS

- 原子化 CSS，开发效率高
- 与 Astro 集成良好
- 响应式设计开箱即用

### 视觉风格：简约清新风

| 用途 | 色值 | 说明 |
|------|------|------|
| 主背景 | `#FAFAFA` | 温暖的浅灰白 |
| 卡片背景 | `#FFFFFF` | 纯白 |
| 主文字 | `#1A1A2E` | 深蓝黑 |
| 次文字 | `#6B7280` | 中灰 |
| 强调色 | `#3B82F6` | 蓝色（链接、按钮） |
| 辅助强调 | `#10B981` | 绿色（标签、状态） |
| 代码背景 | `#F3F4F6` | 浅灰 |

字体选择：Inter（标题/正文）+ JetBrains Mono（代码块）

设计原则：大量留白、卡片式布局、圆角 8-12px、微妙阴影和过渡动画、响应式设计。

<hr/>

<div class="callout callout-info">
<strong>📘 背景</strong>
选择 Inter + JetBrains Mono 的字体组合是 2025 年技术博客的主流选择。Inter 在中英文混排时表现优秀，JetBrains Mono 的连字特性（如 <kbd>=></kbd>、<kbd>!=</kbd> 显示为单个字形）对代码阅读体验提升明显。
</div>

---

## 三、环境准备

### 已有环境

| 工具 | 版本 | 状态 |
|------|------|------|
| Node.js | v25.1.0 | ✅ |
| npm | 11.6.2 | ✅ |
| Git | 2.51.2 | ✅ |
| Python | 3.14.0 | ✅ |
| Homebrew | 5.1.7 | ✅ |
| Docker | 29.4.0 | ✅ |

### 需要补充的环境

```bash
# 安装 pnpm（推荐的包管理器）
npm install -g pnpm

# 验证安装
pnpm --version
```

---

## 四、GitHub Pages 部署

### 4.1 配置 GitHub Actions

创建 `.github/workflows/deploy.yml`：

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

### 4.2 配置 Astro

在 `astro.config.mjs` 中配置 `site`：

```javascript
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://yourusername.github.io',
  base: '/your-repo-name',
});
```

---

## 五、阿里云服务器部署

### 5.1 服务器准备

| 配置 | 说明 |
|------|------|
| 操作系统 | Ubuntu 22.04 LTS |
| 内存 | 2GB+ |
| 存储 | 40GB+ |
| 带宽 | 5Mbps+ |

### 5.2 安装 Nginx

```bash
# 更新包管理器
sudo apt update

# 安装 Nginx
sudo apt install nginx -y

# 启动 Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# 验证安装
curl http://localhost
```

### 5.3 配置 Nginx

创建 `/etc/nginx/sites-available/your-site`：

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

### 5.4 部署流程

```bash
# 本地构建
npm run build

# 上传到服务器
scp -r ./dist/* user@your-server:/var/www/your-site/

# 重启 Nginx
sudo systemctl restart nginx
```

---

## 六、踩坑记录

### 6.1 GitHub Pages 部署失败

**问题**：构建成功但页面 404

**原因**：`astro.config.mjs` 中的 `base` 配置错误

**解决**：确保 `base` 与仓库名一致

### 6.2 阿里云服务器访问慢

**问题**：国内访问速度慢

**原因**：服务器带宽不足或未配置 CDN

**解决**：
- 升级服务器带宽
- 配置阿里云 CDN
- 开启 Gzip 压缩

<hr/>

<div class="callout callout-warning">
<strong>⚠️ 注意</strong>
踩坑 6.2（阿里云访问慢）是最容易被忽视的问题。很多开发者只关注"能不能访问"，忽略了国内用户的加载体验。建议双线路部署：GitHub Pages 服务海外，阿里云 + CDN 服务国内。
</div>

### 6.3 MDX 组件不生效

**问题**：博客文章中嵌入的 React 组件不渲染

**原因**：Astro 默认不启用 React 集成

**解决**：

```bash
npx astro add react
```

---

## 结语

搭建个人网站是一个系统工程，从需求分析到技术选型，从环境搭建到部署上线，每一步都需要仔细考虑。Astro 是 2025 年搭建个人博客/作品集的最佳选择，它天生为内容型网站设计，性能优异，生态完善。

> **关键要点**：Astro 是最佳选择，不是 Next.js。GitHub Pages 适合海外访问，阿里云服务器适合国内访问。踩坑记录比成功经验更有价值。
