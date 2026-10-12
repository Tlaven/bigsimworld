<template>
  <v-app-bar id="app-bar" app flat height="40">
    <v-toolbar-title class="text-center">SimuWorld</v-toolbar-title>

    <v-spacer></v-spacer>
    <RefreshSubscription />
    <v-btn @click="toggleTheme">切换主题</v-btn>
  </v-app-bar>
</template>

<script setup>
import { useTheme } from 'vuetify'
import RefreshSubscription from '@/components/RefreshSubscription.vue';

const theme = useTheme()

function toggleTheme() {
  theme.global.name.value = theme.global.current.value.dark ? 'light' : 'dark'
}
</script>
