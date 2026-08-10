from fastapi import FastAPI, Form, Header, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Dict, Optional
import uvicorn
import time
import io
import re
import itertools
import uuid
from pathlib import Path
from fastapi.responses import Response
import random
import os
import pandas as pd

app = FastAPI()

# -----------------------------------------------------------------------------------------
# MOCK DATABASE FOR JOB TRACKING
# -----------------------------------------------------------------------------------------
# job_id vs. job_uuid — two distinct identifiers, mirroring JOBS in the ERD:
#   - job_uuid: generated HERE by the backend (submit_analysis(), below) when
#     the job is created, and returned once in the POST /api/jobs response.
#     From then on it's the identifier every API call uses (status polling,
#     results, notifications) -- it's what the wire protocol is keyed on.
#     The frontend never invents this value; it only ever echoes back
#     whatever the backend handed it.
#   - job_id: the DB-side primary key, generated HERE by the backend when the
#     job row is created (_next_job_id() stands in for a real auto-increment
#     PK). It's internal bookkeeping — returned once on creation so the
#     frontend can use it for its own project tracking / "which of my
#     submissions is this" UI (session state key, project switcher label),
#     but it is never used to address an API call.
# mock_jobs_db is keyed by job_uuid (that's what every endpoint below looks
# jobs up by); each row also carries its own job_id field.
mock_jobs_db = {}
_job_id_counter = itertools.count(1)
PIPELINE_STEPS = ["Reading Data", "In silico Digestion", "Bioactivity Matching", "Generating Results"]


def _next_job_id() -> str:
    """Stands in for a real DB auto-increment primary key."""
    return f"JOB{next(_job_id_counter):06d}"

# -----------------------------------------------------------------------------------------
# COMPLETION EMAIL
# -----------------------------------------------------------------------------------------
# Where the frontend's Dashboard page lives -- the link mailed out below opens
# straight to this job's results (?job_uuid=...), same identifier every other
# API call uses.
# This must be a browser-reachable URL, NOT an internal Docker service name --
# it's mailed to the user and opened from their own machine, so it has to be
# whatever address/port the frontend container is actually published on
# (e.g. http://localhost:8501 in local dev, or a real public domain once
# deployed). Override via env var; the localhost default only works for
# running everything on one machine outside Docker.
RESULT_BASE_URL = os.environ.get("SMARTBIOPEP_PUBLIC_APP_URL", "http://localhost:8501") + "/Dashboard"


def _send_completion_email(email: str, job_uuid: str) -> str:
    """
    STAND-IN for a real email service (e.g. SES/SendGrid). We don't have one
    wired up in this repo, so "sending" means logging what would have gone
    out -- the important, real part is the URL shape and that it only gets
    sent once per job. Returns the result URL that was "emailed" so callers
    (and GET /api/status, for local testing without a real inbox) can surface
    it too.
    """
    result_url = f"{RESULT_BASE_URL}?job_uuid={job_uuid}"
    print(
        f"[mock email] To: {email}\n"
        f"[mock email] Subject: Your SmartBioPep job is ready\n"
        f"[mock email] Body: Your analysis has finished. View your results: {result_url}"
    )
    return result_url

# -----------------------------------------------------------------------------------------
# REAL RESULT FILES (replaces the random-data mock for summary + sequences)
# -----------------------------------------------------------------------------------------
# This mirrors the JOBS table in the ERD: each job row carries its own
# `output_result_path`, set by the worker once processing finishes. The
# frontend is expected to check that field (via GET /api/status/{job_uuid})
# before asking for results — if it's still null, results aren't ready yet.
#
# We don't have a real worker or a real per-job output directory in this repo
# (there's exactly one sample dataset, Result_Sequence/), so
# _simulate_worker_output_path() below stands in for "the worker finished and
# wrote its output here." Swap that one function for a real lookup (e.g. a
# database read) once jobs actually get their own output directories — every
# other function here already reads through output_result_path, not a
# hardcoded folder, so nothing else needs to change.
SAMPLE_RESULT_DIR = Path(__file__).resolve().parent / "Result_Sequence"

# Matches "RankBioactivity_G1_2Enz", "RankBioactivity_G3a_2Enz", etc.
# group 1 = the numeric part ("1", "3"), group 2 = the optional sub-letter ("", "a", "b")
STAT_FILE_PATTERN = re.compile(r'^RankBioactivity_G(\d+)([a-z]?)(?:_\d+Enz)?$')


