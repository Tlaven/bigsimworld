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
  
      <v-toolbar-title class="text-center">
        My Application
      </v-toolbar-title>
  
      <v-spacer></v-spacer>
      <v-btn @click="toggleTheme">
        Toggle Theme
      </v-btn>
    </v-app-bar>
  </template>
  
  <script setup>
  import { useTheme } from 'vuetify'
  
  const theme = useTheme()
  
  function toggleTheme() {
    theme.global.name.value = theme.global.current.value.dark ? 'light' : 'dark'
  }
  </script>
  