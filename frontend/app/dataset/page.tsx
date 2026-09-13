"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Database,
  Download,
  FileWarning,
  RefreshCw,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchDownload, fetchJson } from "@/lib/api";
import { DatasetStats, formatBytes, formatDate } from "@/lib/badcases";

type ExportFormat = "json" | "csv" | "jsonl";

function topEntries(values: Record<string, number>): [string, number][] {
  return Object.entries(values)
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, 5);
}

function StatsCard({
  title,
  value,
  entries,
}: {
  title: string;
  value?: number;
  entries?: [string, number][];
}) {
  return (
    <Card className="bg-card/80 shadow-lg shadow-black/10">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {typeof value === "number" ? (
          <p className="text-4xl font-semibold tracking-tight">{value}</p>
        ) : entries?.length ? (
          <div className="flex flex-wrap gap-2">
            {entries.map(([label, count]) => (
              <span key={label} className="rounded-full border bg-background px-2.5 py-1 text-xs">
                {label} <span className="ml-1 text-muted-foreground">{count}</span>
              </span>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">暂无数据</p>
        )}
      </CardContent>
    </Card>
  );
}

function DatasetSkeleton() {
  return (
    <>
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-32 rounded-2xl" />
        ))}
      </section>
      <Skeleton className="mt-8 h-44 rounded-2xl" />
      <div className="mt-8 space-y-3">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-28 rounded-2xl" />
        ))}
      </div>
    </>
  );
}

