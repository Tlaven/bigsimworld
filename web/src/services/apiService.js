// src/services/apiService.js
// 后端观测/控制接口（注意度、生命轨迹）。基址与 SSE 共用 VITE_API_BASE_URL。

function baseUrl() {
  return import.meta.env.VITE_API_BASE_URL || '';
}

// 置注意度：pin（value=1）或放掉（value=0）。personId 会映射到其所属团。
export async function setAttention({ personId, clusterId, value = 1.0 }) {
  const body = { value };
  if (clusterId != null) body.cluster_id = clusterId;
  else if (personId != null) body.person_id = personId;
  const res = await fetch(`${baseUrl()}/api/v1/attention`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}

// 某人的生命轨迹；不存在或非 measure 模式返回 null。
export async function fetchLife(personId) {
  const res = await fetch(`${baseUrl()}/api/v1/life/${personId}`);
  if (!res.ok) return null;
  return res.json();
}
