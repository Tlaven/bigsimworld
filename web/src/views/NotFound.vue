<template>
  <v-container class="fill-height d-flex align-center justify-center">
    <v-row>
      <v-col cols="12" class="text-center">
        <v-icon size="96" color="primary">mdi-emoticon-sad-outline</v-icon>
        <v-divider></v-divider>

        <v-sheet>
          <div class="text-h1 mb-2">404</div>
          <div class="text-h4 mb-4">Page Not Found</div>
          <div class="text-body-1 mb-6">
            The page you are looking for doesn't exist.
          </div>

          <!-- 返回首页的按钮 -->
          <v-btn color="primary" @click="goHome" size="large">
            <v-icon icon="mdi-home" start></v-icon>
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
