# M1 Air SRT SaaS 需求文档

> Phase 1 的可执行开发/验收规格见 `docs/m1-air-srt-saas-phase1-spec.md`。本文保留完整需求背景、Phase 2/3 方向和待验证问题；真正开工以 Phase 1 spec 为准。

## 1. 项目定位

将 `bangumi-grillmaster` 包装为运行在家用 M1 Air Server 上的轻量 SaaS，用于从公开视频 URL 自动生成中文字幕 SRT。

第一版不做通用视频翻译平台，而是聚焦：

- 日语综艺 / 广播 / 偶像内容
- URL 输入
- SRT-only 输出
- 高质量术语一致性
- 结构可靠性与闪轴修复
- 小规模内测 / 私用 / 朋友使用

核心链路：

```text
Video URL
  → 下载视频
  → 提取音频 / 抽帧
  → ElevenLabs Scribe v2 ASR
  → Gemini 多模态 pre-pass
  → Gemini chunk 翻译
  → DeepSeek 结构修复
  → 合并 / 清理 / snap-gap 闪轴修复
  → 输出 finalized.srt
```

### 1.1 `bangumi-grillmaster` 当前状态与封装边界

SaaS 层不是重写字幕核心逻辑，而是在现有 `bangumi-grillmaster` pipeline 外新增 Web/API、任务队列、用户系统、额度系统和清理机制。

当前可视为已存在的核心能力：

| 能力 | 状态 | 说明 |
|---|---|---|
| URL/视频信息获取 | 已有 | 现有 workflow 使用 `yt-dlp` 获取元数据与下载视频 |
| 音频提取 / 抽帧 | 已有 | 由 media 处理模块承担 |
| ElevenLabs Scribe v2 ASR | 已有 | 需要在 SaaS 阶段补并发、费用、失败重试限制 |
| Gemini pre-pass / chunk 翻译 | 已有 | 当前通过 Google GenAI SDK 直连，需要新增 Agent Platform adapter |
| DeepSeek 结构修复 | 已有 | 作为 chunk 输出结构不稳定时的修复层 |
| finalize / SRT 输出 | 已有 | 已加入 snap-gap 闪轴修复，SRT-only SaaS 可直接复用 |
| Web/API/用户/计费/任务看板 | 待实现 | SaaS 层新增 |
| Worker queue / crash recovery | 待实现 | SaaS 层新增 |
| 自动清理策略 | 待实现 | SaaS 层新增 |

Phase 1 的工作量主要来自“把现有同步/CLI pipeline 包装成可恢复的异步任务系统”，而不是重写 ASR/翻译/finalize 本身。

## 2. 运行环境结论

M1 Air Server 对第一版需求完全够用，原因是：

- 不自建 ASR 模型
- 不自建翻译模型
- 不压制视频
- 不支持大文件上传
- 本地主要承担下载、FFmpeg 处理、抽帧、缓存、任务编排

推荐限制：

| 项目 | 建议值 |
|---|---|
| 全局视频任务并发 | 1 |
| 单任务 Gemini chunk 并发 | 2-3 起步，稳定后可调到 3-5 |
| 最大视频时长 | 30-60 分钟 |
| 输出格式 | SRT only |
| 输入方式 | URL only |
| 中间文件保留 | 任务完成后立即删除，失败任务 TTL 清理 |
| 结果文件保留 | 7-30 天，可配置 |

当前 M1 Server 没有其他正在运行的项目，因此可作为该 SaaS 的专用主机。

## 3. 非目标范围

第一版明确不做：

- 本地文件上传
- 完整视频压制 / 字幕烧录
- 在线播放器
- 多语言泛化翻译平台
- 高并发公开视频服务
- GPU 本地模型推理
- 商业计费闭环

这些功能可作为后续 Phase 2/3。

## 4. 部署端口与服务形态

建议端口：

```text
8600: subtitle-saas API/Web
```

现有 Homeserver `:8500` 保持不动，不与该项目混用。

推荐进程：

```text
M1 Air
├─ Web/API service :8600
├─ Worker process
├─ SQLite job database
├─ local job storage
└─ Cloudflare Tunnel（可选，用于外网访问）
```

第一版可使用 SQLite，不强制引入 Redis/PostgreSQL。原因是并发任务为 1，SQLite 作为任务队列和状态存储足够。

SQLite 必须开启 WAL：

```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
PRAGMA foreign_keys=ON;
```

原因：

- API 进程会频繁读 job 状态。
- Worker 进程会持续写 stage / heartbeat / logs。
- 即使全局只有 1 个 running job，API 和 Worker 仍是两个进程并发访问 SQLite。
- 不开启 WAL 容易出现 `database is locked`。

Cloudflare Tunnel 说明：

- Phase 1 只支持 URL 输入，不上传视频文件。
- 因此天然规避 Cloudflare 免费版请求体大小限制。
- 后续如果做文件上传，应走 R2/S3 presigned upload，不应把大文件 POST 到 M1 Air API。

### 4.1 API 与 Worker 进程边界

Phase 1 明确采用两个进程：

```text
API/Web process
  - 接收登录、提交任务、查询状态、下载结果
  - 写入 SQLite jobs 表
  - 不直接执行长任务

Worker process
  - SQLite polling 获取 queued job
  - 独占执行一个 running job
  - 每完成一个 stage 就更新 jobs.stage / jobs.status
  - 任务成功后触发 cleanup
```

通信方式：

