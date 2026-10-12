<template>
  <div class="app-layout">
    <AppBar />
    <div class="content">
      <LeftSidebar />
      <div class="main-content">
        <router-view /> <!-- 子路由内容 -->
      </div>
      <RightDrawer />
    </div>
  </div>
</template>

<script setup>
import AppBar from './AppBar.vue';
import LeftSidebar from './LeftSidebar.vue';
import RightDrawer from './RightDrawer.vue';
</script>

<style scoped>
.app-layout {
  height: 100vh;
}

.content {
  display: flex;
  height: calc(100vh - 40px); /* 减去 AppBar 高度 */
}

/* 左右两列由 v-navigation-drawer 自行定位（Vuetify 布局系统给 v-main 自动留白），
   这里只负责中间主内容区域的滚动 */
.main-content {
  flex: 1;
  padding: 10px;
  overflow-y: auto;
}
</style>
