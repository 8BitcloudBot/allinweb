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