```text
API → SQLite jobs table → Worker polling
```

Phase 1 不引入 Redis。Worker 每 3-5 秒轮询一次 `queued` job，并使用事务把 job 从 `queued` 原子更新为 `running`，避免重复执行。

Worker 崩溃处理：

- `running` job 记录 `worker_id`、`heartbeat_at`。
- Worker 每 10-30 秒更新 heartbeat。
- API 不直接判断崩溃，只展示 `running` + 最后心跳时间。
- 启动时 Worker 扫描超时 `running` job，标记为 `failed` 或 `queued`，具体取决于 stage 是否可安全恢复。

Phase 1 恢复粒度：

| stage | 恢复策略 |
|---|---|
| `created` / `metadata_fetched` | 可重新执行 |
| `video_downloaded` | 如果 video 文件存在可复用，否则重新下载 |
| `audio_extracted` | 如果 audio 文件存在可复用，否则重提取 |
| `asr_completed` | 如果 source.srt 存在可复用，否则重跑 ASR |
| `prepass_completed` | 如果 pre_pass manifest 匹配可复用，否则重跑 |
| `translated` | 如果 translated.srt 存在可复用，否则重跑翻译 |
| `finalized` | 如果 finalized.srt 存在可直接进入 cleanup |
| `cleanup_completed` | 终态，不再执行 |

Worker 形态：

- Phase 1：单进程、单任务。
- Phase 2：可启动多个 Worker，但必须先引入更严格的 job locking。
- 单个 Worker 内部可以让 Gemini chunk 并发，但不能同时处理多个视频任务。

## 5. 存储目录规划

不要把任务产物堆在源码目录里。建议：

```text
~/services/bangumi-grillmaster/          # 代码部署目录
~/data/bangumi-grillmaster/jobs/         # 每个任务的工作目录
~/data/bangumi-grillmaster/results/      # 对外下载结果
~/logs/bangumi-grillmaster/              # 服务日志
```

单任务目录：

```text
jobs/{job_id}/
├─ input/
│  └─ video.mp4              # 临时，任务完成后删除
├─ media/
│  ├─ audio.m4a              # 临时，任务完成后删除
│  ├─ frames/                # 临时，任务完成后删除
│  └─ chunks/                # 临时，任务完成后删除
├─ cache/
│  ├─ pre_pass.json          # 可保留
│  └─ chunk_responses/       # 可选保留，默认短 TTL
├─ output/
│  ├─ source.srt             # 可下载/调试
│  ├─ translated.srt         # 可下载/调试
│  └─ finalized.srt          # 主输出
└─ job.log
```

任务成功后默认删除：

- 原视频
- 提取音频
- chunk 音频
- 抽帧图片
- 临时媒体切片

默认保留：

- `finalized.srt`
- `source.srt`
- `translated.srt`
- `pre_pass.json`
- `job.log`

保留 TTL：

| 文件 | 默认 TTL | 说明 |
|---|---:|---|
| `finalized.srt` | 7-30 天 | 用户主下载结果 |
| `source.srt` | 7-30 天 | 调试/对照用，可在隐私模式关闭 |
| `translated.srt` | 7-30 天 | 调试/对照用，可在隐私模式关闭 |
| `pre_pass.json` | 7 天 | 术语/人物/上下文调试用 |
| `chunk_responses/` | 24 小时 | 默认短保留，避免泄露和占盘 |
| `job.log` | 30 天 | 脱敏后保留，用于排障 |

## 6. Gemini / DeepSeek / Agent Platform 接入判断

当前 `bangumi-grillmaster` 使用：

```python
from google import genai
client = genai.Client(api_key=settings.gemini_api_key)
```

当前项目未提供 Gemini base URL / proxy URL 配置。SaaS 版的核心要求不是必须走现有 `gemini-proxy`，而是 Gemini 翻译请求应优先走 Agent Platform 额度 / endpoint，避免继续依赖普通 AI Studio 直连路径。

现有 `gemini-proxy` 信息：

```text
URL: https://gemini-proxy.srzwyuu.workers.dev
Backend: Agent Platform by default
Secret: AGENT_PLATFORM_API_KEY / GEMINI_API_KEY
Request shape: Gemini generateContent REST shape
```

该 proxy 支持：

```text
POST https://gemini-proxy.srzwyuu.workers.dev?model={model}
Body: { contents, generationConfig, ... }
```

因此第一版 SaaS 应新增 Gemini 调用适配层：

```text
GeminiBackend
├─ google_genai_sdk         # 现有直连方式，仅作为 fallback / 本地调试
├─ agent_platform_rest      # 推荐，直接请求 Agent Platform REST endpoint
└─ gemini_proxy_rest        # 可选，通过现有 gemini-proxy 间接走 Agent Platform
```

配置项建议：

```text
GEMINI_BACKEND=agent_platform | proxy | sdk
GEMINI_AGENT_PLATFORM_BASE_URL=https://aiplatform.googleapis.com
GEMINI_AGENT_PLATFORM_LOCATION=us-central1
GEMINI_PROXY_URL=https://gemini-proxy.srzwyuu.workers.dev  # 可选
GEMINI_MODEL=gemini-2.5-pro 或 gemini-3-flash-preview
```

注意事项：

