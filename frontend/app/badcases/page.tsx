"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  DatabaseZap,
  FileWarning,
  Search,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { SeverityBadge } from "@/components/severity-badge";
import { fetchJson } from "@/lib/api";
import {
  BadCaseListResponse,
  BadCaseStats,
  formatBytes,
  formatDate,
} from "@/lib/badcases";

const PAGE_SIZE = 5;

function topEntries(values: Record<string, number>): [string, number][] {
  return Object.entries(values)
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, 5);
}

function SummaryCard({
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

function ListSkeleton() {
  return (
    <div className="space-y-3" aria-label="正在加载 badcase">
      {Array.from({ length: 4 }, (_, index) => (
        <Card key={index} className="p-5">
          <div className="flex items-start gap-4">
            <Skeleton className="size-10 shrink-0 rounded-xl" />
            <div className="w-full space-y-3">
              <Skeleton className="h-5 w-44" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

export default function BadCasesPage() {
  const [stats, setStats] = useState<BadCaseStats | null>(null);
  const [statsError, setStatsError] = useState("");
  const [result, setResult] = useState<BadCaseListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sourceFormat, setSourceFormat] = useState("");
  const [targetFormat, setTargetFormat] = useState("");
  const [errorType, setErrorType] = useState("");
  const [keywordInput, setKeywordInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [sort, setSort] = useState("captured_at:desc");
  const [page, setPage] = useState(1);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setStatsError("");
    fetchJson<BadCaseStats>("/api/badcases/stats", { signal: controller.signal })
      .then(setStats)
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") return;
        setStatsError(requestError instanceof Error ? requestError.message : "统计数据加载失败");
      });
    return () => controller.abort();
  }, [reloadToken]);

  useEffect(() => {
    const controller = new AbortController();
    const [sortBy, order] = sort.split(":");
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(PAGE_SIZE),
      sort_by: sortBy,
      order,
    });
    if (sourceFormat) params.set("source_format", sourceFormat);
    if (targetFormat) params.set("target_format", targetFormat);
    if (errorType) params.set("error_type", errorType);
    if (keyword) params.set("keyword", keyword);

    setLoading(true);
    setError("");
    fetchJson<BadCaseListResponse>(`/api/badcases?${params.toString()}`, {
      signal: controller.signal,
    })
      .then(setResult)
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") return;
        setError(requestError instanceof Error ? requestError.message : "Badcase 加载失败");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [sourceFormat, targetFormat, errorType, keyword, sort, page, reloadToken]);

  const sourceOptions = useMemo(() => Object.keys(stats?.by_source_format ?? {}).sort(), [stats]);
  const targetOptions = useMemo(() => Object.keys(stats?.by_target_format ?? {}).sort(), [stats]);
  const errorOptions = useMemo(() => Object.keys(stats?.by_error_type ?? {}).sort(), [stats]);
  const totalPages = Math.max(1, Math.ceil((result?.total ?? 0) / PAGE_SIZE));

  function updateFilter(setter: (value: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setKeyword(keywordInput.trim());
    setPage(1);
  }

  function clearFilters() {
    setSourceFormat("");
    setTargetFormat("");
    setErrorType("");
    setKeywordInput("");
    setKeyword("");
    setPage(1);
  }

  return (
    <main className="min-h-[calc(100vh-4rem)] bg-[radial-gradient(circle_at_top_right,_rgba(244,63,94,0.1),_transparent_30%)]">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
        <div className="mb-9 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 text-sm font-medium text-rose-300">
              <DatabaseZap size={16} /> Failure dataset / 失败数据集
            </div>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-5xl">Badcase Explorer</h1>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Search, filter, and inspect conversion failures. 搜索、筛选并查看每一次转换失败。
            </p>
          </div>
          <Button variant="outline" onClick={() => setReloadToken((value) => value + 1)}>
            Refresh / 刷新
          </Button>
        </div>

        {statsError ? (
          <Card className="mb-6 border-red-900/60 bg-red-950/20 p-5 text-sm text-red-200">
            统计数据加载失败：{statsError}
          </Card>
        ) : stats ? (
          <section className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <SummaryCard title="Total badcases / 总数" value={stats.total} />
            <SummaryCard title="Top source formats / 源格式 Top 5" entries={topEntries(stats.by_source_format)} />
            <SummaryCard title="Top error types / 错误类型 Top 5" entries={topEntries(stats.by_error_type)} />
            <SummaryCard title="Severity / 严重程度" entries={topEntries(stats.by_severity)} />
          </section>
        ) : (
          <section className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="h-32 rounded-2xl" />)}
          </section>
        )}

        <Card className="mb-6 bg-card/75 p-4 sm:p-5">
          <form onSubmit={submitSearch} className="grid gap-3 md:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_1.4fr_auto]">
            <select
              aria-label="源格式"
              value={sourceFormat}
              onChange={(event) => updateFilter(setSourceFormat, event.target.value)}
              className="h-10 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">全部源格式</option>
              {sourceOptions.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
            <select
              aria-label="目标格式"
              value={targetFormat}
              onChange={(event) => updateFilter(setTargetFormat, event.target.value)}
              className="h-10 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">全部目标格式</option>
              {targetOptions.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
            <select
              aria-label="错误类型"
              value={errorType}
              onChange={(event) => updateFilter(setErrorType, event.target.value)}
              className="h-10 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">全部错误类型</option>
              {errorOptions.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
            <div className="relative">
              <Search className="absolute left-3 top-3 text-muted-foreground" size={16} />
              <input
                aria-label="关键词"
                value={keywordInput}
                onChange={(event) => setKeywordInput(event.target.value)}
                className="h-10 w-full rounded-lg border bg-background pl-9 pr-3 text-sm outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring"
                placeholder="文件名或错误信息"
              />
            </div>
            <Button type="submit">Search / 搜索</Button>
          </form>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t pt-3">
            <button type="button" className="text-xs text-muted-foreground hover:text-foreground" onClick={clearFilters}>
              Clear filters / 清除筛选
            </button>
            <select
              aria-label="排序方式"
              value={sort}
              onChange={(event) => updateFilter(setSort, event.target.value)}
              className="h-8 rounded-md border bg-background px-2 text-xs"
            >
              <option value="captured_at:desc">最新优先</option>
              <option value="captured_at:asc">最早优先</option>
              <option value="file_size:desc">文件从大到小</option>
              <option value="file_size:asc">文件从小到大</option>
            </select>
          </div>
        </Card>

        {loading ? (
          <ListSkeleton />
        ) : error ? (
          <Card className="border-red-900/60 bg-red-950/20 p-8 text-center">
            <AlertTriangle className="mx-auto mb-3 text-red-300" />
            <p className="font-medium">Badcase 加载失败</p>
            <p className="mt-2 text-sm text-red-200">{error}</p>
            <Button className="mt-5" variant="outline" onClick={() => setReloadToken((value) => value + 1)}>
              Retry / 重试
            </Button>
          </Card>
        ) : !result?.items.length ? (
          <Card className="p-12 text-center">
            <DatabaseZap className="mx-auto mb-4 text-muted-foreground" size={32} />
            <p className="font-medium">暂无 badcase</p>
            <p className="mt-2 text-sm text-muted-foreground">调整筛选条件，或先提交一次失败转换。</p>
          </Card>
        ) : (
          <>
            <div className="space-y-3">
              {result.items.map((item) => (
                <Link key={item.case_id} href={`/badcases/${encodeURIComponent(item.case_id)}`} className="group block">
                  <Card className="p-5 transition-colors hover:border-primary/50 hover:bg-card">
                    <div className="flex items-start gap-4">
                      <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-rose-500/10 text-rose-300">
                        <FileWarning size={19} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-md bg-muted px-2 py-1 font-mono text-xs">{item.source_format}</span>
                            <ArrowRight size={14} className="text-muted-foreground" />
                            <span className="rounded-md bg-muted px-2 py-1 font-mono text-xs">{item.target_format}</span>
                            <span className="truncate font-medium">{item.original_filename}</span>
                          </div>
                          <time className="shrink-0 text-xs text-muted-foreground">{formatDate(item.captured_at)}</time>
                        </div>
                        <p className="mt-3 line-clamp-2 break-words text-sm leading-6 text-muted-foreground">{item.error_message}</p>
                        <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
                          <SeverityBadge severity={item.severity} />
                          <span>{item.error_type}</span><span>·</span><span>{formatBytes(item.file_size)}</span>
                        </div>
                      </div>
                      <ArrowRight className="mt-2 hidden text-muted-foreground transition-transform group-hover:translate-x-1 sm:block" size={18} />
                    </div>
                  </Card>
                </Link>
              ))}
            </div>

            <div className="mt-7 flex flex-col items-center justify-between gap-3 sm:flex-row">
              <p className="text-sm text-muted-foreground">
                共 {result.total} 条 · 第 {result.page} / {totalPages} 页
              </p>
              <div className="flex gap-2">
                <Button variant="outline" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
                  Previous / 上一页
                </Button>
                <Button variant="outline" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>
                  Next / 下一页
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
