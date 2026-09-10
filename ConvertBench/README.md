# ConvertBench

> **Convert anything. Learn from every failure.** 让每一次格式转换失败，都成为下一次成功的数据。

ConvertBench is a format-conversion agent that turns failed conversion attempts into structured, replayable datasets.  
ConvertBench 是一个格式转换 Agent：负责执行转换，并将失败请求自动沉淀为结构化、可回放的数据集。

[![Status](https://img.shields.io/badge/status-MVP-f59e0b?style=flat-square)](#roadmap--后续方向)
[![License](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node.js-20%2B-339933?style=flat-square&logo=node.js&logoColor=white)](https://nodejs.org/)

## Why ConvertBench / 为什么做这个

File conversion is easy on the happy path and difficult at the edges: malformed documents, unusual encodings, missing fonts, unsupported codecs, and tool-specific behavior all create failures that are usually discarded.  
格式转换在理想输入下并不复杂，真正困难的是损坏文件、特殊编码、字体缺失、编解码器不兼容和工具差异，而这些失败信息通常被直接丢弃。

ConvertBench closes that loop:

1. **Convert / 转换** — receive a file and execute the matching conversion path.
2. **Capture / 采集** — record failed requests, metadata, and error context as JSONL.
3. **Improve / 迭代** — use accumulated cases for evaluation, regression tests, labeling, and agent improvement.

The goal is not only to build another converter, but to build a system that becomes more reliable as it encounters real-world failures.  
目标不只是再做一个转换工具，而是构建一个能从真实失败中持续变强的转换系统。

## Demo / 演示

> 🚧 Demo assets are coming soon / 演示素材即将补充。

The current Web UI supports file upload, target-format selection, conversion status display, and result download.  
当前 Web 界面已支持文件上传、目标格式选择、转换状态展示和结果下载。

```text
[ Select file / 选择文件 ] → [ Choose format / 选择格式 ]
                              ↓
                     [ Start conversion ]
                              ↓
                 succeeded → download result
                 failed    → append JSONL dataset
```

## Features / 当前能力

- **End-to-end workflow / 完整链路** — upload, convert, query status, and download output.
- **Failure-as-data / 失败即数据** — failed conversions are appended to a reusable JSONL dataset automatically.
- **Built-in converters / 内置转换器** — UTF-8 TXT and Markdown conversion, plus same-extension copying.
- **Persistent records / 任务持久化** — SQLAlchemy models backed by SQLite.
- **Local-first storage / 本地优先存储** — explicit directories for inputs, outputs, and datasets.
- **Modern Web UI / 现代前端** — Next.js 14, TypeScript, Tailwind CSS, and shadcn/ui conventions.
- **Typed API / 类型化接口** — FastAPI, Pydantic schemas, and interactive OpenAPI documentation.
- **Container-ready / 容器化运行** — separate images orchestrated by Docker Compose.

> ConvertBench is currently an MVP. The text converters establish the full data loop; production document, image, and media engines are planned.  
> ConvertBench 当前处于 MVP 阶段。文本转换器用于打通完整数据闭环，文档、图片和音视频引擎将在后续接入。

## Supported formats / 支持格式

| Source / 源格式 | Target / 目标格式 | Status / 状态 | Behavior / 行为 |
|---|---|---|---|
| `txt` | `md` | ✅ Supported | Adds a title and preserves UTF-8 text / 添加标题并保留 UTF-8 文本 |
| `md` | `txt` | ✅ Supported | Removes common Markdown markers / 移除常见 Markdown 标记 |
| Any valid extension | Same extension | ✅ Supported | Copies without content transformation / 原样复制文件 |
| PDF / Office | Multiple formats | 🗓️ Planned | LibreOffice and Pandoc / 计划接入 LibreOffice、Pandoc |
| Images | Multiple formats | 🗓️ Planned | ImageMagick or equivalent / 计划接入 ImageMagick 等工具 |
| Audio / Video | Multiple formats | 🗓️ Planned | FFmpeg / 计划接入 FFmpeg |

Target extensions must contain 1–16 lowercase letters or digits after normalization. Unsupported pairs are recorded as failed cases instead of being silently ignored.  
目标扩展名标准化后必须由 1–16 个小写字母或数字组成。不支持的组合会被记录为失败案例，而不是静默忽略。

## Architecture / 架构

```text
┌──────────────────────────────┐
│ Browser / 浏览器             │
└──────────────┬───────────────┘
               │ HTTP + multipart/form-data
               ▼
┌──────────────────────────────┐
│ Next.js 14 Web UI            │
│ TypeScript · Tailwind · UI   │
└──────────────┬───────────────┘
               │ REST API
               ▼
┌─────────────────────────────────────────────────────┐
│ FastAPI Backend / 后端                              │
│                                                     │
│  API endpoints ──► Conversion service / 转换服务    │
│        │                    │                       │
│        │                    ├── success / 成功      │
│        │                    │      └── output file  │
│        │                    │                       │
│        │                    └── failure / 失败      │
│        │                           └── JSONL dataset │
│        ▼                                            │
│  SQLAlchemy ──► SQLite task records / 任务记录      │
└───────────────────────┬─────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│ Local storage / 本地存储                            │
│ uploads/ · outputs/ · datasets/ · data/*.db         │
└─────────────────────────────────────────────────────┘
```

Key directories / 核心目录：

```text
ConvertBench/
├── frontend/                       # Next.js 前端
│   ├── app/                        # App Router 页面
│   ├── components/ui/              # shadcn/ui 组件
│   └── lib/                        # 前端工具函数
├── backend/
│   ├── app/
│   │   ├── api/endpoints/          # HTTP 接口
│   │   ├── core/                   # 运行配置
│   │   ├── db/                     # 数据库连接
│   │   ├── models/                 # SQLAlchemy 模型
│   │   ├── schemas/                # Pydantic 数据结构
│   │   └── services/               # 转换与数据集逻辑
│   ├── data/                       # SQLite 数据库
│   └── storage/
│       ├── uploads/                # 原始上传文件
│       ├── outputs/                # 转换结果
│       └── datasets/               # JSONL 失败数据集
└── docker-compose.yml
```

## Quick start with Docker / Docker 快速启动

Requirements / 环境要求：Docker Engine 24+ and Docker Compose v2.

```bash
git clone <your-repository-url>
cd ConvertBench

# 可选：复制端口配置，默认前端 3000、后端 8000
cp .env.example .env
docker compose up --build
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

| Service / 服务 | URL |
|---|---|
| Web UI / 前端界面 | <http://localhost:3000> |
| OpenAPI docs / API 文档 | <http://localhost:8000/docs> |
| Health check / 健康检查 | <http://localhost:8000/api/health> |

Stop services / 停止服务：

```bash
docker compose down
```

SQLite data and local files are bind-mounted under `backend/data` and `backend/storage`, so a normal container restart does not remove them.  
SQLite 数据与本地文件通过目录挂载持久化，普通容器重启不会删除这些数据。

## Local development / 本地开发

### Backend / 后端

Python 3.11 is required / 需要 Python 3.11：

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

macOS or Linux:

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend / 前端

Node.js 20+ is required / 需要 Node.js 20 或更高版本：

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

On Windows, replace `cp` with `Copy-Item`. Run `npm run typecheck` and `npm run lint` before submitting changes.  
Windows 环境请将 `cp` 替换为 `Copy-Item`。提交修改前建议运行类型检查与代码检查。

## API overview / API 概览

| Method | Endpoint | Description / 说明 |
|---|---|---|
| `GET` | `/api/health` | Check backend health / 检查后端健康状态 |
| `POST` | `/api/conversions` | Upload and convert a file / 上传文件并执行转换 |
| `GET` | `/api/conversions` | List the latest 100 tasks / 查询最近 100 条任务 |
| `GET` | `/api/conversions/{id}` | Get one task / 查询单个任务 |
| `GET` | `/api/conversions/{id}/download` | Download a successful output / 下载成功任务的结果 |

Create a conversion / 创建转换任务：

```bash
curl -X POST "http://localhost:8000/api/conversions" \
  -F "file=@example.txt" \
  -F "target_format=md"
```

Example response / 响应示例：

```json
{
  "id": "d4348d1c-e666-4c67-8c74-8168f7341e20",
  "original_filename": "example.txt",
  "source_format": "txt",
  "target_format": "md",
  "status": "succeeded",
  "file_size": 128,
  "output_path": "storage/outputs/d4348d1c-e666-4c67-8c74-8168f7341e20/example.md",
  "error_message": null,
  "created_at": "2026-09-11T08:00:00Z"
}
```

## Dataset format / 数据集格式

When a converter raises an exception or a format pair is unsupported, the task is marked as `failed` and one JSON object is appended to:  
转换器抛出异常或格式组合不受支持时，任务会标记为 `failed`，并向以下文件追加一条 JSON 记录：

```text
backend/storage/datasets/conversion_failures.jsonl
```

Example JSONL record / JSONL 样例（实际文件中每行一条）：

```json
{"case_id":"aa3f1208-9b70-4f4d-b460-f5e94a43e51b","original_filename":"report.pdf","source_format":"pdf","target_format":"docx","file_size":48291,"error_message":"Unsupported conversion: pdf -> docx / 暂不支持该格式","captured_at":"2026-09-11T08:10:30.120000+00:00"}
```

| Field / 字段 | Type / 类型 | Description / 说明 |
|---|---|---|
| `case_id` | `string` | Conversion task UUID / 转换任务 UUID |
| `original_filename` | `string` | Original uploaded filename / 原始上传文件名 |
| `source_format` | `string` | Normalized source extension / 标准化后的源扩展名 |
| `target_format` | `string` | Requested target extension / 请求的目标扩展名 |
| `file_size` | `integer` | Uploaded size in bytes / 上传大小，单位为字节 |
| `error_message` | `string` | Exception or rejection reason / 转换异常或拒绝原因 |
| `captured_at` | `string` | UTC ISO 8601 capture time / UTC ISO 8601 采集时间 |

The dataset stores metadata and error context, not a duplicate of file contents. Source files remain under `storage/uploads/{case_id}`.  
数据集只保存元数据与错误上下文，不重复写入文件内容；原始文件保留在 `storage/uploads/{case_id}` 中。

## Adding a converter / 添加转换器

Converter routing lives in [`backend/app/services/converter.py`](./backend/app/services/converter.py). Add a branch to `convert_file`, write the result into `output_dir`, and return the resulting `Path`.  
转换路由集中在 `convert_file` 函数中。新增格式时，将结果写入 `output_dir` 并返回输出文件路径。

```python
def convert_file(source: Path, output_dir: Path, target_format: str) -> Path:
    source_format = normalize_format(source.suffix)
    target_format = normalize_format(target_format)
    output = output_dir / f"{source.stem}.{target_format}"

    if (source_format, target_format) == ("csv", "json"):
        # 在这里实现 CSV 到 JSON 的转换逻辑
        convert_csv_to_json(source, output)
        return output

    # 未匹配的格式必须抛出异常，系统会自动采集失败样本
    raise UnsupportedConversionError(
        f"Unsupported conversion: {source_format} -> {target_format}"
    )
```

For external engines, add the Python dependency to `backend/requirements.txt` or install the system package in `backend/Dockerfile`. Keep errors descriptive because they become evaluation signals.  
如果依赖外部引擎，请同步修改 `backend/requirements.txt` 或 `backend/Dockerfile`。错误信息应具体明确，因为它们会成为后续评测信号。

- Validate successful and malformed inputs / 验证正常与异常输入。
- Keep output deterministic where possible / 尽量保证输出可复现。
- Never overwrite the uploaded source / 不覆盖原始上传文件。
- Update the supported-formats table / 更新支持格式表。
- Confirm failures appear in JSONL / 确认失败案例能够进入 JSONL。

## Roadmap / 后续方向

| Conversion capabilities / 转换能力 | Data capabilities / 数据能力 |
|---|---|
| LibreOffice for Office documents / Office 文档转换 | Failure clustering and deduplication / 失败聚类与去重 |
| Pandoc for document and markup formats / 文档与标记语言转换 | Human labeling workflow / 人工标注流程 |
| ImageMagick for image pipelines / 图片转换链路 | Sensitive-data detection and redaction / 敏感数据识别与脱敏 |
| FFmpeg for audio and video / 音视频转换 | Benchmark replay and regression evaluation / 基准回放与回归评测 |
| Planner + tool registry for multi-step conversion / 多步转换规划 | Dataset versioning and export / 数据集版本管理与导出 |
| File sniffing, limits, scanning, and job queues / 类型嗅探、限流、扫描与任务队列 | Quality scoring and failure taxonomy / 质量评分与失败分类 |
| PostgreSQL and S3 production profile / PostgreSQL 与 S3 生产配置 | Governance and retention policies / 数据治理与保留策略 |

## Contributing / 如何贡献

Contributions are welcome, especially new converters, failure cases, tests, and documentation improvements.  
欢迎贡献新的转换器、失败案例、测试和文档改进。

1. Fork the repository and create a focused branch / Fork 仓库并创建单一目的分支。
2. Implement the change; use Chinese for comments where comments are needed / 实现修改，必要注释使用中文。
3. Update documentation and validate new conversion pairs / 更新文档并验证新增格式组合。
4. Run backend checks and frontend lint/type checks / 执行后端检查以及前端 lint、类型检查。
5. Open a pull request with behavior, limitations, and sample inputs / 提交 PR，说明行为、限制与样例输入。

Do not commit uploads, outputs, SQLite databases, credentials, or private datasets.  
请勿提交上传文件、转换产物、SQLite 数据库、凭据或私有数据集。

## FAQ

<details>
<summary><strong>Is ConvertBench production-ready? / 可以直接用于生产环境吗？</strong></summary>

Not yet. This MVP is intended for local development and architecture validation. Production use still needs authentication, upload limits, malware scanning, async jobs, stronger isolation, and retention controls.  
暂时不建议。当前版本用于本地开发与架构验证；生产环境仍需认证、上传限制、恶意文件扫描、异步任务、强隔离和数据保留策略。
</details>

<details>
<summary><strong>Why create a failed task for an unsupported format? / 为什么不支持的格式仍会创建任务？</strong></summary>

Unsupported requests are valuable product signals. Recording them makes each case available for categorization, replay, and future support.  
不支持的请求本身就是有价值的产品信号。记录任务后，可以对案例进行分类、回放并逐步补齐能力。
</details>

<details>
<summary><strong>Does JSONL contain file contents? / JSONL 是否包含文件内容？</strong></summary>

No. It contains metadata and error context only. Apply privacy, retention, and deletion policies before handling real user data.  
不包含。JSONL 仅保存元数据与错误上下文。处理真实用户数据前，请制定隐私、保留与删除策略。
</details>

<details>
<summary><strong>Can SQLite and local storage be replaced? / 可以替换 SQLite 和本地存储吗？</strong></summary>

Yes. They are simple MVP defaults. A production profile can use PostgreSQL and S3-compatible object storage.  
可以。它们是便于快速启动的默认方案，生产环境可替换为 PostgreSQL 和 S3 兼容对象存储。
</details>

<details>
<summary><strong>Where should agent planning be added? / Agent 规划能力应该放在哪里？</strong></summary>

Add a planner and tool registry above the conversion service while keeping each converter deterministic and independently testable.  
建议在转换服务之上增加 planner 与 tool registry，同时保持每个转换器确定、独立、可测试。
</details>

## License

ConvertBench is released under the [MIT License](./LICENSE).  
ConvertBench 基于 [MIT License](./LICENSE) 开源。
