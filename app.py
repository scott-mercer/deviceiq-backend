# app.py
from fastapi import FastAPI, UploadFile, File, Query, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
import logging
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
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
    group_by: Optional[str] = Query(None, description="Group devices by 'device_model', 'os_version', or 'os_major_version'"),
    api_key: str = Depends(verify_api_key)
):
    logging.info(f"Received upload: {file.filename} with threshold {coverage_threshold}, group_by={group_by}")
    try:
        content = await file.read()
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
    except Exception as e:
        logging.error(f"Failed to read CSV: {e}")
        raise HTTPException(status_code=400, detail=f"Could not read CSV file: {str(e)}")

    # Validate required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(missing)}"
        )

    # Validate usage_percent is numeric
    if not pd.api.types.is_numeric_dtype(df["usage_percent"]):
        raise HTTPException(
            status_code=400,
            detail="Column 'usage_percent' must be numeric."
        )

    # Add os_major_version if needed for grouping
    if group_by == "os_major_version":
        df["os_major_version"] = df["os_version"].astype(str).str.split(".").str[0]

    # Group if requested
    if group_by in {"device_model", "os_version", "os_major_version"}:
        group_cols = [group_by]
        grouped = df.groupby(group_cols, as_index=False).agg({
            "usage_percent": "sum"
        })
        # Optionally keep a representative os_version or device_model
        if group_by == "device_model" and "os_version" in df.columns:
            grouped["os_version"] = df.groupby(group_by)["os_version"].first().values
        if group_by == "os_major_version" and "device_model" in df.columns:
            grouped["device_model"] = df.groupby("os_major_version")["device_model"].first().values
        df = grouped

    # Greedy selection: sort and include up to threshold
    df = df.sort_values(by='usage_percent', ascending=False)
    df['cumulative_coverage'] = df['usage_percent'].cumsum()
    df['include_in_matrix'] = df['cumulative_coverage'] <= coverage_threshold

    matrix = df[df["include_in_matrix"]][df.columns]

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