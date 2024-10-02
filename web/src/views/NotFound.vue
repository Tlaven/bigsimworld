<template>
    <v-container class="fill-height d-flex align-center justify-center">
      <v-row>
        <v-col cols="12" class="text-center">
          <!-- 使用 Vuetify 的内置排版 -->
          <v-icon size="96" color="primary">mdi-emoticon-sad-outline</v-icon>
          <v-divider></v-divider>
  
          <!-- 404 标题和副标题使用 Vuetify 的排版 -->
          <v-sheet>
            <v-typography variant="h1" class="mb-2">404</v-typography>
            <v-typography variant="h4" class="mb-4">Page Not Found</v-typography>
            <v-typography variant="body-1" class="mb-6">
              The page you are looking for doesn't exist.
            </v-typography>
  
            <!-- 返回首页的按钮 -->
            <v-btn color="primary" @click="goHome" large>
              <v-icon left>mdi-home</v-icon>
              Go Home
            </v-btn>
          </v-sheet>
        </v-col>
      </v-row>
    </v-container>
  </template>
  
  <script setup>
  import { useRouter } from 'vue-router';
  
  // 使用 useRouter() 来处理导航
  const router = useRouter();
  
  // 返回首页的函数
  const goHome = () => {
    router.push('/');
  };
  </script>
  