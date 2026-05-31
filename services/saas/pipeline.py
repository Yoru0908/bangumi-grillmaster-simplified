from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol


@dataclass(frozen=True)
class PipelineMetadata:
    video_title: str
    video_duration_seconds: int


@dataclass(frozen=True)
class PipelineResult:
    source_srt_path: str
    translated_srt_path: str
    finalized_srt_path: str


class PipelineError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class SubtitlePipeline(Protocol):
    def fetch_metadata(self, source_url: str) -> PipelineMetadata:
        raise NotImplementedError

    def run(self, *, job_id: str, source_url: str) -> PipelineResult:
        raise NotImplementedError


class WorkflowSubtitlePipeline:
    """Adapter that exposes the existing CLI workflow through the SaaS pipeline API."""

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        translation_hint: str | None = None,
        parent_project_path: str | None = None,
        metadata_fetcher=None,
    ):
        self.project_root = Path(project_root) if project_root is not None else None
        self.translation_hint = translation_hint
        self.parent_project_path = parent_project_path
        self.metadata_fetcher = metadata_fetcher

    def fetch_metadata(self, source_url: str) -> PipelineMetadata:
        try:
            metadata_fetcher = self.metadata_fetcher or _default_metadata_fetcher()
            info = metadata_fetcher(source_url)
        except Exception as exc:
            raise PipelineError("METADATA_FAILED", str(exc)) from exc
        if info.duration is None:
            raise PipelineError(
                "METADATA_FAILED",
                f"missing duration for source: {source_url}",
            )
        return PipelineMetadata(
            video_title=info.title,
            video_duration_seconds=int(info.duration),
        )

    def run(self, *, job_id: str, source_url: str, on_stage_change = None) -> PipelineResult:
        try:
            # Handle uploaded files
            if source_url.startswith("upload://"):
                import shutil, os
                upload_dir = Path(os.environ.get("SAAS_JOB_DATA_DIR", "/tmp")) / "uploads" / job_id
                files = list(upload_dir.glob("*"))
                if not files:
                    raise PipelineError("UPLOAD_MISSING", "Uploaded file not found")
                src = files[0]
                project_id = f"upload_{job_id[:12]}"
                return self._do_upload_pipeline(project_id, src, on_stage_change)
            import project as project_module
            import workflow as workflow_module
            from project import ProgressStage, Project

            project_id = Project.parse_source_str(source_url)
            stop_poll = threading.Event()

            def _poll_stage():
                stage_map = {
                    "METADATA_FETCHED": ("metadata_fetched", "获取视频信息完成"),
                    "DOWNLOADED": ("video_downloaded", "视频下载完成"),
                    "VIDEO_PROCESSED": ("video_downloaded", "视频合并完成"),
                    "AUDIO_EXTRACTED": ("audio_extracted", "音频提取完成"),
                    "ASR_COMPLETED": ("asr_completed", "语音识别完成"),
                    "PRE_PASS_COMPLETED": ("prepass_completed", "预分析完成"),
                    "TRANSLATED": ("translated", "翻译中..."),
                    "STRUCTURE_FIXED": ("structure_fixed", "结构修正完成"),
                    "FINALIZED": ("finalized", "最终化中..."),
                }
                last_stage = ""
                while not stop_poll.is_set():
                    try:
                        pj = self.project_root / "projects" / project_id / "project.json"
                        if pj.exists():
                            data = json.loads(pj.read_text())
                            current = data.get("progress", "")
                            if current and current != last_stage:
                                last_stage = current
                                mapped = stage_map.get(current)
                                if mapped and on_stage_change:
                                    on_stage_change(mapped[0], mapped[1])
                    except Exception:
                        pass
                    time.sleep(3)

            if on_stage_change:
                threading.Thread(target=_poll_stage, daemon=True).start()

            with _project_root_override(self.project_root):
                workflow_module.submit_project(
                    source_str=source_url,
                    translation_hint=self.translation_hint,
                    break_after=None,
                    parent_project_path=self.parent_project_path,
                    enable_refine=False,
                    enable_cover=False,
                )
                if on_stage_change:
                    stop_poll.set()
                project = Project.from_source_str(source_url)
                result = PipelineResult(
                    source_srt_path=str(project.srt_path),
                    translated_srt_path=str(project.translated_path),
                    finalized_srt_path=str(project.finalized_srt_path),
                )
        except PipelineError:
            raise
        except Exception as exc:
            message = str(exc)
            raise PipelineError(_classify_pipeline_error(message), message) from exc

        return result

    def _do_upload_pipeline(self, project_id, src_path, on_stage_change):
        import shutil
        import workflow as workflow_module
        from project import Project
        proj_dir = self.project_root / "projects" / project_id
        proj_dir.mkdir(parents=True, exist_ok=True)
        video_path = proj_dir / "video.mp4"
        if on_stage_change: on_stage_change("video_downloaded", "上传视频已就绪")
        shutil.copy2(str(src_path), str(video_path))
        with _project_root_override(self.project_root):
            # Process directly — video already exists
            workflow_module.process_project(project_id)
        return PipelineResult(
            source_srt_path=str(proj_dir / "video.ja.srt"),
            translated_srt_path=str(proj_dir / "video.cht.srt"),
            finalized_srt_path=str(proj_dir / "video.cht.finalized.srt"),
        )


class _project_root_override:
    def __init__(self, project_root: Path | None):
        self.project_root = project_root
        self.original: str | None = None

    def __enter__(self):
        if self.project_root is None:
            return
        import project as project_module

        self.original = project_module.PROJECT_ROOT_NAME
        project_module.PROJECT_ROOT_NAME = str(self.project_root)

    def __exit__(self, exc_type, exc, tb):
        if self.original is not None:
            import project as project_module

            project_module.PROJECT_ROOT_NAME = self.original


def _default_metadata_fetcher():
    from services.ytdlp.info import get_video_info

    return get_video_info


def _classify_pipeline_error(message: str) -> str:
    if "RESOURCE_EXHAUSTED" in message or "prepayment credits are depleted" in message:
        return "GEMINI_QUOTA_EXHAUSTED"
    return "PIPELINE_FAILED"