from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class JobStage(StrEnum):
    CREATED = "created"
    METADATA_FETCHED = "metadata_fetched"
    VIDEO_DOWNLOADED = "video_downloaded"
    AUDIO_EXTRACTED = "audio_extracted"
    ASR_COMPLETED = "asr_completed"
    PREPASS_COMPLETED = "prepass_completed"
    TRANSLATED = "translated"
    STRUCTURE_FIXED = "structure_fixed"
    FINALIZED = "finalized"
    CLEANUP_COMPLETED = "cleanup_completed"


ALLOWED_STATUS_TRANSITIONS = {
    (JobStatus.QUEUED, JobStatus.RUNNING),
    (JobStatus.RUNNING, JobStatus.RETRYING),
    (JobStatus.RETRYING, JobStatus.RUNNING),
    (JobStatus.RUNNING, JobStatus.SUCCEEDED),
    (JobStatus.RUNNING, JobStatus.FAILED),
    (JobStatus.QUEUED, JobStatus.CANCELLED),
    (JobStatus.RUNNING, JobStatus.CANCELLED),
    (JobStatus.FAILED, JobStatus.CANCELLED),
    (JobStatus.SUCCEEDED, JobStatus.EXPIRED),
}

STAGE_ORDER = [
    JobStage.CREATED,
    JobStage.METADATA_FETCHED,
    JobStage.VIDEO_DOWNLOADED,
    JobStage.AUDIO_EXTRACTED,
    JobStage.ASR_COMPLETED,
    JobStage.PREPASS_COMPLETED,
    JobStage.TRANSLATED,
    JobStage.STRUCTURE_FIXED,
    JobStage.FINALIZED,
    JobStage.CLEANUP_COMPLETED,
]


def assert_status_transition(current: JobStatus, target: JobStatus) -> None:
    if (JobStatus(current), JobStatus(target)) not in ALLOWED_STATUS_TRANSITIONS:
        raise ValueError(f"invalid job status transition: {current} -> {target}")


def assert_stage_transition(current: JobStage, target: JobStage) -> None:
    current_index = STAGE_ORDER.index(JobStage(current))
    target_index = STAGE_ORDER.index(JobStage(target))
    if target_index != current_index + 1:
        raise ValueError(f"invalid job stage transition: {current} -> {target}")
