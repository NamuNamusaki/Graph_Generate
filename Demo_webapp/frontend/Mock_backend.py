from fastapi import FastAPI, Form, Header, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Dict, Optional
import uvicorn
import time
import io
from fastapi.responses import Response
import random
import pandas as pd

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
        "status": "running",
        "step_current": 0
    }
    return {"job_id": payload.job_uuid, "message": "Job started"}

# -----------------------------------------------------------------------------------------
# 3. MOCK EMAIL NOTIFICATION (04_Job_status.py)
# -----------------------------------------------------------------------------------------
class EmailPayload(BaseModel):
    job_uuid: str
    email: str

@app.post("/api/notifications/subscribe")
def subscribe_email(payload: EmailPayload):
    return {"message": f"Subscribed {payload.email} successfully!"}

# -----------------------------------------------------------------------------------------
# 4. MOCK STATUS POLLING (04_Job_status.py)
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
        "list_step_total": PIPELINE_STEPS
    }

# -----------------------------------------------------------------------------------------
# 5. MOCK DASHBOARD RESULTS (05_Dashboard.py)
# -----------------------------------------------------------------------------------------
@app.get("/api/results/{job_id}/summary")
def get_results_summary(job_id: str):
    # Returns dummy data formatted exactly how your dashboard expects it
    data =[]
    groups = ["Group 1", "Group 2", "Group 3a", "Group 3b"]
    bioactivities = ["ACE Inhibitory", "Antimicrobial", "Anti-inflammatory", 
                     "DPP-IV Inhibitory", "Anticancer","Antihypertensive", 
                     "Immunomodulatory", "Antidiabetic","Neuroprotective", "Antiviral"]
    for group in groups:
        selected_bioactivity = random.sample(bioactivities, k=random.randint(5, 10))  # Randomly select 3 bioactivities for each group
        for i in selected_bioactivity:
            data.append({"Group": group, "Bioactivity": i, "nPepSeq": 100})
    df = pd.DataFrame(data)            
    return df.to_dict(orient="records")

@app.get("/api/results/{job_id}/download")
def get_sequence_download(job_id: str, group: str = Query(...), bioactivity: str = Query(...)):
    """
    Returns specific peptide sequences and scores for a given group and bioactivity.
    """
    # Generate mock sequence rows
    data = [
        {
            "Sequence": "".join(random.choices("ACDEFGHIKLMNPQRSTVWY", k=random.randint(5, 15))),
            "Score": round(random.uniform(0.60, 0.99), 4)
        }
        for _ in range(random.randint(5, 25))
    ]
    
    df = pd.DataFrame(data)
    return df.to_dict(orient="records")

@app.get("/api/results/{job_id}/download")
def download_csv(job_id: str, group: str, bioactivity: str):
    csv_content = f"Sequence,Score\nPEPTIDE1,0.99\nPEPTIDE2,0.85\nMock Data for {bioactivity},1.0"
    return Response(content=csv_content, media_type="text/csv")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)