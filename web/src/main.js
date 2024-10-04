// main.js

import { createApp, ref } from 'vue';
import { registerPlugins } from '@/plugins';
import App from './App.vue';
import { fetchClientIdAndStartSSE } from '@/services/sseService';

const app = createApp(App);

// 创建响应式数据和错误状态
const sseData = ref({}); // 作为一个字典保存数据
const error = ref(null);

fetchClientIdAndStartSSE('http://localhost:5000/api/v1/get-client-id', 
    (data) => {
      // 复制旧数据并合并
      const updatedData = { ...sseData.value, ...data }; // 只更新存在的键
      sseData.value = updatedData; // 更新为合并后的数据
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
