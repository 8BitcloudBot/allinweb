---
title: "个人作品集网站技术实现"
description: "从零构建一个现代化的个人作品集网站，使用 Astro、React、Tailwind CSS 等技术栈。"
pubDate: 2025-07-10
lang: "zh"
tags: ["前端", "Astro", "React", "Tailwind CSS"]
---

# 个人作品集网站技术实现

> 从零构建一个现代化的个人作品集网站，使用 Astro、React、Tailwind CSS 等技术栈。

## 目录

- [技术栈选择](#技术栈选择)
- [项目结构](#项目结构)
- [核心功能实现](#核心功能实现)
- [部署方案](#部署方案)

---

## 技术栈选择

### 核心框架

- **Astro 6.x**：现代化的静态站点生成器，支持 Partial Hydration（部分水合），实现首屏快速加载
- **React 19**：用于构建交互式组件，如主题切换开关
- **Tailwind CSS 4.x**：实用优先的 CSS 框架，简化样式开发

### 辅助工具

- **MDX**：支持在 Markdown 中使用 React 组件
- **Shiki**：代码语法高亮
- **GitHub Actions**：CI/CD 自动化部署
- **GitHub Pages**：免费的静态网站托管

<hr/>

<div class="callout callout-tip">
<strong>💡 技巧</strong>
Astro + React 的"岛屿架构"是最适合个人网站的方案：大部分页面是纯静态 HTML（极快加载），只有交互组件（如主题切换）才加载 JS。与 Next.js 相比，Astro 在内容型网站场景下构建产物更小、首屏渲染更快，且 MDX 原生支持让博客写作体验非常流畅。
</div>

## 项目结构

```
WebPage/
├── public/             # 静态资源
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
└── package.json        # 项目依赖
```

## 核心功能实现

### 1. 响应式布局

使用 Tailwind CSS 的响应式类实现不同屏幕尺寸的适配：

```astro
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
  <!-- 照片网格 -->
</div>
```

### 2. 主题切换系统

- **实现原理**：使用 localStorage 存储用户主题偏好，结合 CSS 类切换实现
- **技术细节**：
  - 服务端渲染时通过内联脚本设置初始主题，避免闪烁
  - 客户端使用 React 组件实现交互式切换
  - 暗色模式下自动调整背景、文字颜色和背景光晕

### 3. 内容管理系统

使用 Astro 的内容集合（Content Collections）管理博客和项目：

```typescript
// src/content/config.ts
import { defineCollection, z } from 'astro:content';

const blogCollection = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.date(),
    tags: z.array(z.string()),
  }),
});

export const collections = {
  blog: blogCollection,
};
```

### 4. 代码高亮

使用 Shiki 实现代码语法高亮，支持多种主题：

```astro
---
// astro.config.mjs
import { defineConfig } from 'astro/config';

export default defineConfig({
  markdown: {
    shikiConfig: {
      theme: 'github-dark',
    },
  },
});
---
```

## 部署方案

### GitHub Pages

1. 配置 `astro.config.mjs`：

```javascript
export default defineConfig({
  site: 'https://yourusername.github.io',
  base: '/your-repo-name',
});
```

2. 创建 GitHub Actions 工作流：

```yaml
# .github/workflows/deploy.yml
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npm run build
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ./dist
  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/deploy-pages@v4
```

<hr/>

<div class="callout callout-warning">
<strong>⚠️ 注意</strong>
GitHub Actions 部署的关键配置：<code>base</code> 必须与仓库名一致，否则页面返回 404。另外 <code>permissions</code> 中的 <code>pages: write</code> 和 <code>id-token: write</code> 是 GitHub Pages 部署的必要权限，遗漏会导致部署失败。
</div>

---

## 结语

个人作品集网站是展示技术能力和项目经验的重要窗口。选择合适的技术栈（Astro + React + Tailwind CSS）可以让开发者专注于内容而不是配置，快速搭建一个现代化、高性能的作品集网站。

> **关键要点**：技术栈服务于内容，不是炫技。Astro + React + Tailwind CSS 是最佳组合，让开发者专注于内容而不是配置。
