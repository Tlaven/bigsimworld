// Plugins
import Components from 'unplugin-vue-components/vite';
import Vue from '@vitejs/plugin-vue';
import Vuetify, { transformAssetUrls } from 'vite-plugin-vuetify';
import ViteFonts from 'unplugin-fonts/vite';

// Utilities
import { defineConfig } from 'vite';
import { fileURLToPath, URL } from 'node:url';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    Vue({
      template: { transformAssetUrls },
    }),
    Vuetify(),
    Components(),
    ViteFonts({
      google: {
        families: [
          {
            name: 'Roboto',
            styles: 'wght@100;300;400;500;700;900',
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
    extensions: ['.js', '.json', '.jsx', '.mjs', '.ts', '.tsx', '.vue'],
  },
  server: {
    port: 3000,
  },
  build: {
    chunkSizeWarningLimit: 1000, // 增加 chunk 大小警告阈值到 1000 kB
    rollupOptions: {
      output: {
        manualChunks(id) {
          // 根据模块名称手动分块（兼容 pnpm 的 .pnpm 路径：取最后一段 node_modules）
          if (!id.includes('node_modules')) return undefined;
          const tail = id.split('node_modules/').at(-1);
          const segs = tail.split('/');
          const pkg = segs[0].startsWith('@') ? segs.slice(0, 2).join('/') : segs[0];
          if (pkg === 'echarts') return 'echarts';
          if (pkg === 'vuetify') return 'vuetify';
          if (['vue', 'vue-router', '@vue', 'vuetify-plugin-vuetify'].some((p) => pkg.startsWith(p))) return 'vue-vendor';
          return 'vendor';
        },
      },
    },
  },
});
