"""LLM translation stage for mai_flow.

Takes merged Japanese lines (from segment_llm) and translates to
Simplified Chinese using the subtitle-group prompt in
translate_prompt.md. The model sees numbered lines and returns
{"lines": [{"id": N, "zh": "..."}]}. Timestamps never leave this file.

Batched (~80 lines/call) with per-batch JSON cache for resume.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from loguru import logger

from .llm import generate_json
from .segment_llm import MergedLine

BATCH_SIZE = 80
PROMPT_PATH = Path(__file__).parent / "translate_prompt.md"

# --- deterministic post-processing (subtitle-group rules) -------------------
# The model is asked to follow these, but we enforce them mechanically so a
# sloppy batch can't leak violations into the final SRT.

# Banned filler chars must never appear in output.
_BANNED_CHARS = "啊嗯欸"

# Member names: simplified → official kanji (绝对保留原则).
_NAME_FIXES = {
    "小田仓": "小田倉", "小田岛": "小田倉",
    "小岛": "小島", "小倉丽奈": "小田倉麗奈",
    "小田倉丽奈": "小田倉麗奈", "小島凪纱": "小島凪紗",
    "小田仓丽奈": "小田倉麗奈",
    "斋藤飞鸟": "齋藤飛鳥", "渡边理佐": "渡邉理佐",
    "高桥未来虹": "髙橋未来虹", "川崎樱": "川﨑桜",
    "齐藤京子": "齊藤京子", "滨岸": "濱岸",
    "守屋丽奈": "守屋麗奈", "佐藤璃果": "佐藤璃果",
    "远藤理子": "遠藤理子", "村山美羽": "村山美羽",
    "的野美青": "的野美青", "向井纯叶": "向井純葉",
    "村井优": "村井優", "山下瞳月": "山下瞳月",
    "谷口爱季": "谷口愛季", "中岛优月": "中嶋優月",
    "石森璃花": "石森璃花", "大园玲": "大園玲",
    "大沼晶保": "大沼晶保", "幸阪茉里乃": "幸阪茉里乃",
    "田村保乃": "田村保乃", "藤吉夏铃": "藤吉夏鈴",
    "增本绮良": "増本綺良", "松田里奈": "松田里奈",
    "森田光": "森田ひかる", "山崎天": "山﨑天",
}


def _clean_zh(text: str) -> str:
    """Enforce subtitle-group output rules on every dialogue part."""
    cleaned_parts = []
    for part in text.split(" -"):
        for simp, official in _NAME_FIXES.items():
            part = part.replace(simp, official)
        part = part.replace("，", " ").replace("、", " ")
        part = part.replace("“", "「").replace("”", "」")
        for ch in _BANNED_CHARS:
            part = part.replace(ch, "")
        # Remove punctuation left behind by an omitted filler at either edge.
        part = part.strip().lstrip("。，、 ").rstrip("。，、 ")
        if part:
            cleaned_parts.append(part)
    return " -".join(cleaned_parts)
OUTPUT_CONTRACT = """
【输出契约 — 覆盖上方所有输出格式要求】
输入是带编号的日文字幕行列表（id<TAB>日文）。你必须输出 JSON：
{"lines": [{"id": <int>, "zh": "<简体中文译文>"}, ...]}

- 每个输入 id 必须恰好出现一次，禁止遗漏、禁止新增 id。
- zh 字段只放译文文本，不要注释、不要编号、不要时间轴。
- 日文中已有的 " -" 说话人分隔符必须保留在译文对应位置。
- 预分析报告不要输出——只在内部执行，最终只输出上述 JSON。
"""


def _load_system() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8") + "\n" + OUTPUT_CONTRACT


def _translate_batch(
    lines: list[MergedLine], ids: list[int], system: str
) -> dict[int, str]:
    body = "\n".join(f"{i}\t{lines[i].text}" for i in ids)
    result = generate_json(body, system=system)
    out: dict[int, str] = {}
    for item in result.get("lines", []):
        if isinstance(item, dict) and "id" in item and "zh" in item:
            out[int(item["id"])] = _clean_zh(str(item["zh"]))
    missing = [i for i in ids if i not in out]
    if missing:
        raise RuntimeError(f"translation missing ids: {missing[:10]}")
    return out


def translate_lines(
    lines: list[MergedLine],
    cache_dir: Path | None = None,
) -> list[str]:
    """Translate all lines; returns zh strings aligned with `lines`."""
    system = _load_system()
    translations: dict[int, str] = {}
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)

    i = 0
    while i < len(lines):
        ids = list(range(i, min(i + BATCH_SIZE, len(lines))))
        # Key by content hash, not index: line boundaries shift whenever
        # atomize/merge changes, and an index-keyed cache would silently
        # splice stale translations onto the new timeline.
        body_key = hashlib.sha1(
            "\n".join(f"{j}\t{lines[j].text}" for j in ids).encode()
        ).hexdigest()[:16]
        cache = cache_dir / f"batch_{body_key}.json" if cache_dir else None
        if cache and cache.exists():
            batch = {int(k): v for k, v in
                     json.loads(cache.read_text(encoding="utf-8")).items()}
        else:
            try:
                batch = _translate_batch(lines, ids, system)
            except Exception as e:
                logger.warning(f"translate batch {i} failed: {e}; "
                               f"falling back to source text")
                batch = {j: lines[j].text for j in ids}
            else:
                # Only persist real translations — a fallback batch must
                # not poison the cache, so re-runs retry that batch.
                if cache:
                    cache.write_text(
                        json.dumps(batch, ensure_ascii=False),
                        encoding="utf-8",
                    )
        translations.update(batch)
        i += BATCH_SIZE

    return [_clean_zh(translations[i]) for i in range(len(lines))]



def render_srt(lines: list[MergedLine], texts: list[str]) -> str:
    def ts(t: float) -> str:
        t = max(0.0, t)
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")

    def has_content(text: str) -> bool:
        # A block needs at least one CJK char or alphanumeric to be shown.
        return any(ch.isalnum() or "一" <= ch <= "鿿" for ch in text)

    def clean_dialogue(text: str) -> str:
        # Drop " -" segments that carry no real text after cleanup.
        parts = text.split(" -")
        kept = [p for p in parts if has_content(p)]
        return " -".join(kept)

    blocks = []
    n = 0
    for line, text in zip(lines, texts):
        text = clean_dialogue(text)
        if not has_content(text):
            continue
        n += 1
        blocks.append(f"{n}\n{ts(line.start)} --> {ts(line.end)}\n{text}\n")
    return "\n".join(blocks)