export default function DatasetPage() {
  const [stats, setStats] = useState<DatasetStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sourceFormat, setSourceFormat] = useState("");
  const [targetFormat, setTargetFormat] = useState("");
  const [errorType, setErrorType] = useState("");
  const [downloading, setDownloading] = useState<ExportFormat | null>(null);
  const [downloadError, setDownloadError] = useState("");
  const [downloadMessage, setDownloadMessage] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    fetchJson<DatasetStats>("/api/dataset/stats", { signal: controller.signal })
      .then(setStats)
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") return;
        setError(requestError instanceof Error ? requestError.message : "数据集加载失败");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reloadToken]);

  const sourceOptions = useMemo(() => Object.keys(stats?.by_source_format ?? {}).sort(), [stats]);
  const targetOptions = useMemo(() => Object.keys(stats?.by_target_format ?? {}).sort(), [stats]);
  const errorOptions = useMemo(() => Object.keys(stats?.by_error_type ?? {}).sort(), [stats]);

  async function exportDataset(exportFormat: ExportFormat) {
    const params = new URLSearchParams({ format: exportFormat });
    if (sourceFormat) params.set("source_format", sourceFormat);
    if (targetFormat) params.set("target_format", targetFormat);
    if (errorType) params.set("error_type", errorType);

    setDownloading(exportFormat);
    setDownloadError("");
    setDownloadMessage("");
    try {
      const file = await fetchDownload(`/api/dataset/export?${params.toString()}`);
      const url = URL.createObjectURL(file.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setDownloadMessage(`${file.filename} 已开始下载`);
    } catch (requestError: unknown) {
      setDownloadError(requestError instanceof Error ? requestError.message : "导出失败");
    } finally {
      setDownloading(null);
    }
  }

  function clearFilters() {
    setSourceFormat("");
    setTargetFormat("");
    setErrorType("");
    setDownloadError("");
    setDownloadMessage("");
  }

  return (
    <main className="min-h-[calc(100vh-4rem)] bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.12),_transparent_32%)]">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
        <div className="mb-9 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 text-sm font-medium text-sky-300">
              <Database size={16} /> Dataset center / 数据集中心
            </div>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-5xl">Failure Dataset</h1>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Inspect the latest failures and export training-ready data. 查看最新失败，并导出可复用数据。
            </p>
          </div>
          <Button variant="outline" onClick={() => setReloadToken((value) => value + 1)}>
            <RefreshCw className="mr-2" size={16} /> Refresh / 刷新
          </Button>
        </div>

        {loading ? (
          <DatasetSkeleton />
        ) : error ? (
          <Card className="border-red-900/60 bg-red-950/20 p-10 text-center">
            <AlertTriangle className="mx-auto mb-3 text-red-300" />
            <p className="font-medium">数据集加载失败</p>
            <p className="mt-2 text-sm text-red-200">{error}</p>
            <Button className="mt-5" variant="outline" onClick={() => setReloadToken((value) => value + 1)}>
              Retry / 重试
            </Button>
          </Card>
        ) : !stats ? (
          <Card className="p-12 text-center">暂无数据</Card>
        ) : (
          <>
            <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatsCard title="Total badcases / 总数" value={stats.total} />
              <StatsCard title="Source formats / 源格式 Top 5" entries={topEntries(stats.by_source_format)} />
              <StatsCard title="Target formats / 目标格式 Top 5" entries={topEntries(stats.by_target_format)} />
              <StatsCard title="Error types / 错误类型 Top 5" entries={topEntries(stats.by_error_type)} />
            </section>

            <Card className="mt-8 bg-card/80 p-5 sm:p-6">
              <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
                <div>
                  <h2 className="font-semibold">Export dataset / 导出数据集</h2>
                  <p className="mt-1 text-sm text-muted-foreground">当前筛选条件会应用到下载内容。</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {(["json", "csv", "jsonl"] as const).map((format) => (
                    <Button
                      key={format}
                      variant={format === "jsonl" ? "default" : "outline"}
                      disabled={downloading !== null}
                      onClick={() => exportDataset(format)}
                    >
                      <Download className="mr-2" size={15} />
                      {downloading === format ? "导出中…" : format.toUpperCase()}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="mt-5 grid gap-3 border-t pt-5 md:grid-cols-3">
                <select
                  aria-label="数据集源格式"
                  value={sourceFormat}
                  onChange={(event) => setSourceFormat(event.target.value)}
                  className="h-10 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">全部源格式</option>
                  {sourceOptions.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
                <select
                  aria-label="数据集目标格式"
                  value={targetFormat}
                  onChange={(event) => setTargetFormat(event.target.value)}
                  className="h-10 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">全部目标格式</option>
                  {targetOptions.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
                <select
                  aria-label="数据集错误类型"
                  value={errorType}
                  onChange={(event) => setErrorType(event.target.value)}
                  className="h-10 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">全部错误类型</option>
                  {errorOptions.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <button type="button" onClick={clearFilters} className="text-xs text-muted-foreground hover:text-foreground">
                  Clear filters / 清除筛选
                </button>
                {downloadMessage && <p className="text-sm text-primary">{downloadMessage}</p>}
                {downloadError && <p className="text-sm text-red-300">导出失败：{downloadError}</p>}
              </div>
            </Card>

            <section className="mt-10">
              <div className="mb-4 flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold">Latest badcases / 最新 10 条</h2>
                  <p className="mt-1 text-sm text-muted-foreground">按采集时间倒序排列</p>
                </div>
                <Button asChild variant="outline">
                  <Link href="/badcases">Browse all / 浏览全部</Link>
                </Button>
              </div>

              {!stats.latest_badcases.length ? (
                <Card className="p-12 text-center">
                  <Database className="mx-auto mb-4 text-muted-foreground" size={32} />
                  <p className="font-medium">暂无 badcase</p>
                  <p className="mt-2 text-sm text-muted-foreground">失败转换产生后会显示在这里。</p>
                </Card>
              ) : (
                <div className="space-y-3">
                  {stats.latest_badcases.map((item) => (
                    <Link key={item.case_id} href={`/badcases/${encodeURIComponent(item.case_id)}`} className="group block">
                      <Card className="p-4 transition-colors hover:border-primary/50 sm:p-5">
                        <div className="flex items-start gap-3 sm:gap-4">
                          <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-sky-500/10 text-sky-300">
                            <FileWarning size={18} />
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="rounded-md bg-muted px-2 py-1 font-mono text-xs">{item.source_format}</span>
                                <ArrowRight size={13} className="text-muted-foreground" />
                                <span className="rounded-md bg-muted px-2 py-1 font-mono text-xs">{item.target_format}</span>
                                <span className="truncate font-medium">{item.original_filename}</span>
                              </div>
                              <time className="shrink-0 text-xs text-muted-foreground">{formatDate(item.captured_at)}</time>
                            </div>
                            <p className="mt-2 line-clamp-1 break-words text-sm text-muted-foreground">{item.error_message}</p>
                            <p className="mt-2 text-xs text-muted-foreground">{item.error_type} · {formatBytes(item.file_size)}</p>
                          </div>
                        </div>
                      </Card>
                    </Link>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  );
}
