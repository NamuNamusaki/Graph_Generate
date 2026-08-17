"""
Simulated (mock) data and behaviour for web_api/app_frontend.py.
All function in this files:
1. Stimulate output filepath fro backend -- simulate_worker_output_path
2. Stimulate job progress -- mock_job_progress
3. Stimulate email notification -- send_completion_email, 
                                   subscribe_notification, 
                                   notify_subscriber

Stimulate functions:
  1. Job progress   -- advances 1 step per poll  -> real progress written by the worker
  2. Worker output  -- points at Result_Sequence -> the real path the worker wrote to
  3. Email          -- prints to the console     -> a real SMTP/email service

Authentication is in auth.py 
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import db

# -----------------------------------------------------------------------------------------
# 1. PIPELINE PROGRESS (simulated)
# -----------------------------------------------------------------------------------------
PIPELINE_STEPS = [
    "Reading Data",
    "In silico Digestion",
    "Bioactivity Matching",
    "Generating Results",
]

SAMPLE_RESULT_DIR = Path(__file__).resolve().parent / "Result_Sequence"

def simulate_worker_output_path(job_uuid: str) -> str:
    """Stands in for the path a real worker would have written results to."""
    return str(SAMPLE_RESULT_DIR)

def mock_job_progress(row: dict) -> Tuple[str, int, Optional[str]]:
    """
    Moves a job one pipeline step forward, simulating worker progress.
    """
    list_step_total: List[str] = row["list_step_total"] or PIPELINE_STEPS
    step_current: int = row["step_current"]
    status: str = row["status"]
    output_result_path: Optional[str] = row["output_result_path"]

    already_completed = status == "COMPLETED"

    # Advance one step per poll.
    if step_current < len(list_step_total):
        step_current += 1
        db.update_job_progress(row["job_uuid"], step_current=step_current)

    # Past the last step -> the job is finished.
    if step_current >= len(list_step_total):
        status = "COMPLETED"
        if not output_result_path:
            output_result_path = simulate_worker_output_path(row["job_uuid"])
        # Guarded by already_completed so completed_at isn't re-stamped on
        # every later poll of an already-finished job.
        if not already_completed:
            db.update_job_progress(
                row["job_uuid"],
                status=status,
                output_result_path=output_result_path,
                completed_at_now=True,
            )
    return status, step_current, output_result_path

# -----------------------------------------------------------------------------------------
# 2. COMPLETION EMAIL (simulated)
# -----------------------------------------------------------------------------------------
# Where the frontend's Dashboard page lives -- the mailed link opens straight
# to this job's results (?job_uuid=...).
# This MUST be a browser-reachable URL, NOT an internal Docker service name:
RESULT_BASE_URL = os.environ.get("SMARTBIOPEP_APP_URL", "http://localhost:8501") + "/Dashboard"

job_notifications: Dict[str, dict] = {}

def subscribe_notification(job_uuid: str, email: str) -> None:
    """Records that `email` wants to be told when this job finishes."""
    job_notifications.setdefault(job_uuid, {})["notify_email"] = email

def send_completion_email(email: str, job_uuid: str) -> str:
    """
    Stands in for a real email service -- prints the message to the container
    log instead of sending it. Returns the results URL that "was mailed", so
    the frontend can display it (this demo has no real inbox to check).
    """
    result_url = f"{RESULT_BASE_URL}?job_uuid={job_uuid}"
    print(
        f"[mock email] To: {email}\n"
        f"[mock email] Subject: Your SmartBioPep job is ready\n"
        f"[mock email] Body: Your analysis has finished. View your results: {result_url}"
    )
    return result_url


def notify_subscriber(job_uuid: str) -> Optional[str]:
    """
    Sends the completion email exactly once, and only if someone actually
    subscribed for this job via POST /notifications.
    """
    notif = job_notifications.get(job_uuid)
    if not notif or not notif.get("notify_email"):
        return None

    if not notif.get("result_email_sent"):
        notif["result_url"] = send_completion_email(notif["notify_email"], job_uuid)
        notif["result_email_sent"] = True

    return notif.get("result_url")
