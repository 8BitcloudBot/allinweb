// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';

// 多环境配置
const environments = {
  production: {
    site: 'https://vincentbuilds.fun',
    base: '/',
    output: 'static' as const
  },
  github: {
    site: 'https://8bitcloudbot.github.io',
    base: '/portfolio',
    output: 'static' as const
  },
  development: {
    site: 'http://localhost:4321',
    base: '/',
    output: 'static' as const
  }
};

// 根据环境变量选择配置
const env = process.env.ASTRO_ENV || 'development';
const config = environments[env as keyof typeof environments] || environments.development;

export default defineConfig({
  site: config.site,
  base: config.base,
  output: config.output,
  devToolbar: { enabled: false },
  integrations: [
    react(),
    mdx(),
    sitemap(),
  ],
  vite: {
    plugins: [tailwindcss()],
    server: {
      proxy: {
        // V2 GraphRAG 路由分流到 8001
        '/api/graphchat': {
          target: 'http://localhost:8001',
          changeOrigin: true,
        },
        // 旅行助手 TripPlan 路由分流到 8003（避免与 V1 抢 8000）
        '/api/chat/stream': {
          target: 'http://localhost:8003',
          changeOrigin: true,
        },
        // 其余 /api/*（含 /api/chat、/api/health 等 V1 路由）走 8000
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  },
  markdown: {
    shikiConfig: {
      theme: 'css-variables',
      wrap: false,
    },
  },
});