def _group_label_from_filename(stem: str) -> Optional[str]:
    """'RankBioactivity_G3a_2Enz' -> 'Group 3a'; returns None if it doesn't match."""
    m = STAT_FILE_PATTERN.match(stem)
    if not m:
        return None
    num, letter = m.groups()
    return f"Group {num}{letter}"


def _simulate_worker_output_path(job_uuid: str) -> str:
    """
    STAND-IN for what a real background worker would do: write results to a
    job-specific directory and persist that path on the job row
    (JOBS.output_result_path in the ERD). We only have one shared sample
    dataset checked into this repo, so every job "completes" pointing at the
    same folder — the mechanism (job -> its own path -> its own files) is
    what's real here, not the data.
    """
    return str(SAMPLE_RESULT_DIR)


def _get_job_output_dir(job_uuid: str) -> Path:
    """
    Resolves JOBS.output_result_path for a job (looked up by job_uuid, the
    API-facing identifier) and validates it, mirroring what a real API would
    do before serving results:
      - 404 if the job doesn't exist at all
      - 409 if the job exists but hasn't finished yet (output_result_path
        is still null) -- this is the "check output_result_path first" gate
        the frontend is expected to respect
      - 500 if the stored path is missing/unreadable on disk (data integrity
        problem -- the DB says results exist, the filesystem disagrees)
    """
    job = mock_jobs_db.get(job_uuid)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    output_path = job.get("output_result_path")
    if not output_path:
        raise HTTPException(
            status_code=409,
            detail="Job results are not ready yet (output_result_path is not set). "
                   "Wait for status to reach SUCCESS before requesting results.",
        )

    resolved = Path(output_path).resolve()
    if not resolved.is_dir():
        raise HTTPException(status_code=500, detail=f"output_result_path does not exist on disk: {output_path}")
    return resolved


