<template>
  <div class="app-layout">
    <AppBar />
    <div class="content-container">
      <LeftSidebar />
      <div class="main-content">
        <router-view /> <!-- 用于显示路由内容 -->
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
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.content-container {
  display: flex;
  flex: 1;
}

.main-content {
  flex: 1;
  padding: 10px;
  margin-right: 220px; /* 留出右抽屉的空间，调整为 RightDrawer 的宽度 */
  overflow-y: auto; /* 允许垂直滚动 */
}

/* 添加适当的样式以确保左侧和右侧组件的宽度 */
.left-sidebar {
  width: 250px; /* 根据需要调整宽度 */
}

.right-drawer {
  width: 250px; /* 根据需要调整宽度 */
}
</style>
