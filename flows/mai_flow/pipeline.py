"""End-to-end MAI-Transcribe-2 pipeline: video/audio → SRT.

    python -m flows.mai_flow.pipeline <input> <work_dir> [--srt out.srt]

Stages (all resumable — chunk JSONs and wav slices are cached):
    1. extract   input → work_dir/audio.wav (16kHz mono PCM)
    2. chunk     silence-aligned ~5min slices → work_dir/chunks/
    3. transcribe per-chunk API calls → chunks/chunk_XX.wav.json
    4. merge     → work_dir/asr.json (ElevenLabs-shaped payload)
    5. srt       → work_dir/out.srt via services.elevenlabs.srt_builder
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from loguru import logger

# Allow running as `python -m flows.mai_flow.pipeline` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.elevenlabs.srt_builder import convert_payload_to_srt  # noqa: E402

from .chunker import (  # noqa: E402
    extract_audio, make_chunks, probe_duration, write_manifest,
)
from .merge import merge_chunks  # noqa: E402
from .transcriber import transcribe_chunk  # noqa: E402


def run(
    input_path: Path,
    work_dir: Path,
    srt_path: Path | None = None,
    phrases: list[str] | None = None,
) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    wav_path = work_dir / "audio.wav"
    asr_path = work_dir / "asr.json"
    srt_path = srt_path or work_dir / "out.srt"

    # 1. extract
    if not wav_path.exists():
        extract_audio(input_path, wav_path)
    total = probe_duration(wav_path)
    logger.info(f"Audio duration: {total:.1f}s")

    # 2. chunk
    chunks_dir = work_dir / "chunks"
    chunks = make_chunks(wav_path, chunks_dir, total)
    write_manifest(chunks, chunks_dir / "manifest.json")

    # 3. transcribe (cached per chunk)
    responses = []
    for chunk in chunks:
        t0 = time.time()
        resp = transcribe_chunk(chunk.path, chunk.cache_path, phrases)
        logger.info(
            f"chunk {chunk.index} [{chunk.start:.0f}-{chunk.end:.0f}s]: "
            f"{time.time() - t0:.0f}s, "
            f"{len(resp.get('words') or [])} words"
        )
        responses.append(resp)

    # 4. merge into ElevenLabs-shaped payload
    payload = merge_chunks(chunks, responses)
    asr_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    meta = payload["_mai_meta"]
    logger.info(
        f"Merged {meta['chunks']} chunks: {meta['audio_seconds']:.0f}s audio, "
        f"${meta['cost_usd']:.4f} → {asr_path}"
    )

    # 5. SRT via the existing word-level segmentation engine
    srt_path.write_text(convert_payload_to_srt(payload), encoding="utf-8")
    logger.success(f"SRT written: {srt_path}")
    return srt_path


def main() -> None:
    parser = argparse.ArgumentParser(description="MAI-Transcribe-2 → SRT")
    parser.add_argument("input", type=Path, help="video or audio file")
    parser.add_argument("work_dir", type=Path, help="working/output directory")
    parser.add_argument("--srt", type=Path, default=None, help="SRT output path")
    args = parser.parse_args()
    run(args.input, args.work_dir, args.srt)


if __name__ == "__main__":
    main()
