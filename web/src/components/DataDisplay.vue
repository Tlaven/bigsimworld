<template>
  <div class="data-container">
    <h1>实时数据</h1>
    <div class="data-list">
      <div class="data-item" v-for="(value, key) in receivedData" :key="key">
        <span class="data-key">{{ key }}:</span>
        <span class="data-value">{{ value }}</span>
      </div>
    </div>
    <p v-if="connectionError" class="error-text">连接中断，正在重试...</p>
  </div>
</template>

<script>
export default {
  data() {
    return {
      receivedData: {},  // 存储从后端接收的数据
      connectionError: false,
    };
  },
  mounted() {
    this.setupSSE();
  },
  methods: {
    setupSSE() {
      const eventSource = new EventSource('http://localhost:5000/stream');

      eventSource.addEventListener('data', (event) => {
        const data = JSON.parse(event.data);
        this.receivedData = { ...this.receivedData, ...data }; // 合并数据
        this.connectionError = false;
      });

      eventSource.addEventListener('error', () => {
        this.connectionError = true;
        setTimeout(() => {
          this.setupSSE(); // 5秒后重试
        }, 5000);
      });
    },
  },
};
</script>

<style scoped>
.data-container {
  max-width: 600px;
  margin: 50px auto;
  font-family: Arial, sans-serif;
  text-align: left;
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background-color: #f9f9f9;
}
.data-list {
  max-height: 300px; /* 设置最大高度 */
  overflow-y: auto; /* 添加垂直滚动条 */
  padding: 10px;
  border: 1px solid #eee;
  border-radius: 8px;
}
.data-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #eee;
}
.data-key {
  font-weight: bold;
  color: #333;
}
.data-value {
  color: #555;
}
.error-text {
  color: red;
  text-align: center;
  margin-top: 20px;
}
</style>
