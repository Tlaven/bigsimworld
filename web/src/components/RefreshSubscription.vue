<template>
  <div>
    <v-btn @click="refreshSubscription" color="primary">刷新订阅</v-btn>
    <v-snackbar v-model="snackbar" :timeout="3000" color="error">
      {{ error }}
      <template #action>
        <v-btn color="white" text @click="snackbar = false">关闭</v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script>
import { ref, inject } from 'vue';
import { fetchClientIdAndStartSSE, unsubscribe } from '@/services/sseService';

export default {
  setup() {
    const sseData = inject('sseData');
    const error = ref(null);
    const snackbar = ref(false); // 控制 snackbar 显示的状态

    const refreshSubscription = async () => {
      error.value = null; // 清除之前的错误

      // 先取消之前的订阅
      await unsubscribe(); // 从 localStorage 获取 clientId 并取消订阅

      try {
        await fetchClientIdAndStartSSE(
          'http://localhost:5000/api/v1/get-client-id',
          (data) => {
            sseData.value.push(data); // 更新响应式数据
          },
          (err) => {
            error.value = 'Error: ' + err.message; // 更新错误状态
            snackbar.value = true; // 显示 snackbar
          }
        );
      } catch (err) {
        error.value = 'Failed to refresh subscription: ' + err.message; // 处理获取错误
        snackbar.value = true; // 显示 snackbar
      }
    };

    return {
      refreshSubscription,
      error,
      snackbar,
    };
  },
};
</script>
