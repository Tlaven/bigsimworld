// src/services/sseService.js

// 通用的 SSE 处理函数
export async function handleSSE(sseData, error) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL;; // 获取基础 API URL
  
  try {
    await fetchClientIdAndStartSSE(
      `${baseUrl}/api/v1/get-client-id`,
      (data) => {
        const updatedData = { ...sseData.value, ...data }; // 合并旧数据与新数据
        sseData.value = updatedData;
      },
      (err) => {
        error.value = err; // 更新错误状态
      }
    );
  } catch (err) {
    error.value = 'Failed to refresh subscription: ' + err.message;
  }
}

export async function fetchClientIdAndStartSSE(url, onMessage, onError) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL;; // 获取基础 API URL

  try {
    const response = await fetch(url);
    const data = await response.json();
    const clientId = data.client_id; // 获取客户端 ID
    localStorage.setItem('clientId', clientId); // 存储到 localStorage

    // 使用客户端ID建立SSE连接，并在连接成功后发送通知
    const eventSource = startSSE(`${baseUrl}/stream?channel=${clientId}`, onMessage, onError);

    // 等待连接打开后发送通知
    eventSource.onopen = async () => {
      await notifyConnectionEstablished(`${baseUrl}/api/v1/notify-connection`, { clientId });
    };

    return eventSource; // 返回 EventSource 实例以便外部管理
  } catch (err) {
    console.error('Failed to fetch client ID:', err);
    onError(err); // 调用错误处理回调
  }
}

// 发送连接建立通知
async function notifyConnectionEstablished(url, payload) {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error('Failed to send notification');
    }
    console.log('Connection established notification sent successfully');
  } catch (error) {
    console.error('Error sending connection notification:', error);
  }
}

export async function unsubscribe() {
  const clientId = localStorage.getItem('clientId'); // 从 localStorage 获取 clientId
  const baseUrl = import.meta.env.VITE_API_BASE_URL;; // 获取基础 API URL

  if (!clientId) return;

  try {
    const response = await fetch(`${baseUrl}/api/v1/unsubscribe/${clientId}`, {
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

  // 处理 SSE 消息
  const handleMessage = (event) => {
    try {
      const data = JSON.parse(event.data); // 解析 JSON 数据
      onMessage(data); // 调用回调函数处理数据
    } catch (e) {
      console.error('Failed to parse SSE message:', e);
      onError(e); // 通知调用者解析错误
    }
  };

  // 监听自定义事件 'data'
  eventSource.addEventListener('data', handleMessage);
  
  // 监听自定义事件 'initial_data'
  eventSource.addEventListener('initial_data', handleMessage);

  // 错误处理
  eventSource.onerror = (event) => {
    console.error('SSE error:', event);
    onError(event); // 调用回调函数处理错误
    eventSource.close(); // 关闭连接
  };

  return eventSource; // 返回 EventSource 实例以便外部管理
}
