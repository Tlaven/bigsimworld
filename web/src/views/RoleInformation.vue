<template>
  <div>
    <h1>Role Information</h1>
    <div v-if="currentData.people"> people: {{ currentData.people }}</div>
    
  </div>
</template>
<script setup>
import { inject, computed } from 'vue';

// 使用 inject 获取全局提供的 sseData 和 error
const sseData = inject('sseData');
const error = inject('sseError');

// 计算属性：获取 SSE 流中的最新数据
const currentData = computed(() => {
  // 如果 sseData 存在且不为 null
  return sseData.value || null;
});


</script>

<style scoped>
/* 添加样式 */
</style>
