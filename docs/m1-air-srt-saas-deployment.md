# M1 Air SRT SaaS Phase 1 Deployment Runbook

本文只覆盖 Phase 1 内测部署：本机 SQLite、stdlib HTTP API、单 worker、单 cleanup daemon。不要把 Stripe、多 worker、文件上传或 R2/S3 塞进这份 runbook。

## 1. 目录

```text
repo:    /Users/yoru/Documents/SA/项目/ElevenLabs Scribe v2/bangumi-grillmaster
data:    /Users/yoru/data/bangumi-grillmaster
jobs:    /Users/yoru/data/bangumi-grillmaster/jobs
results: /Users/yoru/data/bangumi-grillmaster/results
logs:    /Users/yoru/logs/bangumi-grillmaster
db:      /Users/yoru/data/bangumi-grillmaster/app.db
```

## 2. 环境变量

最小内测配置：

```bash
export PYTHONPATH="/Users/yoru/Documents/SA/项目/ElevenLabs Scribe v2/bangumi-grillmaster"
export SAAS_DATABASE_PATH="/Users/yoru/data/bangumi-grillmaster/app.db"
export SAAS_JOB_DATA_DIR="/Users/yoru/data/bangumi-grillmaster/jobs"
export SAAS_JOB_RESULT_DIR="/Users/yoru/data/bangumi-grillmaster/results"
export SAAS_LOG_DIR="/Users/yoru/logs/bangumi-grillmaster"
export SAAS_API_HOST="0.0.0.0"
export SAAS_API_PORT="8600"
export SAAS_MIN_SUBMIT_CREDIT_MINUTES="10"
export SAAS_MAX_VIDEO_DURATION_SECONDS="3600"
export SAAS_RUNNING_JOB_HEARTBEAT_TIMEOUT_SECONDS="120"
export SAAS_RESULT_TTL_DAYS="14"
export SAAS_FAILED_JOB_TMP_TTL_HOURS="24"
export SAAS_WORKER_POLL_INTERVAL_SECONDS="5"
export PATH="/opt/homebrew/bin:/Library/Frameworks/Python.framework/Versions/3.12/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
```

真实 pipeline 还需要现有项目本来要求的服务端 secret，例如 ElevenLabs、Gemini Agent Platform、DeepSeek MaaS 或显式 fallback 凭据。凭据只能放环境变量或 secret store，不写进 repo、job log、`job_events` 或前端。

`PATH` 对 launchd 很关键：worker 会通过 `ffmpeg-python`/subprocess 调用 `ffmpeg`、`ffprobe`，默认 launchd PATH 只有 `/usr/bin:/bin:/usr/sbin:/sbin`，找不到 Homebrew 安装的媒体工具。

DeepSeek 结构修复的当前生产决策：继续走 DeepSeek 官方 OpenAI-compatible endpoint 的 v4 系列。Agent Platform / MaaS 当前没有暴露 DeepSeek v4 MaaS；不要为了“统一后端”降级到 v3.x MaaS。

```bash
export DEEPSEEK_BACKEND="deepseek_openai_compatible"
```

只有在后续确认 MaaS 已提供 DeepSeek v4，或明确接受 v3.x MaaS 降级时，才改走 Agent Platform / MaaS。改走 MaaS 前需要先确认 Google Cloud project 已启用 Service Usage API 与 `aiplatform.googleapis.com`，再配置：

```bash
export DEEPSEEK_BACKEND="agent_platform_maas"
export DEEPSEEK_MAAS_API_KEY="..."
export DEEPSEEK_MAAS_BASE_URL="https://REGION-aiplatform.googleapis.com/..."
export DEEPSEEK_MAAS_MODEL="publishers/.../models/..."
```

当前实测阻断：`gen-lang-client-0829034359` 的 `serviceusage.googleapis.com` / `aiplatform.googleapis.com` 未启用，gcloud probe 返回 `SERVICE_DISABLED`，所以 MaaS 真实调用还不能完成；direct DeepSeek smoke 已验证。

## 3. 初始化

```bash
python -m services.saas.bootstrap_cli \
  --invite-code "change-me-member-code" \
  --invite-email "member@example.com" \
  --invite-role member \
  --initial-credit-minutes 30 \
  --now "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
```

这一步会创建 data/log 目录、初始化 SQLite/WAL、写 invite，并给目标邮箱做一次幂等 initial grant。

## 4. 前台启动

开发或手动 smoke test 用三个终端：

```bash
python -m services.saas.server_main
python -m services.saas.worker_main --worker-id worker-1
python -m services.saas.cleanup_daemon
```

