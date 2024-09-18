<template>
    <div class="time-container">
      <h1>Real-time Clock</h1>
      <div id="time" class="time-text">{{ currentTime }}</div>
      <p v-if="connectionError" class="error-text">Connection lost</p>
    </div>
  </template>
  
  <script>
  export default {
    data() {
      return {
        currentTime: 'Waiting for time...',
        connectionError: false,
      };
    },
    mounted() {
      this.setupSSE();
    },
    methods: {
      setupSSE() {
        const eventSource = new EventSource('http://localhost:5000/stream');  // 指向 Flask 后端
  
        eventSource.addEventListener('time', (event) => {
          const data = JSON.parse(event.data);
          this.currentTime = `Current Time: ${data.time}`;
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
  .time-container {
    text-align: center;
    margin-top: 50px;
  }
  .time-text {
    font-size: 48px;
    font-weight: bold;
  }
  .error-text {
    color: red;
  }
  </style>
  