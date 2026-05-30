import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.saas.pipeline import PipelineError, WorkflowSubtitlePipeline


class FakeVideoInfo:
    def __init__(self, *, title: str, duration: int | None):
        self.title = title
        self.duration = duration


class WorkflowSubtitlePipelineTests(unittest.TestCase):
    def test_fetch_metadata_returns_title_and_duration_from_ytdlp(self):
        calls = []
        pipeline = WorkflowSubtitlePipeline(
            metadata_fetcher=lambda url: calls.append(url)
            or FakeVideoInfo(title="Demo Video", duration=123)
        )

        metadata = pipeline.fetch_metadata("https://www.youtube.com/watch?v=demo")

        self.assertEqual(calls, ["https://www.youtube.com/watch?v=demo"])
        self.assertEqual(metadata.video_title, "Demo Video")
        self.assertEqual(metadata.video_duration_seconds, 123)

    def test_fetch_metadata_rejects_missing_duration(self):
        pipeline = WorkflowSubtitlePipeline(
            metadata_fetcher=lambda url: FakeVideoInfo(title="Demo Video", duration=None)
        )

        with self.assertRaisesRegex(PipelineError, "missing duration"):
            pipeline.fetch_metadata("https://www.youtube.com/watch?v=demo")

    def test_run_submits_project_with_phase1_flags_and_returns_project_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "projects"
            pipeline = WorkflowSubtitlePipeline(project_root=project_dir)

            with (
                patch.dict(
                    "os.environ",
                    {
                        "GEMINI_API_KEY": "test-gemini",
                        "DEEPSEEK_API_KEY": "test-deepseek",
                    },
                ),
                patch("workflow.submit_project") as submit_project,
            ):
                result = pipeline.run(
                    job_id="job_1",
                    source_url="https://www.youtube.com/watch?v=demo",
                )

            submit_project.assert_called_once_with(
                source_str="https://www.youtube.com/watch?v=demo",
                translation_hint=None,
                break_after=None,
                parent_project_path=None,
                enable_refine=False,
                enable_cover=False,
            )
            self.assertEqual(
                result.source_srt_path,
                str(project_dir / "v=demo" / "video.ja.srt"),
            )
            self.assertEqual(
                result.translated_srt_path,
                str(project_dir / "v=demo" / "video.cht.srt"),
            )
            self.assertEqual(
                result.finalized_srt_path,
                str(project_dir / "v=demo" / "video.cht.finalized.srt"),
            )

    def test_run_wraps_workflow_errors_as_pipeline_error(self):
        pipeline = WorkflowSubtitlePipeline()

        with (
            patch.dict(
                "os.environ",
                {
                    "GEMINI_API_KEY": "test-gemini",
                    "DEEPSEEK_API_KEY": "test-deepseek",
                },
            ),
            patch("workflow.submit_project", side_effect=RuntimeError("boom")),
        ):
            with self.assertRaises(PipelineError) as context:
                pipeline.run(
                    job_id="job_1",
                    source_url="https://www.youtube.com/watch?v=demo",
                )

        self.assertEqual(context.exception.code, "PIPELINE_FAILED")
        self.assertIn("boom", context.exception.message)

    def test_run_classifies_gemini_resource_exhausted_errors(self):
        pipeline = WorkflowSubtitlePipeline()

        with (
            patch.dict(
                "os.environ",
                {
                    "GEMINI_API_KEY": "test-gemini",
                    "DEEPSEEK_API_KEY": "test-deepseek",
                },
            ),
            patch(
                "workflow.submit_project",
                side_effect=RuntimeError(
                    "Pre-pass failed after 3 attempts: 429 RESOURCE_EXHAUSTED"
                ),
            ),
        ):
            with self.assertRaises(PipelineError) as context:
                pipeline.run(
                    job_id="job_1",
                    source_url="https://www.youtube.com/watch?v=demo",
                )

        self.assertEqual(context.exception.code, "GEMINI_QUOTA_EXHAUSTED")
        self.assertIn("RESOURCE_EXHAUSTED", context.exception.message)


if __name__ == "__main__":
    unittest.main()
