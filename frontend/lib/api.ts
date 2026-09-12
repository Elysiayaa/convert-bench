export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type ApiErrorBody = {
  detail?: string;
};

export async function fetchJson<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      Accept: "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let message = `请求失败 (${response.status})`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      if (body.detail) message = body.detail;
    } catch {
      // 响应不是 JSON 时保留 HTTP 状态信息。
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}
