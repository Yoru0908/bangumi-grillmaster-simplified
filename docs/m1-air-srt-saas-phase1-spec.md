# M1 Air SRT SaaS Phase 1 RHD

> Requirements Hand-off Document。本文把 `m1-air-srt-saas-requirements.md` 收敛成可直接开发和验收的 Phase 1 范围。原则：先做能稳定跑的最小闭环，不把 Stripe、多 worker、文件上传、播放器等后续功能塞进第一版。

## 0. RHD 元信息

| 项目 | 内容 |
|---|---|
| Source of truth | 本文为 Phase 1 开工依据；总需求见 `docs/m1-air-srt-saas-requirements.md` |
| Scope | M1 Air 上的 URL-only / SRT-only / single-worker SaaS MVP |
| Status | Ready for implementation review |
| Target user | 小规模内测用户 / 私用 / 朋友使用 |
| Primary output | `finalized.srt` |
| Downloadable outputs | `source.srt`, `translated.srt`, `finalized.srt` |
| Deployment target | M1 Air Server, API port `8600` |
| Deployment runbook | `docs/m1-air-srt-saas-deployment.md` |
| Billing scope | credit ledger + admin adjustment only |
| Explicitly excluded | Stripe, file upload, video burn-in, ASS exposure, multi-worker, R2/S3 |

### 0.1 开工门禁

开始编码前必须确认：

- 本文中 Phase 1 必做/不做范围无异议。
- `bangumi-grillmaster` 现有本地 pipeline 可在开发机跑出 `finalized.srt`。
- M1 Air 部署目录、数据目录、日志目录已确认。
- Agent Platform backend 若 Phase 1 来不及接入，必须明确使用 SDK fallback 调试模式，不允许实现时临时混用多个 Gemini backend。
- Credit 逻辑以 `credit_ledger` 为准，不允许只做余额字段。
- UI 只做状态准确，不追求产品化视觉。

## 1. Phase 1 核心判断

值得做，但必须砍干净：

- URL only。
- SRT only。
- Invite / allowlist only。
- Single worker。
- Global running job concurrency = 1。
- Credit ledger + admin adjustment。
- 不接 Stripe / Ko-fi / webhook。
- 不做文件上传、ASS、字幕烧录、在线播放器、多 worker。

一句话目标：

```text
已登录用户提交公开视频 URL，系统异步生成 `source.srt`、`translated.srt`、`finalized.srt`，用户可查看进度并下载三种 SRT；其中 `finalized.srt` 是主输出，失败可读、可恢复、可清理、不乱扣额度。
```

## 2. 不变量

这些规则不能靠口头约定，必须写进代码和测试：

1. API 进程不执行长任务，只写 DB 和读状态。
2. Worker 一次只处理一个 video job。
3. 任务状态只通过定义好的状态机迁移。
4. 每次额度变化都必须写 `credit_ledger`，不能只改余额。
5. 任务失败且非用户原因必须 refund 已 reserve 额度。
6. 下载结果必须校验 job owner，admin 访问他人结果必须写审计日志。
7. 成功任务立即删除原视频、音频、抽帧和 chunk 媒体。
8. `finalized.srt` 是 Phase 1 面向用户的主输出；`source.srt` 和 `translated.srt` 也允许下载，用于核对日语原文和翻译中间结果。

## 2.1 验收口径

Phase 1 只按本文验收，不按总需求文档中的 Phase 2/3 方向验收。

验收时看四件事：

1. **功能闭环**：登录用户可以提交 URL，最终下载 `source.srt`、`translated.srt`、`finalized.srt`。
2. **运行稳定**：API/Worker 分离，SQLite WAL，Worker 崩溃不会永久卡死任务。
3. **资金正确**：reserve / consume / refund 都写 ledger，失败不乱扣。
4. **安全底线**：SSRF、下载归属、admin audit、敏感日志脱敏。

不验收：

- UI 美观程度。
- Stripe / Ko-fi。
- 多 worker。
- 文件上传。
- 视频播放器。
- ASS / burn-in。

## 3. Phase 1 范围

### 3.1 必须实现

