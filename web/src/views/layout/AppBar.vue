<template>
  <v-app-bar
    id="app-bar"
    app
    flat
    height="40"
  >
      <v-btn icon @click="$emit('menu-click')">
        <v-icon>mdi-menu</v-icon>
      </v-btn>

      <v-spacer></v-spacer>
      <v-toolbar-title class="text-center" style="flex: 1; text-align: center;">
        <a href="https://github.com/your-username/your-repo" target="_blank" style="color: inherit; text-decoration: none;">
          BigSimWorld
        </a>
      </v-toolbar-title>
      <v-spacer></v-spacer>

      <RefreshSubscription />
      <v-btn @click="toggleTheme">
        Toggle Theme
      </v-btn>
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
