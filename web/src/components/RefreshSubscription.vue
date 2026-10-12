<template>
  <v-btn color="primary" @click="refreshSubscription">刷新订阅</v-btn>

  <v-snackbar v-model="showNotice" :timeout="1500" :color="connected ? 'success' : 'error'" location="top">
    {{ connected ? (announced ? '订阅已刷新' : '已连接') : '订阅失败，将自动重连…' }}
  </v-snackbar>
</template>

<script setup>
import { ref, watch } from 'vue';
import { connect, sseStatus } from '@/services/sseService';

const announced = ref(false); // 首次自动连接成功不弹提示
const showNotice = ref(false);
const connected = ref(false);

watch(sseStatus, (status) => {
  if (status === 'connected') {
    connected.value = true;
    if (announced.value) showNotice.value = true;
    announced.value = true;
  } else if (status === 'error' || status === 'reconnecting') {
    connected.value = false;
    if (announced.value) showNotice.value = true; // 手动刷新失败时提示
  }
});

function refreshSubscription() {
  showNotice.value = false;
  connected.value = false;
  connect();
}
</script>