- 不能只把 API key 换成 proxy 地址，因为 Google GenAI SDK 默认直连 Google endpoint。
- 如果直接走 Agent Platform endpoint，需要封装一个兼容当前 `generate_content` 返回结构的 adapter。
- 如果通过 `gemini-proxy` 间接走 Agent Platform，需要确认 proxy 是否完整透传多模态 parts、response schema、thinking config。
- 若 proxy 无法兼容 `response_json_schema` 或 SDK 类型对象，需要在 adapter 中转换成 REST JSON。
- Agent Platform endpoint 可能存在全局 endpoint / 区域 endpoint / API version 差异，必须保留 fallback 策略。
- 成本统计依赖 `usageMetadata`，adapter 必须把返回字段规范化到现有 `calculate_cost()` 可消费的结构。
- Agent Platform REST 支持多模态和 schema，但 JSON 层级与 SDK 对象不同，adapter 必须完整转换入参与出参。

Agent Platform adapter 必须负责：

- 将现有 SDK-style `contents=[parts...]` 转成 REST `contents[].parts[]`。
- 将本地音频/图片转成可接受的 inline base64 或上传后引用 URI。
- 将 `response_json_schema` / thinking config 转成 Agent Platform REST 可接受字段。
- 将 REST response 规范化成现有代码期望的字段：
  - `text`
  - `candidates`
  - `usage_metadata` / `usageMetadata`
  - `finish_reason`
- 将错误响应规范化为可重试 / 不可重试错误。

### 6.0.1 DeepSeek 也优先评估走 Agent Platform / MaaS

补充要求：DeepSeek 结构修复不要默认继续直连 DeepSeek/OpenAI-compatible endpoint。需要评估是否也能通过 Gemini Enterprise Agent Platform 的 open models / MaaS API 调用。

参考文档：

```text
https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/open-models/use-maas
```

Phase 1 设计上应把“Gemini 翻译”和“DeepSeek 结构修复”都抽象成同一类模型后端，而不是写死两个完全不同的调用路径：

```text
ModelBackend
├─ agent_platform_gemini       # Gemini models on Agent Platform
├─ agent_platform_maas_open    # DeepSeek / open models via MaaS, pending verification
├─ gemini_proxy_rest           # optional fallback for Gemini only
├─ google_genai_sdk            # local debug fallback for Gemini
└─ deepseek_openai_compatible  # emergency fallback for DeepSeek
```

关键点：

- 不能假设 DeepSeek 可以“走 Gemini API”。更准确的判断是：DeepSeek 是否能作为 open model 通过 Agent Platform / MaaS endpoint 调用。
- Gemini 和 DeepSeek 可以共享认证、quota、日志、usage/cost 统计框架，但 request/response shape 可能不同。
- DeepSeek 结构修复需要保留 JSON/结构化输出能力；若 MaaS 不支持当前 response schema，需要在 adapter 层做解析和校验。
- 如果 Agent Platform / MaaS 不支持目标 DeepSeek 模型或目标区域不可用，才 fallback 到 `deepseek_openai_compatible`。
- 不允许自动从 Agent Platform fallback 到直连 DeepSeek，除非配置显式开启，避免成本和额度不可追踪。
- 所有凭据只能放服务端环境变量或 secret store，不得写入需求文档、`.env` 示例值、日志、前端或 job event。

待验证问题：

| 项目 | 需要确认 |
|---|---|
| DeepSeek 模型是否在 Agent Platform / MaaS 可用 | model id、region、版本 |
| MaaS endpoint 形态 | REST 原生、OpenAI-compatible、还是 Agent Platform 专用 shape |
| 结构化输出 | 是否支持 JSON schema / response format |
| usageMetadata | 是否返回 token usage，可否复用现有 cost 统计 |
| 错误码 | 429/5xx/配额不足如何区分可重试与不可重试 |
| 认证 | API key、OAuth、service account 或 Agent Platform key |

### 6.1 Gemini backend 决策树

默认策略：

```text
GEMINI_BACKEND=agent_platform
```

决策顺序：

1. 如果 `GEMINI_BACKEND=agent_platform`：直接请求 Agent Platform REST endpoint。
2. 如果 Agent Platform 返回明确的 endpoint/version/region 不可用错误，可在同 backend 内自动尝试 regional endpoint / fallback API version。
3. 不跨 backend 自动重试到 `proxy` 或 `sdk`，除非配置 `GEMINI_ALLOW_CROSS_BACKEND_FALLBACK=true`。
4. 如果 `GEMINI_BACKEND=proxy`：只请求 `GEMINI_PROXY_URL`，由 proxy 自己处理 Agent Platform / AI Studio 后端。
5. 如果 `GEMINI_BACKEND=sdk`：使用现有 Google GenAI SDK 直连，仅用于本地调试或应急。

跨 backend fallback 默认关闭，原因：

- 避免同一 chunk 在多个计费后端重复扣费。
- 避免 Agent Platform 失败后悄悄走 AI Studio，导致成本和 quota 不可控。
- 避免 response shape 差异导致结构修复逻辑难以追踪。

允许自动 fallback 的范围：

```text
agent_platform global endpoint
  → agent_platform regional endpoint
  → agent_platform fallback api version
```

不默认自动 fallback 的范围：

```text
agent_platform → gemini_proxy
agent_platform → google_genai_sdk
gemini_proxy → google_genai_sdk
```

每次 Gemini 请求必须记录：

- backend
- endpoint family
- model
- API version
- retry count
- usageMetadata
- estimated cost
- fallback path

### 6.2 抽帧策略补充：固定间隔 + scene detection

