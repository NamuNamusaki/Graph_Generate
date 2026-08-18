"""
    auth.py       -- real authentication: bcrypt password hashing, signed
                     session tokens, and the get_current_user dependency.
    helper.py     -- real logic: FASTA validation, job-id formatting,
                     reading result files off disk.
    stimulate.py  -- simulated logic: mock pipeline progress, mock
                     completion emails.

Endpoints (everything except /login needs a valid token):
    POST /login                        -- authenticate, returns a session token
    POST /logout                       -- invalidate the current token
    GET  /me                           -- who am I? (token check)
    POST /jobs                         -- submit a new analysis job
    POST /notifications                -- subscribe an email to a job
    GET  /jobs/{job_uuid}              -- poll job status/progress
    GET  /jobs/{job_uuid}/result       -- job statistics for the Dashboard
    GET  /jobs/{job_uuid}/download     -- one bioactivity's peptide CSV

There is one account, defined in .env (APP_USERNAME/APP_PASSWORD) and seeded
into MySQL at startup -- there is no public registration. See auth.py.

Every /jobs/* route is still scoped to the calling user: another user's job
responds 404, exactly as if it didn't exist. With one account that check
always passes, but it's kept so per-user isolation already works the day a
second account exists.
"""
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, Form, HTTPException, Query
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

