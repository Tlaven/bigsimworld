// src/services/sseService.js

export async function fetchClientIdAndStartSSE(url, onMessage, onError) {
  try {
    const response = await fetch(url);
    const data = await response.json();
    const clientId = data.client_id; // 获取客户端 ID
    localStorage.setItem('clientId', clientId); // 存储到 localStorage

    // 使用客户端ID建立SSE连接
    return startSSE(`http://localhost:5000/stream?channel=${clientId}`, onMessage, onError);
  } catch (err) {
    console.error('Failed to fetch client ID:', err);
    onError(err); // 调用错误处理回调
  }
}

export async function unsubscribe() {
  const clientId = localStorage.getItem('clientId'); // 从 localStorage 获取 clientId
  if (!clientId) return;

  try {
    const response = await fetch(`http://localhost:5000/api/v1/unsubscribe/${clientId}`, {
      method: 'POST',
    });
    const result = await response.json();
    if (result.success) {
      console.log('Successfully unsubscribed');
      localStorage.removeItem('clientId'); // 移除 localStorage 中的 clientId
      return true; // 返回成功状态
    }
  } catch (err) {
    console.error('Failed to unsubscribe:', err);
    throw err; // 抛出错误以便调用者处理
  }
}

export function startSSE(url, onMessage, onError) {
  const eventSource = new EventSource(url);

  // 监听自定义事件 'data'
  eventSource.addEventListener('data', (event) => {
    try {
      const data = JSON.parse(event.data); // 解析 JSON 数据
      onMessage(data); // 调用回调函数处理数据
    } catch (e) {
      console.error('Failed to parse SSE message:', e);
    }
  });
  
  // 监听自定义事件 'initial_data'
  eventSource.addEventListener('initial_data', (event) => {
    try {
      const data = JSON.parse(event.data); // 解析 JSON 数据
      onMessage(data); // 调用回调函数处理数据
    } catch (e) {
      console.error('Failed to parse initial data:', e);
    }
  });

  // 错误处理
  eventSource.onerror = (event) => {
    console.error('SSE error:', event);
    onError(event); // 调用回调函数处理错误
    eventSource.close(); // 关闭连接
  };

  return eventSource; // 返回 EventSource 实例以便外部管理
}
