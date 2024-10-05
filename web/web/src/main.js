// main.js

import { createApp, ref } from 'vue';
import { registerPlugins } from '@/plugins';
import App from './App.vue';
import { fetchClientIdAndStartSSE } from '@/services/sseService';

const app = createApp(App);

// 创建响应式数据和错误状态
const sseData = ref([]);
const error = ref(null);

// 启动获取客户端 ID 并建立 SSE 连接
fetchClientIdAndStartSSE('http://localhost:5000/api/v1/get-client-id', 
  (data) => {
    sseData.value.push(data); // 更新响应式数据
  }, 
  (err) => {
    error.value = err; // 更新错误状态
  }
);

// 将响应式数据和错误状态提供给整个应用
app.provide('sseData', sseData);
app.provide('sseError', error);

registerPlugins(app);
app.mount('#app');
