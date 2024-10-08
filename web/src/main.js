// main.js

import { createApp, ref } from 'vue';
import { registerPlugins } from '@/plugins';
import App from './App.vue';
import { handleSSE } from '@/services/sseService';

const app = createApp(App);

// 创建响应式数据和错误状态
const sseData = ref({});
const error = ref(null);

// 调用通用的 SSE 处理函数
handleSSE(sseData, error);

// 将响应式数据和错误状态提供给整个应用
app.provide('sseData', sseData);
app.provide('sseError', error);

registerPlugins(app);
app.mount('#app');
