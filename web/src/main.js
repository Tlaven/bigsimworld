// main.js

import { createApp, ref } from 'vue';
import { registerPlugins } from '@/plugins';
import App from './App.vue';
import { useSSE } from '@/services/sseService';

const app = createApp(App);

// 创建响应式数据和错误状态
const sseData = ref([]);
const error = ref(null);

// 启动 SSE 连接
useSSE('http://localhost:5000/stream', sseData, error);

// 将响应式数据和错误状态提供给整个应用
app.provide('sseData', sseData);
app.provide('sseError', error);

registerPlugins(app);
app.mount('#app');
