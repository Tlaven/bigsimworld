<template>
  <div>
    <h1>实时数据</h1>
    <div v-if="currentData">{{ currentData }}</div>
    <div v-if="sseError">{{ sseError }}</div>
  </div>
</template>

<script setup>
import { inject, computed } from 'vue';

// 使用 inject 获取全局提供的 sseData 和 error
const sseData = inject('sseData');
const error = inject('sseError');

// 计算属性：获取 SSE 流中的最新数据
const currentData = computed(() => {
  // 如果 sseData 存在且不为空
  if (sseData.value && sseData.value.length > 0) {
    // 返回数组中最后一个元素
    return sseData.value[sseData.value.length - 1];
  } else {
    // 否则返回 null，表示没有数据
    return null;
  }
});

</script>

<style scoped>
/* 添加样式 */
</style>