import auth
import db
import helper
import stimulate

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once when the API starts: make sure the .env account exists in
    MySQL (creating it, or updating its password, as needed)."""
    auth.ensure_app_user()
    yield

app = FastAPI(title="SmartBioPep Frontend API", lifespan=lifespan)

# -----------------------------------------------------------------------------------------
# SHARED
# -----------------------------------------------------------------------------------------
def get_owned_job_or_404(job_uuid: str, current_user: dict) -> dict:
    """
    Fetches a job by uuid, but only if it belongs to the calling user.
    Returns 404 (not 403) for someone else's job on purpose: a 403 would
    confirm that job_uuid exists, letting an attacker map out real jobs.
    "Not yours" and "doesn't exist" should look identical.
    """
    row = db.get_job_by_uuid(job_uuid)
    if row is None or row.get("owner_user_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Job not found")
    return row

# -----------------------------------------------------------------------------------------
# REQUEST MODELS
# -----------------------------------------------------------------------------------------
class AnalyzePayload(BaseModel):
    project_name: str
    sample_name: Optional[str] = None
    list_bioactivities_id: list[int]
    fasta_content: str
    # Accept the other form fields (organism, enzyme_id, miss, description,
    # ml_models_id) without declaring each one -- they're stored as-is.
    model_config = {"extra": "allow"}

class EmailPayload(BaseModel):
    job_uuid: str
    email: str

# -----------------------------------------------------------------------------------------
# 1. AUTHENTICATION (web_ui/pages/02_Login.py)
# -----------------------------------------------------------------------------------------
@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    """
    Verifies credentials against the users table and returns a session token.

    02_Login.py posts form-encoded fields, so this reads Form(), not JSON.
    The response keeps the same `access_token` key the UI already expects --
    only the token itself changed, from a fixed string everyone shared to a
    fresh random one issued per login.
    """
    user = auth.authenticate_user(username, password)
    token = auth.create_access_token(user["id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"],
    }

@app.post("/logout")
def logout(credentials: HTTPAuthorizationCredentials = Depends(auth.bearer_scheme)):
    """
    Invalidates the caller's token so it stops working immediately.

    Takes the raw credentials rather than get_current_user because we need
    the token string itself, not the user it maps to.
    """
    if credentials and credentials.credentials:
        auth.revoke_access_token(credentials.credentials)
    return {"message": "Logged out"}


@app.get("/me")
def read_current_user(current_user: dict = Depends(auth.get_current_user)):
    """Returns the logged-in user -- lets the UI check whether a stored
    token is still valid."""
    return current_user

# -----------------------------------------------------------------------------------------
# 2. UPLOAD & SUBMISSION (web_ui/pages/03_Data_prep.py)
# -----------------------------------------------------------------------------------------
@app.post("/jobs")
def submit_analysis(
    payload: AnalyzePayload,
    current_user: dict = Depends(auth.get_current_user),
):
    """
    Creates a project + job row for a new submission and returns the two
    identifiers the frontend needs: job_id (display label) and job_uuid
    (used by every subsequent call). The project is owned by the logged-in
    user, which is what makes the ownership checks elsewhere work.
    """
    fasta_errors = helper.validate_fasta_content(payload.fasta_content)
    if fasta_errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Invalid FASTA input", "errors": fasta_errors},
        )

    job_uuid = str(uuid.uuid4())
    extra_fields = payload.model_dump()

    project_id = db.create_project(
        current_user["id"],
        project_name=payload.project_name,
        description=extra_fields.get("description"),
    )

    extra_params = {
        "organism": extra_fields.get("organism"),
        "enzyme_id": extra_fields.get("enzyme_id"),
        "miss": extra_fields.get("miss"),
        "sample_name": payload.sample_name,
    }

    db.create_job(
        job_uuid,
        project_id,
        input_fasta_path=None,
        list_bioactivity_id=payload.list_bioactivities_id,
        list_step_total=stimulate.PIPELINE_STEPS,
        extra_params=extra_params,
    )

    db.update_job_progress(job_uuid, status="RUNNING", started_at_now=True)

    row = db.get_job_by_uuid(job_uuid)
    return {
        "job_id": helper.format_job_id(row["id"]),
        "job_uuid": job_uuid,
        "message": "Job started",
    }

# -----------------------------------------------------------------------------------------
# 3. EMAIL NOTIFICATION (web_ui/pages/04_Job_status.py)
# -----------------------------------------------------------------------------------------
@app.post("/notifications")
def subscribe_email(
    payload: EmailPayload,
    current_user: dict = Depends(auth.get_current_user),
):
    """
    Subscribes an email address to this job's completion notice.
    Defaults to the account's own email.
    """
    get_owned_job_or_404(payload.job_uuid, current_user)

    email = payload.email or current_user.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="No email address given or on file.")

    stimulate.subscribe_notification(payload.job_uuid, email)
    return {"message": f"Subscribed {email} successfully!"}


# -----------------------------------------------------------------------------------------
# 4. STATUS POLLING (web_ui/pages/04_Job_status.py)
# -----------------------------------------------------------------------------------------
@app.get("/jobs/{job_uuid}")
def get_status(job_uuid: str, current_user: dict = Depends(auth.get_current_user)):
    """
    Returns this job's current progress. Because there's no real worker yet,
    each call also advances the simulated pipeline by one step (see
    stimulate.mock_job_progress).
    """
    row = get_owned_job_or_404(job_uuid, current_user)

    status, step_current, output_result_path = stimulate.mock_job_progress(row)
    result_url = stimulate.notify_subscriber(job_uuid)

    return {
        "job_id": helper.format_job_id(row["id"]),
        "status": status,
        "step_current": step_current,
        "list_step_total": row["list_step_total"] or stimulate.PIPELINE_STEPS,
        "output_result_path": output_result_path,  # null until COMPLETED
        "result_url": result_url,  # null until the email has gone out
    }

# -----------------------------------------------------------------------------------------
# 5. JOB RESULT -- statistics only (web_ui/pages/05_Dashboard.py)
# -----------------------------------------------------------------------------------------
@app.get("/jobs/{job_uuid}/result")
def get_job_result(job_uuid: str, current_user: dict = Depends(auth.get_current_user)):
    # Statistical summary for the Dashboard's charts and tables. Does NOT include peptide sequences
    row = get_owned_job_or_404(job_uuid, current_user)

    return {
        "job_id": helper.format_job_id(row["id"]),
        "status": row["status"],
        "error_message": row["error_message"],
        "stat_files": helper.read_stat_files(row["output_result_path"]),
        "extra_params": row.get("extra_params") or {},
    }

# -----------------------------------------------------------------------------------------
# 6. SEQUENCE DOWNLOAD -- one bioactivity, on demand (web_ui/pages/05_Dashboard.py)
# -----------------------------------------------------------------------------------------
@app.get("/jobs/{job_uuid}/download")
def download_sequence_file(
    job_uuid: str,
    group: str = Query(..., description='e.g. "Group 1", "Group 3a"'),
    bioactivity: str = Query(..., description='e.g. "ACE_inhibitor" -- raw name, matching the CSV filename'),
    current_user: dict = Depends(auth.get_current_user),
):
    row = get_owned_job_or_404(job_uuid, current_user)

    path = helper.resolve_sequence_file(row["output_result_path"], group, bioactivity)
    return Response(content=path.read_text(encoding="utf-8-sig"), media_type="text/csv")


if __name__ == "__main__":
    # 0.0.0.0, not 127.0.0.1: inside a container, 127.0.0.1 only accepts
    # connections from within that same container, so the web_ui container
    # could never reach this API even with the port published correctly.
    uvicorn.run(app, host="0.0.0.0", port=8000)
