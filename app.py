# app.py
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io

app = FastAPI()

# Allow frontend calls from local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload-csv/")
async def upload_csv(file: UploadFile = File(...)):
    content = await file.read()
    df = pd.read_csv(io.StringIO(content.decode("utf-8")))

    df = df.sort_values(by='usage_percent', ascending=False)
    df['cumulative_coverage'] = df['usage_percent'].cumsum()
    df['include_in_matrix'] = df['cumulative_coverage'] <= 90

    matrix = df[df["include_in_matrix"]][["device_model", "os_version", "usage_percent"]]
    return matrix.to_dict(orient="records")