日语综艺 / 偶像节目常包含大量花字（Telop）、姓名牌、角标、企划说明。仅按固定时间间隔抽帧可能漏掉关键信息。

Phase 1 仍以固定间隔为主：

```text
pre-pass: 每 120 秒抽帧
chunk: 每 30 秒抽帧
```

Phase 2 可加入轻量 scene detection：

- 检测画面变化率，额外抽取变化明显的帧。
- 对开场成员介绍、企划标题、字幕花字密集区域提高抽帧密度。
- 控制总帧数上限，避免 Gemini 成本失控。

建议策略：

```text
frames = fixed_interval_frames + scene_change_frames
max_frames_per_job = 可配置
max_frames_per_chunk = 可配置
```

scene detection 只作为召回增强，不应替代固定间隔抽帧。

## 7. Auth 设计参考

Auth 可参考 `sakamichi-platform` 既有系统，但第一版应简化。

参考能力：

- 邮箱注册 / 登录
- OAuth 登录（Google / Discord 可选）
- JWT / HttpOnly cookie
- `/api/auth/me`
- 用户角色
- 管理员能力

第一版建议：

```text
guest: 不允许提交任务，只能看介绍页
member: 可提交任务，有额度限制
admin: 可查看全部任务、重试、删除、调整状态
```

最小 API：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 当前用户 |
| POST | `/api/jobs` | 提交 URL 任务 |
| GET | `/api/jobs` | 我的任务列表 |
| GET | `/api/jobs/{id}` | 任务详情/进度 |
| GET | `/api/jobs/{id}/download/source.srt` | 下载日语 ASR 字幕 |
| GET | `/api/jobs/{id}/download/translated.srt` | 下载翻译后字幕 |
| GET | `/api/jobs/{id}/download/finalized.srt` | 下载最终闪轴修复字幕 |
| POST | `/api/admin/jobs/{id}/retry` | 管理员重试 |
| DELETE | `/api/admin/jobs/{id}` | 管理员删除任务 |

如果第一版只给自己和朋友使用，可以先采用 invite code / allowlist，避免开放注册带来的滥用风险。

## 8. 付费与额度设计

第一版不建议一开始做完整商业计费闭环，但需要提前把数据库和业务模型按“可计费”设计，否则后续很难补。

### 8.1 可参考的既有实现

`sakamichi-platform` 中已有可参考部分：

```text
workers/auth/src/routes/payment-links.ts
workers/auth/src/routes/webhook-kofi.ts
workers/auth/src/db/schema.sql
src/components/user/UserDashboard.tsx
```

现有能力：

- `user_subscriptions` 表：记录用户订阅 / plan / status / payment_ref / expires_at。
- `user_payment_links` 表：允许用户关联 `afdian` / `kofi` / `stripe` 付款账号。
- `unmatched_payments` 表：无法自动匹配用户的付款先落库，管理员后续处理。
- Ko-fi webhook：校验 token、幂等检查、按邮箱/payment link 匹配用户、创建订阅、升级用户权限。
- 前端 Dashboard：已有付款账号关联 UI，可复用交互思路。

注意：目前看到的 `sakamichi-platform` 更偏 Ko-fi webhook 和付款账号关联；`stripe` 在 payment link 平台枚举中预留，但未看到完整 Stripe Checkout Session / Stripe webhook 闭环。因此 Stripe 不能直接“照搬完成品”，但可以参考用户表、订阅表、付款账号关联和权限升级模式。

### 8.2 SaaS 第一版建议

第一版建议采用“额度制”，比纯订阅更适合字幕任务：

```text
free / trial:
  每月少量分钟数或 invite-only

paid:
  购买字幕分钟数 / credits

admin:
  手动加额度、重试任务、豁免限制
```

推荐计量单位：

```text
credit = subtitle minute
```

消耗规则：

- 提交任务后先获取 metadata，拿到视频时长后再预留额度。
- 任务失败且非用户原因时退回额度。
- 任务成功后按实际视频时长确认扣费。
- 管理员重试不重复扣费，除非手动指定。

额度检查与 reserve 时机：

```text
POST /api/jobs
  → 检查是否有最低可用额度
  → 创建 job(status=queued, stage=created)
  → Worker 获取 metadata
  → 得到 duration
  → 按真实时长 reserve minutes
    → 余额足够: 修正预留额度，继续下载/处理
    → 余额不足: status=failed, error_code=INSUFFICIENT_CREDITS，不下载视频，不调用 ASR/Gemini
```

提交阶段防呆：

- Phase 1 不按最大时长冻结完整 60 分钟，避免体验过差。
- 但提交时必须要求用户至少有最低可用额度，例如 `MIN_SUBMIT_CREDIT_MINUTES=10`。
- metadata 获取真实时长后再执行正式 reserve。
- 如果用户只剩 5 分钟，不能提交任务，避免低余额用户大量占用队列做 metadata probing。

并发竞态处理：

- `reserve` 必须在数据库事务中执行。
- 同一用户同时提交多个任务时，按 job 获取 metadata 后的事务顺序抢占余额。
- Phase 1 全局单 worker，竞态风险较低；Phase 2 多 worker 时必须依赖 ledger + balance row lock。

建议新增表：

```text
user_credits
  user_id
  balance_minutes
  updated_at

credit_ledger
  id
  user_id
  job_id
  type: grant | reserve | consume | refund | adjustment
  minutes
  reason
  created_at

checkout_orders
  id
  user_id
  provider: stripe | kofi | manual
  provider_session_id
  provider_payment_id
  status
  amount_cents
  currency
  purchased_minutes
  raw_payload
  created_at
  updated_at
```

