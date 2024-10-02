// src/services/sseService.js
import { onMounted, onUnmounted } from 'vue';

export function useSSE(url, sseData, error) {
  let eventSource = null;

  const onMessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      sseData.value.push(data);

      // 保留最近的 60 次数据
      if (sseData.value.length > 60) {
        sseData.value.shift();
      }
    } catch (e) {
      error.value = 'Failed to parse SSE message';
      console.error(e);
    }
  };

  const onError = (event) => {
    error.value = 'Error in SSE connection';
    console.error(event);
  };

  onMounted(() => {
    if (!!window.EventSource) {
      eventSource = new EventSource(url);
      eventSource.addEventListener('message', onMessage);
      eventSource.onerror = onError;
    } else {
      error.value = 'SSE is not supported in this browser.';
    }
  });

  onUnmounted(() => {
    if (eventSource) {
      eventSource.close();
    }
  });
}
