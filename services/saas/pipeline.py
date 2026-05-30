from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


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

    def run(self, *, job_id: str, source_url: str) -> PipelineResult:
        try:
            import project as project_module
            import workflow as workflow_module
            from project import Project

            with _project_root_override(self.project_root):
                workflow_module.submit_project(
                    source_str=source_url,
                    translation_hint=self.translation_hint,
                    break_after=None,
                    parent_project_path=self.parent_project_path,
                    enable_refine=False,
                    enable_cover=False,
                )
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
