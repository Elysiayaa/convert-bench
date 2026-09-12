"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertTriangle, ArrowLeft, Check, Clipboard, FileWarning } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchJson } from "@/lib/api";
import { BadCase, formatBytes, formatDate } from "@/lib/badcases";

function DetailSkeleton() {
  return (
    <Card className="space-y-5 p-6 sm:p-8">
      <Skeleton className="h-8 w-64" />
      {Array.from({ length: 6 }, (_, index) => (
        <div key={index} className="space-y-2">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-5 w-full max-w-xl" />
        </div>
      ))}
    </Card>
  );
}

export default function BadCaseDetailPage() {
  const params = useParams<{ case_id: string }>();
  const caseId = params.case_id;
  const [item, setItem] = useState<BadCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");

  const loadBadCase = useCallback(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    fetchJson<BadCase>(`/api/badcases/${encodeURIComponent(caseId)}`, {
      signal: controller.signal,
    })
      .then(setItem)
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") return;
        setItem(null);
        setError(requestError instanceof Error ? requestError.message : "Badcase 加载失败");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [caseId]);

  useEffect(() => loadBadCase(), [loadBadCase]);

  async function copyJson() {
    if (!item) return;
    setCopyError("");
    try {
      await navigator.clipboard.writeText(JSON.stringify(item, null, 2));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch (copyError: unknown) {
      setCopyError(copyError instanceof Error ? copyError.message : "复制失败，请手动复制");
    }
  }

  return (
    <main className="min-h-[calc(100vh-4rem)] bg-[radial-gradient(circle_at_top_right,_rgba(244,63,94,0.1),_transparent_32%)]">
      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 sm:py-14">
        <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="mb-2 text-sm font-medium text-rose-300">Badcase detail / 失败详情</p>
            <h1 className="text-3xl font-semibold tracking-tight">Conversion failure</h1>
          </div>
          <Button asChild variant="outline">
            <Link href="/badcases"><ArrowLeft className="mr-2" size={16} />返回列表</Link>
          </Button>
        </div>

        {loading ? (
          <DetailSkeleton />
        ) : error ? (
          <Card className="border-red-900/60 bg-red-950/20 p-10 text-center">
            <AlertTriangle className="mx-auto mb-3 text-red-300" />
            <p className="font-medium">无法加载 badcase</p>
            <p className="mt-2 text-sm text-red-200">{error}</p>
            <Button className="mt-5" variant="outline" onClick={loadBadCase}>Retry / 重试</Button>
          </Card>
        ) : !item ? (
          <Card className="p-12 text-center">
            <FileWarning className="mx-auto mb-4 text-muted-foreground" />
            <p>暂无 badcase</p>
          </Card>
        ) : (
          <Card className="overflow-hidden bg-card/85 shadow-2xl shadow-black/10">
            <div className="flex flex-col justify-between gap-4 border-b p-6 sm:flex-row sm:items-center sm:p-8">
              <div className="flex min-w-0 items-center gap-4">
                <div className="grid size-12 shrink-0 place-items-center rounded-2xl bg-rose-500/10 text-rose-300">
                  <FileWarning size={22} />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-lg font-semibold">{item.original_filename}</p>
                  <p className="mt-1 font-mono text-sm text-muted-foreground">{item.source_format} → {item.target_format}</p>
                </div>
              </div>
              <Button onClick={copyJson} variant="outline">
                {copied ? <Check className="mr-2 text-primary" size={16} /> : <Clipboard className="mr-2" size={16} />}
                {copied ? "已复制" : "复制 JSON"}
              </Button>
              {copyError && <p className="text-sm text-red-300">{copyError}</p>}
            </div>

            <dl className="grid gap-px bg-border sm:grid-cols-2">
              {[
                ["Case ID", item.case_id],
                ["Original filename / 原文件名", item.original_filename],
                ["Source format / 源格式", item.source_format],
                ["Target format / 目标格式", item.target_format],
                ["File size / 文件大小", `${formatBytes(item.file_size)} (${item.file_size} bytes)`],
                ["Error type / 错误类型", item.error_type],
                ["Captured at / 采集时间", formatDate(item.captured_at)],
              ].map(([label, value]) => (
                <div key={label} className="min-w-0 bg-card p-5 sm:p-6">
                  <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</dt>
                  <dd className="mt-2 break-words font-mono text-sm">{value}</dd>
                </div>
              ))}
              <div className="bg-card p-5 sm:col-span-2 sm:p-6">
                <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Error message / 错误信息</dt>
                <dd className="mt-3 whitespace-pre-wrap break-words rounded-xl border bg-background p-4 font-mono text-sm leading-6 text-red-200">
                  {item.error_message}
                </dd>
              </div>
            </dl>
          </Card>
        )}
      </div>
    </main>
  );
}