### 8.3 Stripe 方案

如果做 Stripe，建议使用 Stripe Checkout，而不是自己处理卡信息：

```text
用户选择套餐
  → POST /api/billing/checkout
  → 后端创建 Stripe Checkout Session
  → 前端跳转 Stripe 托管付款页
  → Stripe webhook: checkout.session.completed
  → 写 checkout_orders
  → 写 credit_ledger grant
  → 增加 user_credits.balance_minutes
```

必须实现：

- Webhook 签名校验。
- `event.id` / `checkout.session.id` 幂等。
- 付款成功后再加额度。
- 未匹配订单落入 `unmatched_payments` 或 `checkout_orders(status='unmatched')`。
- Stripe secret key 只放服务端环境变量，不进入前端。

本地 / Tunnel 调试：

- 本地开发优先用 Stripe CLI 转发 webhook。
- M1 Air 通过 Cloudflare Tunnel 暴露后，Stripe 可直接回调公网 tunnel 域名。
- webhook handler 必须支持重复事件，不得因 Stripe 重试造成重复加额度。
- webhook 原始 body 需要用于签名校验，不应在校验前被 JSON parser 改写。

可参考 `sakamichi-platform`：

- Auth cookie / `getAuthUser()` 模式
- `user_subscriptions` 表的状态字段
- `user_payment_links` 的平台关联模型
- `webhook-kofi.ts` 的 token 校验、幂等、匹配用户、升级权限流程

### 8.4 现成前端项目 / 模板选择

可选路线：

1. 继续沿用 `sakamichi-platform` 的 Astro + React 风格，复用 Auth 与 Dashboard 思路。
2. 使用 Next.js SaaS starter，适合 Stripe Checkout、用户 Dashboard、订阅页，但需要迁移/整合现有 Python worker。
3. 使用 Supabase SaaS starter，适合快速 Auth + billing，但会引入另一套后端依赖。
4. 使用 shadcn/ui dashboard 模板，自建 FastAPI/SQLite/Stripe 后端，控制力最高。

本项目建议：

```text
前端: Astro/React 或 Next.js
后端: FastAPI
Worker: Python
DB: SQLite 起步，后续 PostgreSQL
Billing: Stripe Checkout + webhook
Auth: 参考 sakamichi-platform 的 cookie/JWT/role 模型
```

如果优先速度，第一版可以先不接 Stripe，只做：

```text
invite code
admin adjustment
credit ledger
```

后续再把 Stripe webhook 接到同一套 `credit_ledger`。

### 8.5 参考项目提炼

可参考的开源项目/方向分为三类：

#### A. 通用 SaaS Starter

代表：

```text
nextjs/saas-starter
mickasmt/next-saas-stripe-starter
vercel/nextjs-subscription-payments
KolbySisk/next-supabase-stripe-starter
```

可借鉴：

- 登录态保护页面
- 用户 Dashboard
- Stripe Checkout / Subscription webhook
- Customer portal
- Admin panel / user roles
- Pricing page
- 账号设置页
- 邮件通知

不应照搬：

- Vercel-only 假设
- Prisma/Neon/Supabase 强绑定
- “订阅即授权”的简单模型

原因：本项目核心是 M1 Air 上的 Python 长任务 Worker、文件系统和 FFmpeg，并不是纯 Next.js CRUD SaaS。

#### B. AI SaaS Credits 项目

代表：

```text
adrianhajdin/ai_saas_app
GitHub topic: ai-saas + credits + stripe
```

可借鉴：

- credits purchase UI
- 使用前检查 credits
- Stripe 支付成功后增加 credits
- 每次 AI 操作扣 credits
- 用户可见余额

不应照搬：

- “一次图片生成 = 1 credit” 的简单扣费模型
- MongoDB/Clerk/Cloudinary 等强绑定

字幕 SaaS 的扣费单位更适合按“视频分钟数”，且有长任务失败退款、metadata 后 reserve 和成功确认扣费。

#### C. Usage-based Billing 平台

代表：

```text
getlago/lago
flexprice/flexprice
useautumn/autumn
stripe-samples/subscription-use-cases
```

可借鉴：

- usage metering
- credit grants
- entitlement checks
- invoice / webhook 幂等
- usage event ledger
- 复杂定价规则

第一版不建议引入：

- Lago / Flexprice / Autumn 适合更复杂的 B2B usage-based billing。
- 当前 M1 Air 内测 SaaS 只需要本地 `credit_ledger`。
- 引入完整 billing 平台会增加部署、权限、数据同步和维护成本。

### 8.6 本项目必须实现的 billing 能力清单

从上述项目抽象后，本项目真正需要的是：

```text
PricingPage
  展示充值包 / 包月套餐

Checkout API
  创建 Stripe Checkout Session

Webhook API
  接收 Stripe / Ko-fi 等付款事件
  校验签名 / token
  幂等处理

Credit Ledger
  所有额度变动都写流水

Balance Snapshot
  快速读取用户剩余额度

Entitlement Check
  提交时检查最低额度门槛，metadata 后检查真实时长额度

Reservation
  metadata 后按真实视频时长 reserve 额度

Settlement
  成功后确认扣费，失败后退款

Admin Adjustment
  管理员赠送 / 补偿 / 修正额度

User Billing Dashboard
  显示余额、套餐、消费记录、充值入口

Admin Billing Dashboard
  查看用户余额、订单、异常付款、手动调整
```

