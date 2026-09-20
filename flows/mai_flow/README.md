# mai_flow — MAI-Transcribe-2 ASR pipeline

ElevenLabs Scribe v2 的替代 ASR 流程。走 OpenRouter 的
`microsoft/mai-transcribe-2`，成本约 **$0.10/h**（ElevenLabs $0.22/h
的一半以下），实测 60min Showroom 全程 82 秒跑完。

## 用法

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
uv run python -m flows.mai_flow.pipeline <视频或音频> <工作目录>
```

输出（全部可断点续跑）：

```
work_dir/
  audio.wav              # 16kHz 单声道 PCM
  chunks/chunk_XX.wav    # 静音点对齐的 ~5min 切片
  chunks/*.wav.json      # 每片原始 API 响应（缓存，重跑不重复计费）
  chunks/manifest.json   # 切片边界
  asr.json               # 合并后的 ElevenLabs 形状 payload
  out.srt                # 最终字幕
```

## 结构

| 文件 | 职责 |
|---|---|
| `chunker.py` | ffmpeg 抽音频 → silencedetect 找静音 → ~5min 切片 |
| `transcriber.py` | OpenRouter API 调用（verbose_json + word 时间戳 + diarization + phraseList），429/5xx 退避重试，逐片缓存 |
| `merge.py` | 片间偏移合并 → ElevenLabs `words[]` 形状（`word`→`text`、`speaker`→`speaker_id`，带 `cNN_sM` 片内前缀） |
| `pipeline.py` | 编排 + CLI 入口 |

## 断句

不断句逻辑在本目录 —— 合并后直接复用
`services/elevenlabs/srt_builder.py` 的词级断句引擎（硬标点强断 /
静音 gap / 软标点 / 助词安全切分 / hold time 延长）。MAI 日语输出是
逐字符 token，srt_builder 原生支持。

## 注意

- **speaker 编号是片内局部**的（`c03_s1`），跨片不保证同一人。
  双人对话场景够用；要严格对齐需另做 speaker embedding。
- **429 限流常见**，已内置重试；并发跑多个任务会加剧。
- phraseList 在 `transcriber.py:DEFAULT_PHRASES`，按档期成员改。
- `transcribeStyle` 用 `verbatim`（保留语气词，对口型轴更真实）；
  要干净文本改 `clean`。
