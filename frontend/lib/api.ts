export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

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

export type DownloadedFile = {
  blob: Blob;
  filename: string;
};

export async function fetchDownload(path: string): Promise<DownloadedFile> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: "application/json, text/csv, application/x-ndjson" },
  });

  if (!response.ok) {
    let message = `导出失败 (${response.status})`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      if (body.detail) message = body.detail;
    } catch {
      // 非 JSON 错误响应沿用 HTTP 状态信息。
    }
    throw new Error(message);
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
  return {
    blob: await response.blob(),
    filename: filenameMatch?.[1] ?? "convertbench_dataset.jsonl",
  };
}