其中 `Admin Adjustment` 就是“管理员手动加分钟”的正式定义。它不是主要充值方式，而是：

- 内测赠送
- 故障补偿
- 异常订单处理
- 客服修正
- 测试账号初始化

正式充值必须由 `Checkout API + Webhook API + Credit Ledger` 自动完成。

### 8.7 推荐实现顺序

```text
1. credit_ledger + user_credit_balances
2. admin adjustment
3. job submit 前余额检查
4. job reserve / consume / refund
5. 用户 billing dashboard
6. Stripe Checkout 一次性充值包
7. Stripe webhook 自动加 purchased_minutes
8. 包月 subscription + monthly_minutes
9. Stripe customer portal
10. 更复杂 usage-based billing / 外部 billing 平台
```

## 9. Job 状态机

任务状态：

```text
queued
running
retrying
succeeded
failed
cancelled
expired
```

处理阶段：

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

stage 与核心链路映射：

| stage | 对应链路 | 主要产物 |
|---|---|---|
| `created` | `POST /api/jobs` 创建任务 | job row |
| `metadata_fetched` | `yt-dlp` 获取标题/时长/来源信息 | video_title, video_duration_seconds |
| `video_downloaded` | 下载视频 | input/video.* |
| `audio_extracted` | 提取音频 / 抽帧准备 | media/audio.* |
| `asr_completed` | ElevenLabs Scribe v2 ASR | output/source.srt |
| `prepass_completed` | Gemini 多模态 pre-pass | cache/pre_pass.json |
| `translated` | Gemini chunk 翻译合并 | output/translated.raw.srt |
| `structure_fixed` | DeepSeek / normalization 结构修复确认 | output/translated.srt |
| `finalized` | finalize + snap-gap | output/finalized.srt |
| `cleanup_completed` | 删除视频、音频、抽帧、chunk 媒体 | 保留 SRT/log/pre_pass |

实现时应以本表命名为准，避免 workflow、DB、前端显示各自使用不同 stage 名称。

`retrying` 状态语义：

- 用于 ElevenLabs / Gemini / DeepSeek / 下载层的临时错误重试。
- 典型错误：502、503、504、429、连接中断、可恢复的上游超时。
- Worker 进入 `retrying` 时记录 `retry_after_seconds` 和 `retry_count`。
- 指数退避后回到 `running` 继续同一 stage。
- 超过最大重试次数后进入 `failed`。

chunk 级恢复：

- Gemini chunk 翻译应记录 `current_chunk_index` 和 `total_chunks`。
- 每个 chunk 成功后写入 chunk response cache 和 DB progress。
- Worker 重启后优先复用已完成 chunk，避免重新翻译已完成片段。
- chunk cache 必须带 manifest / prompt digest，避免 prompt 或模型变更后误用旧结果。

Job 表字段建议：

```text
id
user_id
source_url
status
stage
current_chunk_index
total_chunks
progress_message
error_message
error_code
video_title
video_duration_seconds
cost_estimate
reserved_minutes
consumed_minutes
worker_id
heartbeat_at
created_at
started_at
finished_at
expires_at
source_srt_path
translated_srt_path
result_srt_path
log_path
```

## 10. 并发与限流

M1 Air 第一版建议：

```text
GLOBAL_JOB_CONCURRENCY=1
GEMINI_CHUNK_CONCURRENCY=2-3
MAX_VIDEO_DURATION_SECONDS=3600
MIN_SUBMIT_CREDIT_MINUTES=10
SQLITE_JOURNAL_MODE=WAL
SQLITE_BUSY_TIMEOUT_MS=5000
```

原因：

- 本地 CPU 足够，但长时间 FFmpeg/抽帧仍可能发热降频
- Gemini / ElevenLabs API rate limit 比本机算力更容易成为瓶颈
- 任务并发 1 更容易保证稳定性与成本可控

Phase 1 不启用 per-user running limit。因为全局任务并发已经是 1，`PER_USER_RUNNING_JOBS=1` 在此阶段没有实际额外收益。

Phase 2 多用户内测再加入：

```text
PER_USER_RUNNING_JOBS=1
PER_USER_QUEUED_JOBS=3
DAILY_FREE_MINUTES_LIMIT=可选
```

## 11. URL 输入策略

第一版只支持 URL，不支持文件上传。

允许类型：

- `yt-dlp` 支持的视频 URL
- 可直接下载的媒体 URL
- 管理员配置的可信站点

限制：

- 下载前检查视频时长
- 超过最大时长则拒绝
- 不允许内网地址 / localhost / metadata IP，避免 SSRF
- 设置下载超时
- 设置最大文件大小
- 对 301/302/307/308 重定向后的最终 URL 再做一次 SSRF / IP 校验，避免 DNS rebinding 或 redirect-to-internal 攻击

SSRF 防护必须包括：

```text
127.0.0.0/8
10.0.0.0/8
172.16.0.0/12
192.168.0.0/16
169.254.0.0/16
::1
fc00::/7
```

DNS / redirect 防护：

- 解析原始 URL host，拒绝内网 / link-local / localhost。
- 如果下载器跟随重定向，必须校验最终 URL 的 host/IP。
- 对自写下载脚本尤其要谨慎，不能只信任初始 URL。
- 对冷门站点先走 `yt-dlp --dump-json` 获取 metadata，不直接执行不受控下载逻辑。

