// main.js

import { createApp, ref } from 'vue';
import { registerPlugins } from '@/plugins';
import App from './App.vue';
import { connect } from '@/services/sseService';

const app = createApp(App);

// 全局 SSE 数据与错误状态
const sseData = ref({});
const sseError = ref(null);

connect({
  onMessage: (data) => {
    sseData.value = { ...sseData.value, ...data };
  },
  onError: (err) => {
    sseError.value = err?.message || String(err);
  },
});

// 将响应式数据和错误状态提供给整个应用
app.provide('sseData', sseData);
app.provide('sseError', sseError);

registerPlugins(app);
app.mount('#app');
