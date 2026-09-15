export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

type ApiErrorBody = {
  detail?: string;
};

export type NonJsonResponsePayload = {
  error: "Server returned non-JSON response";
  status: number;
  body: string;
};

export class NonJsonResponseError extends Error implements NonJsonResponsePayload {
  readonly error = "Server returned non-JSON response" as const;
  readonly status: number;
  readonly body: string;

  constructor(status: number, body: string) {
    super("服务器返回异常响应，请查看后端日志");
    this.name = "NonJsonResponseError";
    this.status = status;
    this.body = body.slice(0, 200);
  }
}

export async function parseJsonResponse<T>(response: Response): Promise<T> {
  // 先读取文本，确保 HTML 或纯文本错误页不会直接产生难懂的 JSON.parse 异常。
  const text = await response.text();
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new NonJsonResponseError(response.status, text);
  }
}

function apiErrorMessage(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as ApiErrorBody).detail;
    if (typeof detail === "string" && detail) return detail;
  }
  return `请求失败 (${status})`;
}

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
  const body = await parseJsonResponse<T>(response);
  if (!response.ok) throw new Error(apiErrorMessage(body, response.status));
  return body;
}

export type DownloadedFile = {
  blob: Blob;
  filename: string;
};

export async function fetchDownload(path: string): Promise<DownloadedFile> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: "application/json, text/csv, application/x-ndjson" },
  });

  if (!response.ok) {
    const body = await parseJsonResponse<unknown>(response);
    throw new Error(apiErrorMessage(body, response.status));
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
  return {
    blob: await response.blob(),
    filename: filenameMatch?.[1] ?? "convertbench_dataset.jsonl",
  };
}
