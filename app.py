# app.py
from fastapi import FastAPI, UploadFile, File, Query, HTTPException, Depends, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
import logging
import sys
import json
from prometheus_fastapi_instrumentator import Instrumentator
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
import os
from dotenv import load_dotenv
from typing import Optional
import asyncio

# Load environment variables from .env file
load_dotenv()

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

app = FastAPI()

# Allow frontend calls from local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = "your-secret-api-key"  # Change this to a secure value

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")

REQUIRED_COLUMNS = {"device_model", "os_version", "usage_percent"}

@app.post("/upload-csv/")
async def upload_csv(
    file: UploadFile = File(...),
    coverage_threshold: float = Query(90, ge=0, le=100, description="Cumulative coverage threshold (0-100)"),
    api_key: str = Depends(verify_api_key)
):
    logging.info(f"Received upload: {file.filename} with threshold {coverage_threshold}")
    try:
        content = await file.read()
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
    except Exception as e:
        logging.error(f"Failed to read CSV: {e}")
        sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=400, detail=f"Could not read CSV file: {str(e)}")

    # Validate required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        msg = f"Missing required columns: {', '.join(missing)}"
        logging.error(msg)
        sentry_sdk.capture_message(msg)
        raise HTTPException(status_code=400, detail=msg)

    # Validate usage_percent is numeric
    if not pd.api.types.is_numeric_dtype(df["usage_percent"]):
        msg = "Column 'usage_percent' must be numeric."
        logging.error(msg)
        sentry_sdk.capture_message(msg)
        raise HTTPException(status_code=400, detail=msg)

    df = df.sort_values(by='usage_percent', ascending=False)
    df['cumulative_coverage'] = df['usage_percent'].cumsum()
    df['include_in_matrix'] = df['cumulative_coverage'] <= coverage_threshold

    matrix = df[df["include_in_matrix"]][["device_model", "os_version", "usage_percent", "cumulative_coverage"]]

    # Summary statistics
    total_devices = len(df)
    included_devices = len(matrix)
    total_usage = df["usage_percent"].sum()
    covered_usage = matrix["usage_percent"].sum()

    result = {
        "matrix": matrix.to_dict(orient="records"),
        "summary": {
            "total_devices": total_devices,
            "included_devices": included_devices,
            "total_usage_percent": round(total_usage, 2),
            "covered_usage_percent": round(covered_usage, 2),
        }
    }

    logging.info(f"Processed upload: {file.filename} | Included: {included_devices}/{total_devices} | Covered usage: {covered_usage:.2f}%")
    return result

@app.post("/analytics/")
async def analytics(
    file: UploadFile = File(...),
    group_by: Optional[str] = Query(None, description="Group devices by 'device_model', 'os_version', or 'os_major_version'"),
    api_key: str = Depends(verify_api_key)
):
    try:
        content = await file.read()
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
    except Exception as e:
        logging.error(f"Failed to read CSV: {e}")
        raise HTTPException(status_code=400, detail=f"Could not read CSV file: {str(e)}")

    # Add os_major_version if needed
    if group_by == "os_major_version":
        df["os_major_version"] = df["os_version"].astype(str).str.split(".").str[0]

    # Group if requested
    if group_by in {"device_model", "os_version", "os_major_version"}:
        group_cols = [group_by]
        grouped = df.groupby(group_cols, as_index=False).agg({
            "usage_percent": "sum"
        })
        df = grouped

    # Device/OS usage distribution
    usage_distribution = df.sort_values(by='usage_percent', ascending=False).to_dict(orient="records")

    # Cumulative coverage curve
    df_sorted = df.sort_values(by='usage_percent', ascending=False)
    df_sorted['cumulative_coverage'] = df_sorted['usage_percent'].cumsum()
    cumulative_curve = df_sorted[['device_model', 'os_version', 'usage_percent', 'cumulative_coverage']].to_dict(orient="records")

    # OS version breakdown
    os_version_breakdown = df.groupby('os_version', as_index=False)['usage_percent'].sum().sort_values(by='usage_percent', ascending=False).to_dict(orient="records")

    return {
        "usage_distribution": usage_distribution,
        "cumulative_curve": cumulative_curve,
        "os_version_breakdown": os_version_breakdown
    }

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Use a custom logger for structured logs to avoid uvicorn.access formatting issues
    logger = logging.getLogger("deviceiq")
    logger.info(json.dumps({
        "event": "request",
        "method": request.method,
        "url": str(request.url)
    }))
    response = await call_next(request)
    logger.info(json.dumps({
        "event": "response",
        "status_code": response.status_code,
        "url": str(request.url)
    }))
    return response

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    try:
        # Example: Replace this with your Appium log process
        # For now, we simulate log streaming with dummy data
        for i in range(100):
            log_line = f"Appium log line {i}"
            device_info = {"device_id": "emulator-5554", "status": "active"}
            await websocket.send_json({"log": log_line, "device": device_info})
            await asyncio.sleep(0.5)  # Simulate log arrival
    except WebSocketDisconnect:
        logging.info("WebSocket disconnected")
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        await websocket.close()

# Prometheus metrics endpoint
Instrumentator().instrument(app).expose(app)

# Sentry error monitoring with logging integration
SENTRY_DSN = os.getenv("SENTRY_DSN")

sentry_logging = LoggingIntegration(
    level=logging.INFO,
    event_level=logging.WARNING
)
sentry_sdk.init(
    dsn=SENTRY_DSN,
    integrations=[sentry_logging],
    traces_sample_rate=1.0
)