| 模块 | Phase 1 要求 |
|---|---|
| Auth | allowlist / invite code 登录；HttpOnly cookie session |
| Jobs | submit URL、list own jobs、view job detail、download source/translated/finalized SRT |
| Playground | 低额度/未付费用户可试用 1 分钟以内 URL；metadata 超过 60 秒直接拒绝 |
| Admin | list all jobs、retry failed job、delete/expire job、manual credit adjustment |
| Worker | SQLite polling、heartbeat、single running job、stage checkpoint |
| Pipeline adapter | 调用现有 `bangumi-grillmaster` pipeline，强制 SRT-only |
| Model backend | Gemini 走 Agent Platform；DeepSeek 结构修复优先评估 Agent Platform / MaaS |
| Credits | balance snapshot、ledger、reserve、consume、refund |
| Storage | job workdir、result dir、TTL cleanup |
| Logs | `job_events` 给前端；`job.log` 仅 admin |
| Security | SSRF 防护、最大时长、最大下载大小、下载权限 |

### 3.2 明确不做

| 功能 | Phase |
|---|---|
| Stripe Checkout / webhook | Phase 3 |
| Ko-fi / Afdian payment link | Phase 3 |
| 文件上传 | Phase 3 |
| R2/S3 signed URL | Phase 3 |
| 多 worker | Phase 3 |
| ASS 输出 / 字幕烧录 | Phase 3 |
| 在线播放器 | Phase 3 |
| OAuth 登录 | Phase 2+ |
| Admin cookies Web UI | Phase 2 |

## 4. 运行形态

```text
M1 Air
├─ FastAPI Web/API :8600
├─ Worker process
├─ SQLite WAL database
├─ local job storage
└─ optional Cloudflare Tunnel
```

Phase 1 只要求本机可访问。Cloudflare Tunnel 可以配置，但不作为 MVP 验收前置条件。

启动命令建议：

```text
bootstrap: python -m services.saas.bootstrap_cli --invite-code ... --invite-email ... --initial-credit-minutes 30
api:       python -m services.saas.server_main
worker:    python -m services.saas.worker_main --worker-id worker-1
cleanup:   python -m services.saas.cleanup_daemon
```

## 5. 数据库规格

SQLite 必须启用：

```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
PRAGMA foreign_keys=ON;
```

### 5.1 表

```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL CHECK (role IN ('member', 'admin')),
  status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE invite_codes (
  code_hash TEXT PRIMARY KEY,
  email TEXT,
  role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'admin')),
  used_by_user_id TEXT REFERENCES users(id),
  used_at TEXT,
  expires_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  source_url TEXT NOT NULL,
  source_url_redacted TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'retrying', 'succeeded', 'failed', 'cancelled', 'expired')),
  stage TEXT NOT NULL CHECK (stage IN ('created', 'metadata_fetched', 'video_downloaded', 'audio_extracted', 'asr_completed', 'prepass_completed', 'translated', 'structure_fixed', 'finalized', 'cleanup_completed')),
  current_chunk_index INTEGER NOT NULL DEFAULT 0,
  total_chunks INTEGER NOT NULL DEFAULT 0,
  progress_message TEXT,
  error_code TEXT,
  error_message TEXT,
  video_title TEXT,
  video_duration_seconds INTEGER,
  reserved_minutes REAL NOT NULL DEFAULT 0,
  consumed_minutes REAL NOT NULL DEFAULT 0,
  worker_id TEXT,
  heartbeat_at TEXT,
  source_srt_path TEXT,
  translated_srt_path TEXT,
  result_srt_path TEXT,
  log_path TEXT,
  retry_count INTEGER NOT NULL DEFAULT 0,
  retry_after_seconds INTEGER,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  expires_at TEXT
);

CREATE TABLE job_events (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  level TEXT NOT NULL CHECK (level IN ('info', 'warning', 'error', 'success')),
  stage TEXT NOT NULL,
  code TEXT NOT NULL,
  message TEXT NOT NULL,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE credit_balances (
  user_id TEXT PRIMARY KEY REFERENCES users(id),
  balance_minutes REAL NOT NULL CHECK (balance_minutes >= 0),
  updated_at TEXT NOT NULL
);

CREATE TABLE credit_ledger (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  job_id TEXT REFERENCES jobs(id),
  type TEXT NOT NULL CHECK (type IN ('grant', 'reserve', 'consume', 'refund', 'adjustment')),
  minutes REAL NOT NULL CHECK (minutes > 0),
  reason TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  created_by_user_id TEXT REFERENCES users(id),
  created_at TEXT NOT NULL
);

CREATE TABLE admin_audit_logs (
  id TEXT PRIMARY KEY,
  actor_user_id TEXT NOT NULL REFERENCES users(id),
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);
```

