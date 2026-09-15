export type Severity = "warning" | "error" | "critical";

export type BadCase = {
  case_id: string;
  original_filename: string;
  source_format: string;
  target_format: string;
  file_size: number;
  error_message: string;
  error_type: string;
  severity: Severity;
  image_dimensions: {
    width: number;
    height: number;
    total_pixels: number;
  } | null;
  captured_at: string;
};

export type BadCaseListResponse = {
  total: number;
  page: number;
  page_size: number;
  items: BadCase[];
};

export type BadCaseStats = {
  total: number;
  by_source_format: Record<string, number>;
  by_target_format: Record<string, number>;
  by_error_type: Record<string, number>;
  by_severity: Record<Severity, number>;
  by_date: Record<string, number>;
};

export type DatasetStats = BadCaseStats & {
  latest_badcases: BadCase[];
};

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
