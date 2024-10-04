<template>
  <!-- Right Navigation Drawer -->
  <v-navigation-drawer app location="right" permanent width="250px">
    <v-list>
      <v-list-item title="Right Drawer Item" prepend-icon="mdi-information"></v-list-item>
      
      <v-card>
        <v-card-title>Current Data</v-card-title>
        <v-card-text>
          <!-- Show error if there is any -->
          <v-alert v-if="error" type="error">{{ error }}</v-alert>

          <!-- Show current data or waiting message -->
          <span v-else>{{ currentData ? currentData.time : 'Waiting for data...' }}</span>
        </v-card-text>
      </v-card>
      
    </v-list>
  </v-navigation-drawer>
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


