# mai_flow — MAI-Transcribe-2 ASR pipeline

ElevenLabs Scribe v2 的替代 ASR 流程。走 OpenRouter 的
`microsoft/mai-transcribe-2`，成本约 **$0.10/h**（ElevenLabs $0.22/h
的一半以下），实测 60min Showroom 全程 82 秒跑完。

## 用法

```bash
export OPENROUTER_API_KEY=sk-or-v1-...        # ASR 用
export GEMINI_AGENT_PLATFORM_PROXY_URL=https://gemini-proxy.srzwyuu.workers.dev  # LLM 用
uv run python -m flows.mai_flow.pipeline <视频或音频> <工作目录> [--llm-segment] [--translate]

输出（全部可断点续跑）：

```
work_dir/
  audio.wav              # 16kHz 单声道 PCM
  chunks/chunk_XX.wav    # 静音点对齐的 ~5min 切片
  chunks/*.wav.json      # 每片原始 API 响应（缓存，重跑不重复计费）
  chunks/manifest.json   # 切片边界
  asr.json               # 合并后的 ElevenLabs 形状 payload
  out.srt                # 确定性断句基线（srt_builder）
  merge_cache/           # LLM 合并决策 per-batch 缓存（--llm-segment）
  out_llm_ja.srt         # LLM 断句日文（--llm-segment）
  zh_cache/              # 翻译批次缓存（--translate）
  out_zh.srt             # 中文字幕（--translate）

## 结构

| 文件 | 职责 |
|---|---|
| `chunker.py` | ffmpeg 抽音频 → silencedetect 找静音 → ~5min 切片 |
| `transcriber.py` | OpenRouter API 调用（verbose_json + word 时间戳 + diarization + phraseList），429/5xx 退避重试，逐片缓存 |
| `merge.py` | 片间偏移合并 → ElevenLabs `words[]` 形状（`word`→`text`、`speaker`→`speaker_id`，带 `cNN_sM` 片内前缀） |
| `segment_llm.py` | 词级 atomize（确定性）+ LLM 合并（`segment_prompt.md`） |
| `translate_llm.py` | LLM 翻译（`translate_prompt.md`）+ 确定性后处理 |
| `seg_lab.py` | prompt 迭代测试台，与 pipeline 共享 atomize/prompt |
| `llm.py` | LLM client：proxy / OpenRouter / AI Studio / Vertex 四后端 |
| `pipeline.py` | 编排 + CLI 入口 |

## 断句（两阶段）

**拆 = 纯算法**（`build_atoms`）：词级时间戳上切最小 atom ——
speaker 切换 / 词间静音 ≥1s / 硬标点结尾 / 软标点(≥24字) /
48字长度兜底。边界都是物理事实，不会错切。

**合 = LLM**（`merge_utterances`）：模型只看 atom 列表（id/speaker/
gap/text），输出 `{"groups": [[id,...]]}`，程序按 atom 边界回算
时间戳 —— LLM 永远不碰时间轴。默认模型 `gemini-2.5-pro`，
`SEGMENT_MODEL` env 可覆盖。

无 `--llm-segment` 时 `out.srt` 仍走 srt_builder 确定性断句基线。

## Prompt 迭代

```bash
# 只看原子化（不调 LLM）
uv run python -m flows.mai_flow.seg_lab asr.json --start 0 --end 120 --atoms
# 跑一段看效果
uv run python -m flows.mai_flow.seg_lab asr.json --start 0 --end 120
# 换 prompt / 模型
uv run python -m flows.mai_flow.seg_lab asr.json --system my.md --model gemini-3.8-flash
```

改 `segment_prompt.md` 后直接重跑 lab 即可，pipeline 读同一份。

## 注意

- **speaker 编号是片内局部**的（`c03_s1`），跨片不保证同一人。
  双人对话场景够用；要严格对齐需另做 speaker embedding。
- **429 限流常见**，已内置重试；并发跑多个任务会加剧。
- phraseList 在 `transcriber.py:DEFAULT_PHRASES`，按档期成员改。
- `transcribeStyle` 用 `verbatim`（保留语气词，对口型轴更真实）；
  要干净文本改 `clean`。
