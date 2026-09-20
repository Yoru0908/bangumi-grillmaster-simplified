"""LLM-assisted subtitle segmentation for mai_flow.

Stage 2 of the pipeline. Two layers:

1. ``build_atoms`` — deterministic, word-level. MAI words are split into
   minimal atoms at physical boundaries only: speaker change, inter-word
   silence, hard punctuation, and a length fallback. No semantic judgment,
   so atoms can never be "wrong" — at worst slightly too small.

2. ``merge_utterances`` — the LLM sees numbered atoms (with speaker and
   gap) and returns groups of indices to merge into subtitle lines.
   Timestamps are recomputed from atom boundaries, so the model can never
   corrupt the timeline.

The system prompt lives in ``segment_prompt.md`` — the same file the
seg_lab test bench reads, so prompt iteration in the lab carries over
directly.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from .llm import generate_json

# Atoms per LLM call, plus trailing context shown but not decided.
BATCH_SIZE = 120
CONTEXT_TAIL = 20

PROMPT_PATH = Path(__file__).parent / "segment_prompt.md"

HARD_PUNCT = set("。！？?!")
SOFT_PUNCT = set("、，,：:；;")

SILENCE_SPLIT_S = 1.0
SOFT_SPLIT_CHARS = 24
MAX_ATOM_CHARS = 48

# Merging across a pause this long is almost always wrong; reject such
# groups even if the model returns them.
MAX_MERGE_GAP_S = 2.0


def _load_system() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


@dataclass
class MergedLine:
    start: float
    end: float
    text: str
    utterance_ids: list[int]


def build_atoms(payload: dict) -> list[dict]:
    """Split MAI words into minimal atoms at word-level boundaries."""
    words = sorted(payload["words"], key=lambda w: w["start"])
    atoms: list[dict] = []
    cur: list[dict] = []

    def flush() -> None:
        if not cur:
            return
        atoms.append({
            "speaker_id": cur[0].get("speaker_id"),
            "start": cur[0]["start"],
            "end": cur[-1]["end"],
            "text": "".join(w["text"] for w in cur),
        })
        cur.clear()

    for w in words:
        if cur:
            prev = cur[-1]
            gap = w["start"] - prev["end"]
            text_len = sum(len(x["text"]) for x in cur)
            last = prev["text"][-1]
            if (
                w.get("speaker_id") != prev.get("speaker_id")
                or gap >= SILENCE_SPLIT_S
                or last in HARD_PUNCT
                or (last in SOFT_PUNCT and text_len >= SOFT_SPLIT_CHARS)
                or text_len >= MAX_ATOM_CHARS
            ):
                flush()
        cur.append(w)
    flush()

    prev_end = None
    for a in atoms:
        a["gap"] = 0.0 if prev_end is None else max(0.0, a["start"] - prev_end)
        prev_end = a["end"]
    return atoms


def _format_atom(i: int, a: dict) -> str:
    spk = (a.get("speaker_id") or "?").split("_")[-1]
    return f"{i} | {spk} | +{a['gap']:.2f}s | {a['text']}"


def _llm_merge_batch(
    atoms: list[dict], start_idx: int, end_idx: int
) -> list[list[int]]:
    """Ask the LLM for safe merge groups within one batch."""
    lines = []
    ctx_end = min(end_idx + CONTEXT_TAIL, len(atoms))
    for i in range(start_idx, ctx_end):
        marker = "" if i < end_idx else "  (context)"
        lines.append(_format_atom(i, atoms[i]) + marker)
    prompt = (
        "对以下 atom 做合并决策。只对不带 (context) 标记的行做决定；"
        "context 行仅供你判断边界语义。\n\n" + "\n".join(lines)
    )
    result = generate_json(
        prompt,
        system=_load_system(),
        model=os.environ.get("SEGMENT_MODEL", "gemini-2.5-pro"),
    )
    raw_groups = result.get("groups", []) if isinstance(result, dict) else []

    clean: list[list[int]] = []
    used: set[int] = set()
    for raw in raw_groups:
        if not isinstance(raw, list) or len(raw) < 2:
            continue
        if not all(isinstance(i, int) for i in raw):
            continue
        group = raw
        if (
            group != sorted(group)
            or group != list(range(group[0], group[-1] + 1))
            or group[0] < start_idx
            or group[-1] >= end_idx
            or any(i in used for i in group)
        ):
            continue
        # Never let a group bridge a long pause even if the model asked.
        if any(
            atoms[b]["start"] - atoms[a]["end"] >= MAX_MERGE_GAP_S
            for a, b in zip(group, group[1:])
        ):
            continue
        clean.append(group)
        used.update(group)
    return clean


def merge_utterances(
    atoms: list[dict],
    cache_dir: Path | None = None,
) -> list[MergedLine]:
    """Return merged subtitle lines.

    ``cache_dir`` holds one JSON per batch (``batch_XXXX.json``) so a
    failed batch never poisons the whole run — re-running only retries
    the missing files.  Each batch also gets one in-process retry before
    falling back to unmerged atoms.
    """
    groups: list[list[int]] = []
    i = 0
    while i < len(atoms):
        end = min(i + BATCH_SIZE, len(atoms))
        cache_file = (
            cache_dir / f"batch_{i:05d}.json" if cache_dir else None
        )
        if cache_file and cache_file.exists():
            groups.extend(
                json.loads(cache_file.read_text(encoding="utf-8"))
            )
        else:
            batch_groups = None
            for attempt in (1, 2):
                try:
                    batch_groups = _llm_merge_batch(atoms, i, end)
                    break
                except Exception as e:
                    logger.warning(
                        f"segment batch {i}-{end} attempt {attempt} "
                        f"failed: {e}"
                    )
            if batch_groups is not None:
                groups.extend(batch_groups)
                # Only persist successful batches — a failed batch must
                # not poison the cache, so re-runs retry just that batch.
                if cache_file:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(
                        json.dumps(batch_groups, ensure_ascii=False),
                        encoding="utf-8",
                    )
        i = end

    # Apply groups; ungrouped atoms become single lines.
    grouped = {i for g in groups for i in g}
    lines: list[MergedLine] = []
    i = 0
    while i < len(atoms):
        g = next((g for g in groups if g[0] == i), None)
        if g:
            parts = []
            prev_spk = None
            for j in g:
                u = atoms[j]
                spk = u.get("speaker_id")
                if prev_spk is not None and spk != prev_spk:
                    parts.append(" -" + u["text"])
                else:
                    parts.append(u["text"])
                prev_spk = spk
            lines.append(MergedLine(
                start=atoms[g[0]]["start"],
                end=atoms[g[-1]]["end"],
                text="".join(parts),
                utterance_ids=g,
            ))
            i = g[-1] + 1
        else:
            u = atoms[i]
            lines.append(MergedLine(
                start=u["start"], end=u["end"],
                text=u["text"], utterance_ids=[i],
            ))
            i += 1
    logger.info(
        f"LLM merge: {len(atoms)} atoms → {len(lines)} lines "
        f"({len(grouped)} merged)"
    )
    return lines
