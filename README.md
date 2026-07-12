# Bangumi GrillMaster (Simplified)

> Fork 說明：本 fork 將字幕翻譯輸出與格式清理調整為**簡體中文**風格（大陸簡體字幕慣例），核心程式、流程設計與專案所有權皆歸原作者所有。請優先參考原專案與原作者說明。

下载日本综艺节目，自动生成**简体中文** SRT / ASS 字幕，方便个人使用识读。

![](/doc/image2.jpg)
![](/doc/image3.png)
![](/doc/image1.png)

## 说明

- 目标是 one shot 即可直接观看，不想校准 (避免被暴雷)
- 1 小时左右的影片成本大概 $20 台币 (ASR $6 + 翻译 $14)，处理时间约 15 分钟
- 设定偏好都是个人主观，如需修改请自行 fork
- 更详细请[查看心得](/article.md)

## 技术栈

- **语言**：Python 3.13+
- **包管理**：[uv](https://github.com/astral-sh/uv)（推荐）或 pip
- **媒体处理**：FFmpeg、[yt-dlp](https://github.com/yt-dlp/yt-dlp)
- **ASR**：[ElevenLabs Scribe v2](https://elevenlabs.io/)（日文语音识别）
- **翻译**：[Google Gemini](https://ai.google.dev/)（`gemini-3-flash-preview`）
- **结构修正**：[DeepSeek](https://www.deepseek.com/)（`deepseek-v4-flash`，修正 chunk 输出的 index / timecode 结构错误）
- **可选后处理**：[Codex CLI](https://github.com/openai/codex)（字幕润色、风格化封面）
- **核心依赖**：`pydantic` / `pydantic-settings`（配置与项目模型）、`typer`（CLI）、`loguru`（日志）、`google-genai`、`openai`、`elevenlabs`、`ffmpeg-python`、`pycryptodomex`

## 工具

经过各种尝试，API、自架等组合后，觉得以下方式最合适

### ASR

`ElevenLabs Scribe v2` 日文辨识效果稳定，尤其在一堆人大声喧哗，或者装傻吐槽之间无间隔状况都能分析出来。

### 翻译

测试多种模型还是 `Gemini 3 Flash` 的润饰最能抓住日本综艺的韵味 (Pro 更好，但成本...)，加上图片音档的理解真的很好，但 `Gemini 3 Flash` 的输出常常会漏 Index 或弄错时间轴，所以如果验证错误，会透过 `DeepSeek V4 Flash` 做修正

翻译目标为**简体中文**（大陆简体字幕风格，使用 `酱 / 你 / 广播 / 听众` 等形式，而非 `醬 / 妳 / 廣播 / 聽眾`）。

进行**两阶段翻译**：

1. **Pre-pass**：完整 SRT + 节目信息 + 完整音档 + 少量全片代表图片，输出：人物对照、专有名词/ASR 修正 dict、梗的固定译法、整体语气、每段局部摘要
2. **并发翻译**：SRT 按字元数平均切块，每块配上 pre-pass 简报 + 局部摘要 + 该段音档切片 + 该段的代表图片，平行送出翻译
3. **组装**：每块输出验证 index/timecode 连续性，使用额外 code 专长便宜模型修正，再拼接写档

不只听音讯，也会参考影片抽出的图片，帮助辨识人物、场景、道具与画面上的提示文字
![](doc/image4.jpg)

另外，翻译过程的 chunk / pre-pass 资源与回应会保留在专案资料夹中，方便失败后直接 resume，不用每次都重切音讯、重抽图、重跑整个翻译

## 流程

```
Video ID
    ↓
下载影片 (yt-dlp)
    ↓
合并影片 (FFmpeg)
    ↓
提取音档 (FFmpeg, mono 16kHz opus)
    ↓
语音辨识 (ElevenLabs Scribe v2)
    ↓
产生 SRT 字幕
    ↓
翻译字幕 (Gemini: pre-pass → 并发 chunk 翻译 → 组装验证)
    ↓
润饰字幕 (Codex, 可选)
    ↓
Finalize：格式清理（简体标点、繁→简用字转换），输出 ASS (套样式) + SRT
    ↓
归档 (可选)
    ↓
封装交付 (可选：字幕烧录进影片)
```

每个阶段都是幂等的：已完成阶段会被跳过，进度自动保存到 `project.json`，失败后可直接重跑 resume。

## 支持来源

通过 yt-dlp 支持以下平台（传入视频 ID 或完整 URL 均可）：

| 平台 | 示例 |
| --- | --- |
| Bilibili | `BV1ZArvBaEqL` / `https://www.bilibili.com/video/BV1ZArvBaEqL` |
| TVer | `ep12345` / `https://tver.jp/episodes/ep12345` |
| Abema | `90-979_s1_p123` / `https://abema.tv/video/episode/90-979_s1_p123` |
| YouTube | `v=dQw4w9WgXcQ` / `https://youtu.be/dQw4w9WgXcQ` |

TVer 与 Abema 来源还会额外抓取出演者 (talents) 元数据，作为翻译 pre-pass 的人物锚点。

## 安装

### 前置需求

- Python 3.13+
- FFmpeg (自行安装并加入 PATH)
- uv (推荐) 或 pip
- (可选) Codex CLI — 启用字幕润色 / 封面生成时需要

### 安装步骤

```bash
# 使用 uv
uv sync

# 或使用 pip
pip install -e .
```

## 使用方式

### 方式一：直接执行（跨平台）

```bash
python main.py <SOURCE> [TRANSLATION_HINT] [OPTIONS]
```

### 方式二：加入 PATH（Windows）

`scripts/` 下提供 `grill.bat`（Windows 批处理，调用 `.venv` 里的 Python）。将 `scripts/` 加到系统 PATH 后执行：

```bash
grill <SOURCE> [TRANSLATION_HINT] [OPTIONS]
```

> 注意：目前仅提供 Windows 启动脚本，macOS / Linux 请使用 `python main.py`。

### 参数

| 参数 | 说明 |
| --- | --- |
| `SOURCE` | 影片 ID 或完整 URL |
| `TRANSLATION_HINT` | 可选，翻译提示。未提供时使用影片标题（bilibili 只有隐晦标题时常用） |
| `--break-after <STAGE>` | 到达指定阶段后停止，便于调试 / 分段执行。阶段值如 `is_asr_completed`、`is_translated`、`is_finalized` 等 |
| `--parent-project <PATH>` | 复用某个父专案目录的 `pre_pass.json` 作为本集 pre-pass 种子，实现跨集一致性（接受目录路径，因父专案可能已归档） |
| `--refine` | 本次运行强制启用 Codex 字幕润色（覆盖 `ENABLE_SRT_REFINE`，默认关闭） |
| `--cover` | 本次运行强制启用 Codex 风格化封面生成（覆盖 `ENABLE_COVER_GENERATION`，默认关闭；设置 `--break-after` 时整体跳过） |

### 范例

```bash
# 使用影片标题作为翻译提示
python main.py BV18KBJBeEmV

# 自订翻译提示
python main.py BV1CakEBaEJp "华大千鸟 - 全力100万 - 间谍 1/7"

# 使用完整 URL
python main.py "https://www.bilibili.com/video/BV18KBJBeEmV"

# 只跑到 ASR 完成就停
python main.py BV18KBJBeEmV --break-after is_asr_completed

# 复用上一集的 pre-pass，并强制启用润色与封面
python main.py BV1CakEBaEJp --parent-project projects/BV18KBJBeEmV --refine --cover
```

## 环境变量

建立 `.env` 档案：

```env
# ElevenLabs Speech to Text
ELEVENLABS_API_KEY=xxx
ELEVENLABS_STT_MODEL=scribe_v2
ELEVENLABS_STT_LANGUAGE_CODE=jpn

# Google Gemini (翻译)
GEMINI_API_KEY=xxx
GEMINI_MODEL=gemini-3-flash-preview

# DeepSeek (chunk 结构修正)
DEEPSEEK_API_KEY=xxx
LLM_CHUNK_FIX_MAX_RETRIES=3            # 修正失败重试次数

# 可选：Gemini 翻译调校
GEMINI_THINKING_LEVEL=HIGH             # 翻译 thinking level: LOW/MEDIUM/HIGH
GEMINI_PRE_PASS_FRAME_INTERVAL_SECONDS=120 # pre-pass 全片图片抽样频率（每几秒一张，另外固定包含影片首尾帧）
GEMINI_PRE_PASS_FRAME_MAX_SIDE=768     # pre-pass 图片最长边尺寸
GEMINI_CHUNK_CHAR_LIMIT=6000           # 每块目标字元数 (约 5 分钟字幕)
GEMINI_CONCURRENCY=10                  # chunk 并发上限
GEMINI_CHUNK_MAX_RETRIES=3             # chunk 失败重试次数
GEMINI_CHUNK_FRAME_INTERVAL_SECONDS=30 # chunk 图片抽样频率（每几秒一张，另外固定包含每段首尾帧）
GEMINI_CHUNK_FRAME_MAX_SIDE=768        # chunk 图片最长边尺寸
GEMINI_CHUNK_MISSING_BLOCK_TOLERANCE=2 # 每块允许未对齐/缺漏字幕区块数上限
GEMINI_INTRO_SKIP_SECONDS=3.0          # 抽样参考帧时跳过影片开头 N 秒（避开电视台 logo/intro 帧），作用于 pre-pass 与首个 chunk

# 可选：Codex 后处理（需安装 Codex CLI）
ENABLE_SRT_REFINE=true             # 翻译后再用 Codex 润饰简体字幕
ENABLE_COVER_GENERATION=true       # 下载后并行 Codex 风格化封面图
CODEX_EXECUTABLE=codex             # Codex CLI 可执行文件名或绝对路径
CODEX_DEFAULT_TIMEOUT_SECS=900     # 单次 codex exec 调用超时（秒）

# 可选：下载/归档/封装
COOKIES_TXT_PATH=cookies.txt       # 影片来源网站 cookies (供 yt-dlp 使用)
ARCHIVED_PATH=NAS:\bangumi\ai\     # 归档路径 - 处理完直接移至指定资料夹并将资料夹名称改为影片名称
PACKAGE_PATH=NAS:\bangumi\package\ # 封装路径 - 将 ASS 字幕烧录进影片并复制封面到 <package_path>/<id>_<name>/
```

## 专案结构

```
projects/{video_id}/
├── project.json              # 专案状态与累计成本
├── video.mp4                 # 合并后的影片
├── video.ja.srt              # 日文原文字幕
├── .asr/                     # ASR 音档与 ElevenLabs 原始结果
│   ├── audio.opus
│   └── asr.json
├── .pre_pass/                # Gemini pre-pass 简报与图片快取
│   └── pre_pass.json
├── .chunks/                  # chunk 音档 / 图片 / 翻译回应快取（供 resume）
├── .refine/                  # Codex 润饰快取（可选）
├── poster.jpg                # yt-dlp 取得的原始封面
├── poster.cover.png          # Codex 风格化封面（可选）
├── video.cht.srt             # 简体中文翻译字幕
├── video.cht.refined.srt     # Codex 润饰后字幕（可选）
├── video.cht.finalized.srt   # 最终 SRT（标点清理 + 繁简用字转换，给不支援 ASS 的装置）
└── video.cht.ass             # 最终 ASS（套样式 + 标点清理 + 繁简用字转换）
```

> 文件名沿用的 `.cht` 后缀为历史命名，实际内容为**简体中文**。

## 测试

```bash
# 使用 uv
uv run pytest

# 或使用 pip
pytest
```

测试覆盖 ASR SRT 生成、Gemini 资产/规整/内联媒体、chunk 结构修正、字幕 finalize、媒体处理、yt-dlp 信息解析、workflow 断点与成本统计等。