### 5.2 索引

```sql
CREATE INDEX idx_jobs_user_created ON jobs(user_id, created_at DESC);
CREATE INDEX idx_jobs_status_created ON jobs(status, created_at);
CREATE INDEX idx_jobs_worker_heartbeat ON jobs(worker_id, heartbeat_at);
CREATE INDEX idx_job_events_job_created ON job_events(job_id, created_at);
CREATE INDEX idx_credit_ledger_user_created ON credit_ledger(user_id, created_at DESC);
CREATE INDEX idx_admin_audit_target ON admin_audit_logs(target_type, target_id, created_at DESC);
```

## 6. 状态机

### 6.1 Job status

允许迁移：

| From | To | 条件 |
|---|---|---|
| queued | running | Worker 原子 claim job |
| running | retrying | 可恢复上游错误 |
| retrying | running | backoff 到期 |
| running | succeeded | `cleanup_completed` 后成功 |
| running | failed | 不可恢复错误或重试耗尽 |
| queued/running/failed | cancelled | admin 删除或取消 |
| succeeded | expired | 结果 TTL 到期 |

禁止迁移：

- `failed -> succeeded`。必须通过 admin retry 创建一次新的执行尝试或把 status 设回 `queued` 并保留审计日志。
- `expired -> running`。过期结果不恢复执行。
- 普通用户不能直接改变 job status。

### 6.2 Stage 顺序

```text
created
metadata_fetched
video_downloaded
audio_extracted
asr_completed
prepass_completed
translated
structure_fixed
finalized
cleanup_completed
```

Worker 每完成一个 stage 必须：

1. 原子更新 `jobs.stage`。
2. 写一条 `job_events`。
3. 如果该 stage 产生可复用文件，写 manifest 或校验信息。

## 7. Credit 事务

### 7.1 提交流程

```text
POST /api/jobs
  -> auth required
  -> validate URL syntax
  -> check balance >= MIN_SUBMIT_CREDIT_MINUTES
  -> insert job(status=queued, stage=created)
```

### 7.2 Reserve / consume / refund

Worker 获取 metadata 后，在同一个 DB transaction 内：

1. 读取 `credit_balances`。
2. 检查 `balance_minutes >= duration_minutes`。
3. 扣减 balance。
4. 写 `credit_ledger(type='reserve')`。
5. 更新 `jobs.reserved_minutes`。

任务成功：

1. 写 `credit_ledger(type='consume')`，使用同一个 `job_id`。
2. 更新 `jobs.consumed_minutes`。
3. 不再修改 balance，因为 reserve 时已经扣除。

任务失败：

1. 如果 `reserved_minutes > consumed_minutes`，返还差额到 balance。
2. 写 `credit_ledger(type='refund')`。
3. 用户原因失败不退款：`INSUFFICIENT_CREDITS`、`VIDEO_TOO_LONG`、`UNSUPPORTED_URL`、`FORBIDDEN_URL`。

## 8. API 契约

### 8.1 Auth

| Method | Path | Auth | 说明 |
|---|---|---|---|
| POST | `/api/auth/login` | public | email + invite code 登录或创建用户 |
| POST | `/api/auth/logout` | user | 清 session |
| GET | `/api/auth/me` | user | 当前用户 |

### 8.2 Jobs