### 11.1 yt-dlp cookies / 登录态管理

下载层必须预留 cookies 管理，因为 TVer / YouTube / Bilibili 等来源可能要求登录态、年龄验证或地区状态。

Phase 1 做法：

```text
YTDLP_COOKIES_TXT_PATH=/Users/xxx/secrets/bangumi-cookies.txt
```

要求：

- cookies 文件路径只存在服务端环境变量或 admin-only 配置中。
- 不允许普通用户上传 cookies。
- Worker 调用 yt-dlp 时读取该 cookies 文件。
- cookies 文件不得写入 job log。
- cookies 更新先通过管理员 SSH/本地文件替换完成，不做 Web UI。

Phase 2 可选：

- Admin 页面显示 cookies 文件更新时间。
- Admin 页面支持上传/替换 cookies.txt。
- 下载失败如果疑似 cookies 过期，错误码标为 `COOKIES_EXPIRED_OR_REQUIRED`。

cookies 失败处理：

| 情况 | 处理 |
|---|---|
| cookies 文件不存在 | 对公开 URL 继续尝试；需要登录态的站点直接失败 |
| cookies 过期 | job failed，提示管理员更新 cookies |
| 用户 URL 需要个人 cookies | 第一版不支持，提示用户换公开视频/直链 |

## 12. 清理策略

任务成功：

```text
立即删除原视频、音频、抽帧、chunk 媒体
保留 SRT / prepass / log
```

任务失败：

```text
保留中间文件 24 小时用于 debug
超过 TTL 自动清理
```

结果文件：

```text
默认保留 7-30 天
过期后状态变为 expired
```

`expires_at` 语义：

- `expires_at` 指结果文件过期时间，不表示 job record 过期。
- 到达 `expires_at` 后，清理器删除可下载结果文件，job `status` 更新为 `expired`。
- job record 默认继续保留 90 天，用于用户历史和管理员审计。
- `cleanup_completed` 是处理流程 stage，表示中间媒体已清理；`expired` 是结果可下载状态，二者不冲突。

需要定时清理器：

```text
每小时扫描 jobs
删除 expired / failed-old 的临时目录
写入 cleanup log
```

## 13. 前端页面需求

页面：

```text
/
  产品说明 + 登录入口
/jobs/new
  提交 URL
/jobs
  我的任务列表
/jobs/{id}
  任务进度、日志摘要、下载结果
/admin/jobs
  管理员任务看板
/billing
  Phase 1 只展示余额和消费记录；Phase 3 增加套餐 / 充值入口
/account
  账号信息；付款账号关联在接入 Stripe/Ko-fi 后启用
```

任务详情页展示：

- 当前状态
- 当前阶段
- 视频标题
- 预计/实际耗时
- 失败原因
- 下载按钮
- 日志摘要
- 剩余额度 / 本任务预计消耗分钟数

Phase 1 页面范围：

| 页面 | Phase 1 范围 |
|---|---|
| `/jobs/new` | 提交 URL、显示最大时长限制 |
| `/jobs` | 我的任务列表、状态、创建时间、过期时间 |
| `/jobs/{id}` | 阶段进度、错误原因、下载 source/translated/finalized SRT |
| `/billing` | 只读余额、ledger 最近记录，不展示 Stripe 付款入口 |
| `/account` | 当前用户、退出登录、基础信息 |
| `/admin/jobs` | 管理员查看任务、重试、删除、查看脱敏日志 |

## 14. 安全与滥用控制

必须实现：

- 登录后才能提交任务
- 全局队列限制
- URL SSRF 防护
- 最大时长限制
- 最大下载文件大小限制
- API key 不落盘、不进前端
- Gemini 统一走 proxy 时，key 只留在 Cloudflare Worker Secret
- 如果不走 proxy 而直连 Agent Platform，Agent Platform key / service account 凭据只允许存在服务端环境变量或受控 secret 中
- 付款 webhook 必须校验签名或 token
- 额度扣减必须走 ledger，不允许只更新余额而无流水
- 下载接口必须校验 job 归属，普通用户只能下载自己的 job 结果
- 管理员下载他人结果必须记录审计日志

建议实现：

- invite code 注册
- admin adjustment
- Phase 2 增加单用户并发限制
- 每日任务数限制
- 操作审计日志

下载接口权限：

| 接口 | 权限 | 说明 |
|---|---|---|
| `GET /api/jobs/{id}/download/source.srt` | job owner 或 admin | 下载日语 ASR 字幕，必须校验归属 |
| `GET /api/jobs/{id}/download/translated.srt` | job owner 或 admin | 下载翻译后字幕，必须校验归属 |
| `GET /api/jobs/{id}/download/finalized.srt` | job owner 或 admin | 下载最终闪轴修复字幕，必须校验归属 |
| `GET /api/admin/jobs/{id}/download/{name}.srt` | admin | 管理员审计下载，记录 actor / job_id / file / time |
| signed URL | Phase 3 可选 | 接入 R2/S3 后再引入短时效 signed URL |

## 15. 额外注意事项

### 15.1 M1 Air 长期运行

- 关闭自动睡眠。
- 使用 `launchd` / `pm2` / `supervisor` 保活。
- 日志必须按天轮转，避免撑满磁盘。
- Worker 崩溃后不能丢任务，必须依赖 DB 状态恢复。

