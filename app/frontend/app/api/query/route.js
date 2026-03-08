export async function POST(request) {
  try {
    const body = await request.json();
    const backendBase = process.env.BACKEND_API_BASE || 'http://127.0.0.1:8000';
    const response = await fetch(`${backendBase}/api/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    });

    const text = await response.text();
    let data;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = null;
    }

    if (!response.ok) {
      return Response.json(
        {
          error: data?.detail || data?.error || '后端服务暂时不可用，请确认 FastAPI 已启动。',
          status: response.status,
        },
        { status: response.status },
      );
    }

    return Response.json(data ?? { error: '后端返回了空响应。', status: 502 }, { status: data ? response.status : 502 });
  } catch (error) {
    return Response.json(
      {
        error: `请求转发失败：${error.message}`,
        status: 502,
      },
      { status: 502 },
    );
  }
}
