<template>
  <div>
    <h1>实时数据</h1>
    <ul>
      <li v-for="(item, index) in sseData" :key="index">{{ item }}</li>
    </ul>
    <div v-if="sseError">{{ sseError }}</div>
  </div>
</template>

<script>
import { inject } from 'vue';

export default {
  setup() {
    const sseData = inject('sseData');
    const sseError = inject('sseError');

    return { sseData, sseError };
  }
};
</script>
