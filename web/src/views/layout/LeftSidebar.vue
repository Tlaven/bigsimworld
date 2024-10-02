<template>
  <v-navigation-drawer :width="150" app permanent>
    <!-- 应用标题部分 -->
    <v-list-item title="My Application" subtitle="Vuetify"></v-list-item>
    <v-divider></v-divider>

    <!-- 列表项 -->
    <v-list>
      <v-list-item link :to="{ name: 'Home' }" title="List Item 1">
        <v-list-item-icon>
          <v-icon>mdi-home</v-icon> <!-- Use icons as needed -->
        </v-list-item-icon>
      </v-list-item>

      <v-list-item link :to="{ name: 'ResourceManagement' }" title="模拟资源管理">
        <v-list-item-icon>
          <v-icon>mdi-account</v-icon>
        </v-list-item-icon>
      </v-list-item>

      <v-list-item link :to="{ name: 'DistributionStatistics' }" title="模拟分布统计">
        <v-list-item-icon>
          <v-icon>mdi-chart-bar</v-icon>
        </v-list-item-icon>
        </v-list-item>

    </v-list>
  </v-navigation-drawer>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';

// Optionally, you can define active states or other functionalities here
const router = useRouter();
</script>

<style scoped>
/* Add any necessary styles here */
</style>