### 15.2 下载与版权风险

- 产品文案必须要求用户仅处理自己有权处理的内容。
- URL 下载失败要给出可读错误，不要暴露内部命令。
- 对 TVer / YouTube 等站点要预留 cookies / rate limit / 下载失败重试。

### 15.3 成本控制

- 提交任务前估算视频时长和预计成本。
- Gemini chunk 并发不能只看机器性能，还要看 Agent Platform quota。
- ElevenLabs ASR 成本和并发需要单独限流。
- 对失败重试设置最大次数，避免烧 API 额度。

### 15.3.1 ElevenLabs Scribe v2 限制待量化

ASR 是链路中的高成本、高限流风险环节。正式实现前必须补齐：

| 项目 | 当前文档状态 | 需要验证后填写 |
|---|---|---|
| 并发上限 | 未确认 | 同时 ASR job 数 |
| 单分钟音频成本 | 未确认 | 每 1 分钟音频约多少钱 |
| 最大单文件时长 | 未确认 | API 接受的最长音频 |
| 最大单文件大小 | 未确认 | API 接受的最大文件 |
| 失败重试策略 | 未确认 | 哪些错误可重试、最多几次 |
| 速率限制错误码 | 未确认 | 429/配额不足时的处理 |

在上述数据确认前，Phase 1 默认：

```text
ELEVENLABS_ASR_CONCURRENCY=1
MAX_VIDEO_DURATION_SECONDS=3600
ASR_MAX_RETRIES=2
```

### 15.4 可恢复性

- 每个 stage 完成后落库。
- Worker 重启时可从最近 stage 继续或明确失败。
- Gemini pre-pass 和 chunk response 缓存要有 manifest，避免 prompt 改变后误用旧缓存。

### 15.5 隐私与数据保留

- 默认不长期保存原视频。
- 失败任务中间文件仅保留 24 小时。
- 用户可删除任务结果。
- 管理员下载用户字幕应有审计记录。

### 15.6 任务日志结构

每个 job 同时维护两类日志：

```text
job.log
  人类可读文本日志，用于本地排障

job_events
  结构化 JSON lines / DB events，用于前端展示和审计
```

`job_events` 字段建议：

```text
timestamp
level: info | warning | error | success
stage
code
message
metadata_json
```

前端“日志摘要”优先展示 `job_events`，不是直接 tail 原始 `job.log`。`job.log` 仅管理员可见。

脱敏规则：

- 不记录 API key / cookies / Authorization header。
- 用户 URL 如含 query token，前端展示时隐藏 query string。
- yt-dlp / ffmpeg 原始命令需要过滤 cookies 路径和敏感 header。
- Gemini / DeepSeek 原始 prompt 和 response 默认不在前端展示，只保存在短 TTL debug cache。

## 16. Phase 规划

### Phase 1: 本机 MVP

- M1 Air 本地运行 Web/API
- URL 输入
- 登录/allowlist
- SQLite job queue + Worker polling
- 单 worker
- 输出并允许下载 `source.srt`、`translated.srt`、`finalized.srt`
- 任务完成自动清理媒体文件
- credit ledger + admin adjustment
- `/billing` 只读余额页
- Agent Platform backend adapter 初版或明确 fallback 到 SDK 调试模式

### Phase 2: 内测版

- Cloudflare Tunnel 暴露公网
- Auth 完整化
- 用户任务列表
- 管理员重试/删除
- Gemini backend 决策树完善：Agent Platform direct / proxy / sdk
- 基础额度限制
- Phase 2 per-user queue/running limit
- cookies 状态展示 / admin 更新入口
- 用户 job_events 展示

### Phase 3: 产品化

- R2/S3 存结果
- 邮件/通知
- Stripe Checkout + webhook
- 文件上传（presigned upload）
- 多 worker 横向扩展
- ASS 输出 / 视频压制作为高级功能

## 17. 待验证问题

1. Agent Platform 直接 endpoint 是否完整支持当前多模态 parts。
2. Agent Platform 直接 endpoint 是否支持 `response_json_schema` 对应的 REST 字段。
3. Agent Platform 后端是否支持当前使用的 `thinking_config`。
4. Agent Platform 返回的 `usageMetadata` 字段是否足够复用现有成本统计。
5. 如果使用 `gemini-proxy`，proxy 是否完整透传上述字段。
6. M1 Air 长时间跑 FFmpeg 抽帧是否稳定，需要实测 3-5 个连续任务。
7. ElevenLabs ASR 并发和额度限制需要单独确认。
8. Stripe Checkout webhook 在 Cloudflare Tunnel / M1 Air 入口下的公网可达性与签名校验。
9. yt-dlp cookies 对目标站点的有效期、更新方式和失败错误码。
10. SQLite polling + heartbeat 在 M1 Air 长时间运行下的稳定性。

## 18. 当前结论

M1 Air Server 对第一版 SRT-only SaaS 完全够用。

最稳妥的第一版边界是：

```text
URL only
SRT only
single worker
single running job
Gemini chunk concurrency 2-3
任务完成删除原视频与中间媒体
Auth 参考 sakamichi-platform，但采用 invite/allowlist 简化
Gemini 调用优先走 Agent Platform endpoint；可直接 REST 调用，也可通过 gemini-proxy 间接调用
付费系统先做 credit ledger、余额检查、预留/确认扣费/退款、admin adjustment；Stripe Checkout 作为产品化阶段接入
```
