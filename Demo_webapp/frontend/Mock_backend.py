from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
import uvicorn
import time
import io
from fastapi.responses import Response

app = FastAPI()

# -----------------------------------------------------------------------------------------
# MOCK DATABASE FOR JOB TRACKING
# -----------------------------------------------------------------------------------------
# We use this to simulate a job moving from PENDING -> PROCESSING -> SUCCESS
mock_jobs_db = {}
PIPELINE_STEPS = ["Reading Data", "In silico Digestion", "Bioactivity Matching", "Generating Results"]

# -----------------------------------------------------------------------------------------
# 1. MOCK LOGIN (02_Login.py)
# -----------------------------------------------------------------------------------------
class LoginPayload(BaseModel):
    username: str
    password: str

@app.post("/api/login")
def login(payload: LoginPayload):
    if payload.username == "admin" and payload.password == "password":
        return {"access_token": "fake_mock_jwt_token_12345"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

# -----------------------------------------------------------------------------------------
# 2. MOCK UPLOAD & SUBMISSION (03_Upload.py)
# -----------------------------------------------------------------------------------------
class AnalyzePayload(BaseModel):
    job_uuid: str
    project_name: str
    sample_name: str
    list_bioactivity_id: list[int]
    fasta_content: str
    # Catch any other fields dynamically
    model_config = {"extra": "allow"} 

@app.post("/api/jobs")
def submit_analysis(payload: AnalyzePayload, authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Token")
    
    # Register the new job in our mock database starting at step 0
    mock_jobs_db[payload.job_uuid] = {
        "status": "PROCESSING",
        "step_current": 0
    }
    return {"job_id": payload.job_uuid, "message": "Job started"}

# -----------------------------------------------------------------------------------------
# 3. MOCK EMAIL NOTIFICATION (04_Waiting.py)
# -----------------------------------------------------------------------------------------
class EmailPayload(BaseModel):
    job_uuid: str
    email: str

@app.post("/api/notifications/subscribe")
def subscribe_email(payload: EmailPayload):
    return {"message": f"Subscribed {payload.email} successfully!"}

# -----------------------------------------------------------------------------------------
# 4. MOCK STATUS POLLING (04_Waiting.py)
# -----------------------------------------------------------------------------------------
@app.get("/api/status/{job_id}")
def get_status(job_id: str):
    if job_id not in mock_jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = mock_jobs_db[job_id]
    
    # Simulate progress: Move forward one step every time Streamlit asks
    if job["step_current"] < len(PIPELINE_STEPS):
        job["step_current"] += 1
        
    # If it reaches the end, mark it as SUCCESS
    if job["step_current"] >= len(PIPELINE_STEPS):
        job["status"] = "SUCCESS"
        
    return {
        "status": job["status"],
        "step_current": job["step_current"],
        "step_total_list": PIPELINE_STEPS
    }

# -----------------------------------------------------------------------------------------
# 5. MOCK DASHBOARD RESULTS (05_Dashboard.py)
# -----------------------------------------------------------------------------------------
@app.get("/api/results/{job_id}/summary")
def get_results_summary(job_id: str):
    # Returns dummy data formatted exactly how your dashboard expects it
    return {
        "Group 1": [
            {"Bioactivity": "ACE Inhibitory", "nPepSeq": 450},
            {"Bioactivity": "Antioxidant", "nPepSeq": 120},
            {"Bioactivity": "Antimicrobial", "nPepSeq": 85}
        ],
        "Group 2": [
            {"Bioactivity": "ACE Inhibitory", "nPepSeq": 200},
            {"Bioactivity": "Anti-inflammatory", "nPepSeq": 90}
        ]
    }

@app.get("/api/results/{job_id}/download")
def download_csv(job_id: str, group: str, bioactivity: str):
    csv_content = f"Sequence,Score\nPEPTIDE1,0.99\nPEPTIDE2,0.85\nMock Data for {bioactivity},1.0"
    return Response(content=csv_content, media_type="text/csv")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)