API 默认监听 `:8600`。Phase 1 API 是 stdlib HTTP adapter，不依赖 FastAPI/Uvicorn；后续如果换框架，必须保持 `SaasApiService` 业务层契约不变。

## 5. launchd 草案

把下面三个 plist 保存到 `~/Library/LaunchAgents/` 后，用 `launchctl bootstrap gui/$(id -u) <plist>` 启动。示例里只放非敏感配置，真实 secret 不要写进可提交文件。

`com.yoru.bangumi-grillmaster-saas-api.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.yoru.bangumi-grillmaster-saas-api</string>
  <key>WorkingDirectory</key><string>/Users/yoru/Documents/SA/项目/ElevenLabs Scribe v2/bangumi-grillmaster</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>-m</string>
    <string>services.saas.server_main</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key><string>/Users/yoru/Documents/SA/项目/ElevenLabs Scribe v2/bangumi-grillmaster</string>
    <key>SAAS_DATABASE_PATH</key><string>/Users/yoru/data/bangumi-grillmaster/app.db</string>
    <key>SAAS_JOB_DATA_DIR</key><string>/Users/yoru/data/bangumi-grillmaster/jobs</string>
    <key>SAAS_JOB_RESULT_DIR</key><string>/Users/yoru/data/bangumi-grillmaster/results</string>
    <key>SAAS_LOG_DIR</key><string>/Users/yoru/logs/bangumi-grillmaster</string>
    <key>SAAS_API_HOST</key><string>0.0.0.0</string>
    <key>SAAS_API_PORT</key><string>8600</string>
    <key>PATH</key><string>/opt/homebrew/bin:/Library/Frameworks/Python.framework/Versions/3.12/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/Users/yoru/logs/bangumi-grillmaster/api.out.log</string>
  <key>StandardErrorPath</key><string>/Users/yoru/logs/bangumi-grillmaster/api.err.log</string>
</dict>
</plist>
```

Worker 和 cleanup 只需要替换 `Label`、`ProgramArguments`、日志文件：

```text
worker:  /usr/bin/python3 -m services.saas.worker_main --worker-id worker-1
cleanup: /usr/bin/python3 -m services.saas.cleanup_daemon
```

## 6. Smoke Test

1. 初始化 invite 和 credit。
2. 启动 API、worker、cleanup。
3. 检查 API 和 SQLite：

```bash
curl -s http://127.0.0.1:8600/healthz
```

预期：

```json
{"ok": true, "database": "ok"}
```

4. 登录并保存 cookie：

```bash
curl -i -c /tmp/bgm-saas.cookie \
  -H 'Content-Type: application/json' \
  -d '{"email":"member@example.com","invite_code":"change-me-member-code"}' \
  http://127.0.0.1:8600/api/auth/login
```

5. 提交 playground 短视频 URL。真实 pipeline smoke 已用 YouTube 短视频 `Me at the zoo` 验证过下载、ElevenLabs ASR、Gemini 翻译、finalize 和 artifact 下载：

```bash
curl -s -b /tmp/bgm-saas.cookie \
  -H 'Content-Type: application/json' \
  -d '{"source_url":"https://www.youtube.com/watch?v=jNQXAC9IVRw"}' \
  http://127.0.0.1:8600/api/playground/jobs
```

6. 提交正式 job：

```bash
curl -s -b /tmp/bgm-saas.cookie \
  -H 'Content-Type: application/json' \
  -d '{"source_url":"https://example.com/video"}' \
  http://127.0.0.1:8600/api/jobs
```

7. 轮询 job：

```bash
curl -s -b /tmp/bgm-saas.cookie http://127.0.0.1:8600/api/jobs
```

8. 成功后下载：

```bash
curl -L -b /tmp/bgm-saas.cookie \
  -o finalized.srt \
  http://127.0.0.1:8600/api/jobs/JOB_ID/download/finalized.srt
```

9. 检查 DB：

```bash
sqlite3 /Users/yoru/data/bangumi-grillmaster/app.db \
  "select status, stage, job_type, reserved_minutes, consumed_minutes from jobs order by created_at desc limit 5;"
```

## 7. 回滚与清理

停止 launchd：

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.yoru.bangumi-grillmaster-saas-api.plist
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.yoru.bangumi-grillmaster-saas-worker.plist
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.yoru.bangumi-grillmaster-saas-cleanup.plist
```

不要直接删除 SQLite 或 job 目录来“回滚”。如果要清空内测数据，先备份 `app.db`、`jobs/`、`results/`，再人工确认删除范围。