| Method | Path | Auth | 说明 |
|---|---|---|---|
| POST | `/api/jobs` | member/admin | 提交 URL |
| POST | `/api/playground/jobs` | member/admin | 提交 1 分钟以内试用 URL，不要求最低付费额度 |
| GET | `/api/jobs` | member/admin | 当前用户任务列表 |
| GET | `/api/jobs/{id}` | owner/admin | 任务详情 |
| GET | `/api/jobs/{id}/events` | owner/admin | 任务事件摘要，按创建时间升序 |
| GET | `/api/jobs/{id}/download/source.srt` | owner/admin | 下载日语 ASR 字幕 |
| GET | `/api/jobs/{id}/download/translated.srt` | owner/admin | 下载翻译后字幕 |
| GET | `/api/jobs/{id}/download/finalized.srt` | owner/admin | 下载最终闪轴修复字幕 |

`POST /api/jobs` request:

```json
{
  "source_url": "https://example.com/video"
}
```

`POST /api/playground/jobs` request:

```json
{
  "source_url": "https://example.com/short-video"
}
```

Playground 规则：

- API 先获取 metadata duration。
- `duration <= 60` 秒才创建 job。
- 超过 60 秒返回 `TRIAL_VIDEO_TOO_LONG`，不入队、不下载、不调用 ASR/Gemini。
- playground job 必须标记为 trial，便于后续限流、展示和风控。
- playground 不替代正式额度逻辑；正式 job 仍按 credit reserve/consume/refund。

success response:

```json
{
  "job_id": "job_...",
  "status": "queued",
  "stage": "created"
}
```

### 8.3 Admin

| Method | Path | Auth | 说明 |
|---|---|---|---|
| GET | `/api/admin/jobs` | admin | 全部任务 |
| POST | `/api/admin/jobs/{id}/retry` | admin | 重试失败任务 |
| DELETE | `/api/admin/jobs/{id}` | admin | 删除/取消任务 |
| POST | `/api/admin/users/{id}/credits/adjust` | admin | 手动调整额度 |
| GET | `/api/admin/audit-logs` | admin | 审计日志，返回已解析 `metadata` |

Admin 操作必须写 `admin_audit_logs`。

## 9. 错误码

| code | HTTP/status | 说明 |
|---|---|---|
| `AUTH_REQUIRED` | 401 | 未登录 |
| `FORBIDDEN` | 403 | 无权限 |
| `INVALID_URL` | 400 | URL 格式错误 |
| `FORBIDDEN_URL` | 400 | SSRF / localhost / private IP |
| `UNSUPPORTED_URL` | job failed | yt-dlp 不支持 |
| `VIDEO_TOO_LONG` | job failed | 超过最大时长 |
| `FILE_TOO_LARGE` | job failed | 超过最大下载大小 |
| `INSUFFICIENT_CREDITS` | job failed | 额度不足 |
| `DOWNLOAD_FAILED` | job failed/retrying | 下载失败 |
| `COOKIES_EXPIRED_OR_REQUIRED` | job failed | 需要管理员更新 cookies |
| `ASR_FAILED` | job failed/retrying | ElevenLabs 失败 |
| `GEMINI_FAILED` | job failed/retrying | Gemini 失败 |
| `STRUCTURE_FIX_FAILED` | job failed/retrying | DeepSeek 修复失败 |
| `FINALIZE_FAILED` | job failed | SRT finalize 失败 |
| `INTERNAL_ERROR` | 500/job failed | 未分类内部错误 |

## 10. Pipeline adapter 契约

Phase 1 不让 Web/API 直接拼现有 CLI 参数。必须有一个 adapter 函数或类隔离旧 pipeline：

```text
run_subtitle_job(
  job_id,
  source_url,
  work_dir,
  output_dir,
  translation_hint=None,
  srt_only=True,
  disable_refine=True,
  disable_cover=True,
  disable_archive=True,
  disable_package=True,
  event_sink=...
) -> SubtitleJobResult
```

`SubtitleJobResult` 必须包含：

```text
source_srt_path
translated_srt_path
finalized_srt_path
video_title
video_duration_seconds
usage_summary
```

Phase 1 强制关闭：

