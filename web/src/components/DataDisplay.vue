<template>
  <div class="data-container">
    <h1>Real-time Data</h1>
    <div class="data-item" v-for="(value, key) in receivedData" :key="key">
      <span class="data-key">{{ key }}:</span>
      <span class="data-value">{{ value }}</span>
    </div>
    <p v-if="connectionError" class="error-text">Connection lost</p>
  </div>
</template>

<script>
export default {
  data() {
    return {
      receivedData: {},  // 存放从后端接收到的字典数据
      connectionError: false,
    };
  },
  mounted() {
    this.setupSSE();
  },
  methods: {
    setupSSE() {
      const eventSource = new EventSource('http://localhost:5000/stream'); // 指向 Flask 后端

      eventSource.addEventListener('data', (event) => {
        const data = JSON.parse(event.data);
        this.receivedData = data;
        this.connectionError = false;
      });

      eventSource.addEventListener('error', () => {
        this.connectionError = true;
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
