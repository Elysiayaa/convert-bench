"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, Database, FileUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { API_BASE_URL } from "@/lib/api";

type Conversion = {
  id: string;
  status: "pending" | "succeeded" | "failed";
  source_format: string;
  target_format: string;
  original_filename: string;
  error_message: string | null;
};

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [targetFormat, setTargetFormat] = useState("md");
  const [result, setResult] = useState<Conversion | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return setMessage("请先选择一个文件 / Please choose a file.");

    setLoading(true);
    setMessage("");
    const body = new FormData();
    body.append("file", file);
    body.append("target_format", targetFormat);

    try {
      const response = await fetch(`${API_BASE_URL}/api/conversions`, { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Request failed");
      setResult(data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unknown error / 未知错误");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-[calc(100vh-4rem)] overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.16),_transparent_35%)]">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-6xl flex-col px-6">
        <section className="grid flex-1 items-center gap-14 py-16 lg:grid-cols-[1.05fr_.95fr]">
          <div>
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border bg-card/70 px-3 py-1 text-xs text-muted-foreground">
              <Database size={14} /> Failure becomes data / 让失败变成数据
            </div>
            <h1 className="max-w-2xl text-5xl font-semibold leading-[1.05] tracking-[-0.04em] sm:text-7xl">
              Convert files.<br /><span className="text-primary">Learn from failure.</span>
            </h1>
            <p className="mt-7 max-w-xl text-lg leading-8 text-muted-foreground">
              一个专注于格式转换的 agent。每次失败都会自动沉淀为可评测、可回放的数据集样本。
            </p>
          </div>

          <form onSubmit={submit} className="rounded-3xl border bg-card/80 p-6 shadow-2xl shadow-emerald-950/20 backdrop-blur sm:p-8">
            <div className="mb-7 flex items-center gap-3">
              <div className="grid size-11 place-items-center rounded-2xl bg-muted"><FileUp size={21} /></div>
              <div><h2 className="font-semibold">New conversion / 新建转换</h2><p className="text-sm text-muted-foreground">TXT、Markdown MVP pipeline</p></div>
            </div>

            <label className="block text-sm font-medium">Source file / 源文件</label>
            <input
              className="mt-2 block w-full cursor-pointer rounded-xl border bg-background p-3 text-sm file:mr-4 file:rounded-lg file:border-0 file:bg-muted file:px-3 file:py-2 file:text-foreground"
              type="file"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />

            <label className="mt-5 block text-sm font-medium" htmlFor="target">Target format / 目标格式</label>
            <input
              id="target"
              className="mt-2 h-11 w-full rounded-xl border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={targetFormat}
              onChange={(event) => setTargetFormat(event.target.value)}
              placeholder="md"
            />

            <Button className="mt-6 w-full gap-2" size="lg" disabled={loading}>
              {loading ? "Converting / 转换中…" : "Start conversion / 开始转换"}<ArrowRight size={17} />
            </Button>

            {message && <p className="mt-4 text-sm text-red-300">{message}</p>}
            {result && (
              <div className="mt-5 rounded-xl border bg-background/70 p-4 text-sm">
                <p className="font-medium">Task {result.id.slice(0, 8)} · {result.status}</p>
                <p className="mt-1 text-muted-foreground">{result.source_format} → {result.target_format}</p>
                {result.error_message && <p className="mt-2 text-red-300">{result.error_message}</p>}
                {result.status === "succeeded" && (
                  <a
                    className="mt-3 inline-block font-medium text-primary hover:underline"
                    href={`${API_BASE_URL}/api/conversions/${result.id}/download`}
                  >
                    Download result / 下载结果
                  </a>
                )}
              </div>
            )}
          </form>
        </section>
      </div>
    </main>
  );
}