# -----------------------------------------------------------------------------------------
# 1. MOCK LOGIN (02_Login.py)
# -----------------------------------------------------------------------------------------
# 02_Login.py posts `data={...}` (form-encoded), so this reads form fields, not a JSON body.
@app.post("/api/login")
def login(username: str = Form(...), password: str = Form(...)):
    if username == "admin" and password == "password":
        return {"access_token": "fake_mock_jwt_token_12345"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

# -----------------------------------------------------------------------------------------
# 2. MOCK UPLOAD & SUBMISSION (03_Data_prep.py)
# -----------------------------------------------------------------------------------------
class AnalyzePayload(BaseModel):
    project_name: str
    sample_name: str
    list_bioactivities_id: list[int]
    fasta_content: str
    # Catch any other fields dynamically
    model_config = {"extra": "allow"}

@app.post("/api/jobs")
def submit_analysis(payload: AnalyzePayload, authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Token")

    # job_uuid is generated HERE now, not by the frontend -- the backend owns
    # the identifier for its own resource, the same way a real DB would hand
    # back a generated primary/unique key on INSERT rather than accepting one
    # from the client. uuid4() is a random UUID; there's no reason for a
    # deterministic/seeded uuid3 anymore since nothing on the frontend needs
    # to predict this value before the job exists (03_Data_prep.py used to
    # build one from username+project+timestamp before this endpoint existed
    # to hand one back).
    job_uuid = str(uuid.uuid4())

    # job_id is a separate, backend-generated internal identifier (DB primary
    # key stand-in) -- returned once here so the frontend can use it for its
    # own project tracking, but it's never used to address an API call.
    # output_result_path mirrors JOBS.output_result_path in the ERD: it stays
    # null until the (simulated) worker finishes and writes results.
    job_id = _next_job_id()
    mock_jobs_db[job_uuid] = {
        "job_id": job_id,
        "status": "running",
        "step_current": 0,
        "output_result_path": None,
    }
    return {"job_id": job_id, "job_uuid": job_uuid, "message": "Job started"}

# -----------------------------------------------------------------------------------------
# 3. MOCK EMAIL NOTIFICATION (04_Job_status.py)
# -----------------------------------------------------------------------------------------
class EmailPayload(BaseModel):
    job_uuid: str
    email: str

@app.post("/api/notifications")
def subscribe_email(payload: EmailPayload, authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Token")
    if payload.job_uuid not in mock_jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")

    # Persisted on the job row so GET /api/status can "send" the completion
    # email itself once the job actually finishes, instead of here (the job
    # has usually barely started at subscribe time).
    mock_jobs_db[payload.job_uuid]["notify_email"] = payload.email
    return {"message": f"Subscribed {payload.email} successfully!"}

# -----------------------------------------------------------------------------------------
# 4. MOCK STATUS POLLING (04_Job_status.py)
# -----------------------------------------------------------------------------------------
@app.get("/api/status/{job_uuid}")
def get_status(job_uuid: str, authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Token")

    if job_uuid not in mock_jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")

    job = mock_jobs_db[job_uuid]

    # Simulate progress: Move forward one step every time Streamlit asks
    if job["step_current"] < len(PIPELINE_STEPS):
        job["step_current"] += 1

    # If it reaches the end, mark it as SUCCESS and (simulating the worker)
    # write the output_result_path that the frontend should now check for.
    if job["step_current"] >= len(PIPELINE_STEPS):
        job["status"] = "SUCCESS"
        if not job.get("output_result_path"):
            job["output_result_path"] = _simulate_worker_output_path(job_uuid)

        # Fire the completion email exactly once, and only if an email was
        # actually subscribed for this job (POST /api/notifications).
        if job.get("notify_email") and not job.get("result_email_sent"):
            job["result_url"] = _send_completion_email(job["notify_email"], job_uuid)
            job["result_email_sent"] = True

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "step_current": job["step_current"],
        "list_step_total": PIPELINE_STEPS,
        "output_result_path": job.get("output_result_path"),  # null until SUCCESS
        "result_url": job.get("result_url"),  # null until the email has gone out
    }

# -----------------------------------------------------------------------------------------
# 5. DASHBOARD RESULTS (05_Dashboard.py) — now reads real files instead of random data
# -----------------------------------------------------------------------------------------
@app.get("/api/results/{job_uuid}/summary")
def get_results_summary(job_uuid: str, authorization: Optional[str] = Header(None)):
    """
    Reads the 4 RankBioactivity_G*_2Enz.csv files (columns: Bioactivity, nPepSeq)
    from THIS job's own output directory (JOBS.output_result_path) and returns
    them as one flat list of {Group, Bioactivity, nPepSeq} records — the exact
    shape 05_Dashboard.py's fetch_summary_data() already expects, so nothing
    on the frontend needs to change for this endpoint's contract.

    Raises 409 via _get_job_output_dir() if the job hasn't finished yet.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Token")

    job_output_dir = _get_job_output_dir(job_uuid)
    stat_files = sorted(job_output_dir.glob("RankBioactivity_*.csv"))
    if not stat_files:
        raise HTTPException(status_code=404, detail="No statistical result files found")

    records = []
    for path in stat_files:
        group_label = _group_label_from_filename(path.stem)
        if group_label is None:
            continue  # skip anything that doesn't match the expected naming pattern

        # encoding="utf-8-sig" strips the leading BOM these files were saved with
        # (otherwise the first column reads as "﻿Bioactivity", not "Bioactivity")
        df = pd.read_csv(path, encoding="utf-8-sig")
        missing = {"Bioactivity", "nPepSeq"} - set(df.columns)
        if missing:
            raise HTTPException(status_code=500, detail=f"{path.name} is missing columns: {sorted(missing)}")

        for _, row in df.iterrows():
            records.append({
                "Group": group_label,
                "Bioactivity": row["Bioactivity"],
                "nPepSeq": int(row["nPepSeq"]),
            })

    return records

@app.get("/api/results/{job_uuid}/download")
def download_sequence_csv(
    job_uuid: str,
    group: str = Query(...),
    bioactivity: str = Query(...),
    authorization: Optional[str] = Header(None),
):
    """
    Returns specific peptide sequences and scores for a given group and bioactivity
    as a downloadable CSV file (matches what 05_Dashboard.py's fetch_sequence_csv expects).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Token")

    # Generate mock sequence rows
    data = [
        {
            "Sequence": "".join(random.choices("ACDEFGHIKLMNPQRSTVWY", k=random.randint(5, 15))),
            "Score": round(random.uniform(0.60, 0.99), 4)
        }
        for _ in range(random.randint(5, 25))
    ]

    df = pd.DataFrame(data)
    csv_content = df.to_csv(index=False)
    return Response(content=csv_content, media_type="text/csv")

if __name__ == "__main__":
    # 0.0.0.0, not 127.0.0.1: inside a container, 127.0.0.1 only accepts
    # connections from within that same container, so the frontend (a
    # different container) would never be able to reach this API even
    # though the port is published/mapped correctly.
    uvicorn.run(app, host="0.0.0.0", port=8000)