import sys, os
sys.path.insert(0, ".")
from services.saas.pipeline import WorkflowSubtitlePipeline
from services.saas.db import connect_database
from pathlib import Path

JOB_ID = "job_9948b90abda8493b9b3c649c0bc00e07"
DATA_DIR = "/Users/yoru/data/bangumi-grillmaster/jobs"
conn = connect_database("/Users/yoru/data/bangumi-grillmaster/app.db")

upload_dir = Path(DATA_DIR) / "uploads" / JOB_ID
files = list(upload_dir.glob("*"))
src = files[0]
print(f"Processing: {src.name}")

conn.execute("UPDATE jobs SET status='running', stage='created', worker_id='manual' WHERE id=?", (JOB_ID,))
conn.commit()

project_id = f"upload_{JOB_ID[:12]}"
p = WorkflowSubtitlePipeline(project_root=Path.cwd())
result = p._do_upload_pipeline(project_id, src, on_stage_change=None)

conn.execute("""UPDATE jobs SET status='succeeded', stage='cleanup_completed', source_srt_path=?, result_srt_path=? WHERE id=?""", (result.source_srt_path, result.finalized_srt_path, JOB_ID))
conn.commit()
print("JOB DONE")
