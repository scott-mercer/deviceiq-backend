# app.py
from fastapi import FastAPI, UploadFile, File, Query, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
import logging

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
    api_key: str = Depends(verify_api_key)
):
    logging.info(f"Received upload: {file.filename} with threshold {coverage_threshold}")
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

    return result