<template>
  <v-app>
    <v-main>
      <router-view /> <!-- 方便使用 Vue Router -->
    </v-main>
  </v-app>
</template>

<script setup>
import AppLayout from './views/layout/AppLayout.vue'
</script>