- ASS 输出对用户暴露。
- Codex refine。
- cover generation。
- archive path。
- package / burn-in。

## 11. 文件系统

```text
~/services/bangumi-grillmaster/
~/data/bangumi-grillmaster/jobs/{job_id}/
~/data/bangumi-grillmaster/results/{job_id}/source.srt
~/data/bangumi-grillmaster/results/{job_id}/translated.srt
~/data/bangumi-grillmaster/results/{job_id}/finalized.srt
~/logs/bangumi-grillmaster/
```

成功后保留：

- `results/{job_id}/source.srt`
- `results/{job_id}/translated.srt`
- `results/{job_id}/finalized.srt`
- `jobs/{job_id}/output/source.srt`
- `jobs/{job_id}/output/translated.srt`
- `jobs/{job_id}/cache/pre_pass.json`
- `jobs/{job_id}/job.log`

成功后删除：

- 原视频。
- 音频。
- 抽帧图片。
- chunk 音频。
- 临时媒体切片。

## 12. 前端页面

| Page | Phase 1 验收 |
|---|---|
| `/` | 产品说明、登录入口 |
| `/jobs/new` | URL 输入、最大时长提示、提交后跳转 job detail |
| `/jobs` | 当前用户任务列表 |
| `/jobs/{id}` | stage、进度、错误、事件摘要、source/translated/finalized 三个下载按钮 |
| `/billing` | 当前余额、最近 ledger |
| `/account` | 当前账号、退出登录 |
| `/admin/jobs` | admin 任务列表、retry/delete |

页面不用花哨，先把状态展示准确。状态错了，UI 再漂亮也是垃圾。

## 13. 配置项

```text
APP_BASE_URL=http://localhost:8600
DATABASE_URL=sqlite:////Users/yoru/data/bangumi-grillmaster/app.db
JOB_DATA_DIR=/Users/yoru/data/bangumi-grillmaster/jobs
JOB_RESULT_DIR=/Users/yoru/data/bangumi-grillmaster/results
LOG_DIR=/Users/yoru/logs/bangumi-grillmaster

GLOBAL_JOB_CONCURRENCY=1
WORKER_POLL_INTERVAL_SECONDS=5
WORKER_HEARTBEAT_INTERVAL_SECONDS=20
RUNNING_JOB_HEARTBEAT_TIMEOUT_SECONDS=120

MAX_VIDEO_DURATION_SECONDS=3600
MAX_DOWNLOAD_BYTES=2147483648
MIN_SUBMIT_CREDIT_MINUTES=10
RESULT_TTL_DAYS=14
FAILED_JOB_TMP_TTL_HOURS=24

YTDLP_COOKIES_TXT_PATH=/Users/yoru/secrets/bangumi-cookies.txt

ELEVENLABS_ASR_CONCURRENCY=1
ASR_MAX_RETRIES=2

GEMINI_BACKEND=agent_platform
GEMINI_CHUNK_CONCURRENCY=2
GEMINI_ALLOW_CROSS_BACKEND_FALLBACK=false

DEEPSEEK_BACKEND=agent_platform_maas
DEEPSEEK_ALLOW_DIRECT_FALLBACK=false
```

## 13.1 Model backend 约束

Phase 1 不把 Gemini 和 DeepSeek 写死成两套不可控直连逻辑：

- Gemini 翻译默认走 Agent Platform。
- DeepSeek 结构修复优先验证 Agent Platform / MaaS open models API。
- DeepSeek 只有在 MaaS 不可用时才允许显式配置 fallback 到 direct OpenAI-compatible endpoint。
- 跨 backend fallback 默认关闭，避免重复扣费和 quota 失控。
- usage/cost/retry/backend/model/endpoint 必须写入内部日志；前端 job event 只展示脱敏摘要。
- 所有 Agent Platform / MaaS / DeepSeek 凭据只能来自服务端环境变量或 secret store，不能进入文档、前端、job log 或 `job_events`。

## 14. Phase 1 验收清单

### 14.1 成功路径

