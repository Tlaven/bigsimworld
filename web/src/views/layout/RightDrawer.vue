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
import { ref, computed } from 'vue';
import { useSSE } from '@/services/sseService.js';

// 使用组合式函数连接 SSE 服务器
const { sseData, error } = useSSE('http://localhost:5000/stream');

// 计算属性：获取 SSE 流中的最新数据
const currentData = computed(() => sseData.value ? sseData.value[sseData.value.length - 1] : null);
</script>


