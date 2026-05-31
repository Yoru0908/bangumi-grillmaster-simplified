# Kotoba Forge (SaaS) 运维手册

## 架构

```
用户浏览器 (https://kotoba.sakamichi-tools.cfd or https://kotoba-forge.pages.dev)
       │
       ├─ GET / → CF Pages / M1 serve index.html
       ├─ API (POST /api/*) → CF Tunnel → M1:8600 → Python HTTP server
       └─ R2 上传 (PUT) → cf.r2.cloudflarestorage.com (直传，不经过 M1)
```

## 部署位置

| 组件 | 位置 | 启动方式 |
|------|------|----------|
| API Server | M1 Mac (192.168.3.28:8600) | launchd: `kotoba-forge-api.plist` |
| Worker | M1 Mac | launchd: `kotoba-forge-worker.plist` |
| Frontend | CF Pages (kotoba-forge) | `npx wrangler pages deploy web` |
| R2 Bucket | CF R2 (kotoba-forge-uploads) | 预签名直传 |
| DB | M1: `~/data/bangumi-grillmaster/app.db` | SQLite WAL |

## 常用命令

### 部署前端
```bash
cd /path/to/bangumi-grillmaster
npx wrangler pages deploy web --project-name kotoba-forge --branch main
```

### 同步代码到 M1 并重启 API
```bash
rsync -avz services/saas/ web/ settings.py .env yoru@192.168.3.28:/Users/yoru/Documents/kotoba-forge/
ssh yoru@192.168.3.28 "launchctl stop com.yoru.kotoba-forge-api; sleep 1; launchctl start com.yoru.kotoba-forge-api"
```

### 同步代码到 M1 并重启 Worker
```bash
rsync -avz services/saas/ yoru@192.168.3.28:/Users/yoru/Documents/kotoba-forge/services/saas/
ssh yoru@192.168.3.28 "launchctl stop com.yoru.kotoba-forge-worker; sleep 1; launchctl start com.yoru.kotoba-forge-worker"
```

### 查看任务
```bash
ssh yoru@192.168.3.28 "sqlite3 ~/data/bangumi-grillmaster/app.db 'SELECT id, status, stage, user_id FROM jobs ORDER BY created_at DESC LIMIT 5'"
```

### 重置某个任务
```bash
ssh yoru@192.168.3.28 "sqlite3 ~/data/bangumi-grillmaster/app.db \"UPDATE jobs SET status='queued', stage='created', error_code=NULL, error_message=NULL WHERE id='job_xxx'\""
```

### DB 备份
每小时自动备份到 `~/data/bangumi-grillmaster/backups/`，保留最近 24 份。
手动备份：
```bash
ssh yoru@192.168.3.28 "~/data/bangumi-grillmaster/backup.sh"
```

### 查看日志
```bash
ssh yoru@192.168.3.28 "tail -50 ~/logs/bangumi-grillmaster/api.err.log"
ssh yoru@192.168.3.28 "tail -50 ~/logs/bangumi-grillmaster/worker.out.log"
```

### 健康检查
```bash
curl https://kotoba.sakamichi-tools.cfd/healthz
```

## 账号

| 邮箱 | 密码 | 角色 |
|------|------|------|
| srzwyuu@gmail.com | xjj20000908 | admin (无限额度) |
| member@example.com | test123456 | member |
| admin-test@example.com | test123456 | admin |

## 注意

- **禁止 rsync app.db** — DB 只在 M1 上操作
- 代码同步后清除 pycache：`find ~/Documents/kotoba-forge -name __pycache__ -exec rm -rf {} +`
- Worker 单任务串行 (GLOBAL_JOB_CONCURRENCY=1)
- R2 上传链路：presign → 直传 R2 → /api/jobs/r2 → 下载到 M1 → pipeline
- Stripe webhook: `whimsical-euphoria-snapshot` → `https://kotoba.sakamichi-tools.cfd/api/billing/webhook`