1. admin 创建或发放 invite。
2. member 登录成功。
3. admin 给 member 增加 30 minutes。
4. member 提交 5-10 分钟 URL。
5. job 从 `queued -> running -> succeeded`。
6. stage 到 `cleanup_completed`。
7. member 下载 `source.srt`、`translated.srt`、`finalized.srt`。
8. 原视频、音频、抽帧、chunk 媒体已删除。
9. `credit_ledger` 有 reserve 和 consume。

### 14.2 失败路径

| 场景 | 预期 |
|---|---|
| 未登录提交 | 401 `AUTH_REQUIRED` |
| 余额低于最低提交门槛 | 400 或 job 拒绝，不能入队 |
| metadata 后余额不足 | job failed `INSUFFICIENT_CREDITS`，不下载视频 |
| 超过最大时长 | job failed `VIDEO_TOO_LONG`，不调用 ASR/Gemini |
| localhost/private IP URL | 400 `FORBIDDEN_URL` |
| 普通用户下载他人 job | 403 `FORBIDDEN` |
| ASR 临时 429/503 | retrying 后继续或重试耗尽 failed |
| Worker 中途崩溃 | 重启后识别 stale running job 并安全处理 |
| 结果过期 | 文件删除，job status `expired` |

### 14.3 最小测试

```text
unit:
  - URL SSRF validator
  - status/stage transition validator
  - credit reserve/consume/refund transaction
  - credit idempotency replay
  - download permission
  - admin-only routes

integration:
  - submit job -> worker claim -> fake pipeline success
  - fake pipeline failure -> refund
  - stale running job recovery
  - cleanup deletes media but keeps source/translated/finalized SRT
  - expired result cleanup deletes all downloadable SRT
  - playground trial <= 60 seconds without paid credits
```

## 15. 开工顺序

1. 先建 DB schema 和状态机校验。
2. 再做 Auth / allowlist。
3. 再做 credit ledger 和 admin adjustment。
4. 再做 Jobs API，不接真实 pipeline，先用 fake worker 跑通状态。
5. 再接 pipeline adapter。
6. 最后做 UI。

不要反过来。先写 UI 等于先刷油漆，房梁还没搭。

## 16. RHD 交付清单

开发开始前，本 RHD 需要被拆成以下工程任务：

| 顺序 | 任务 | 交付物 | 验收方式 |
|---:|---|---|---|
| 1 | DB + migration | SQLite schema, WAL init | migration test / pragma check |
| 2 | 状态机与错误码 | status/stage validator | unit tests |
| 3 | Auth | login/logout/me, sessions | API tests |
| 4 | Credit ledger | balance, reserve, consume, refund, adjustment | transaction tests |
| 5 | Jobs API | submit/list/detail/download | API tests |
| 6 | Fake worker | polling, claim, heartbeat, fake success/fail | integration tests |
| 7 | Pipeline adapter | existing workflow wrapper | local real job smoke test |
| 8 | Cleanup | media deletion, result retention | filesystem test |
| 9 | Admin | retry/delete/audit/adjustment | API tests |
| 10 | Minimal frontend | jobs/new/detail/billing/account/admin | manual acceptance |

## 17. Definition of Done

Phase 1 完成必须同时满足：

- 一条真实公开视频 URL 可以从提交跑到 `source.srt`、`translated.srt`、`finalized.srt` 下载。
- API 和 Worker 是两个进程。
- SQLite 开启 WAL，前端轮询状态时 Worker 更新不会触发 `database is locked`。
- 任务成功后视频/音频/抽帧/chunk 媒体被删除。
- 普通用户不能下载他人任务结果。
- admin 下载他人结果、调整额度、retry/delete 都写审计日志。
- `credit_ledger` 能解释每一次余额变化。
- Worker 重启后 stale `running` job 不会永久卡住。
- 至少覆盖 RHD 第 14.3 节最小测试。

## 18. RHD 变更规则

实现过程中如果要改变以下内容，必须先更新本文：

- DB schema。
- API path / request / response。
- Job status / stage。
- credit ledger 语义。
- 文件保留 / 清理策略。
- Phase 1 做/不做边界。

普通实现细节可以直接在代码中演进，但不能突破本文定义的交付边界。
