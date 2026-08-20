"""Vulnerable Cloud Object & File Storage Service (Demo Target).
Contains:
1. Path Traversal (CWE-22) in `/files/download` via unsanitized filename input
2. Unrestricted File Upload & Missing Extension Whitelisting (CWE-434) in `/files/upload`
"""

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse

app = FastAPI(title="FileStorage API", version="1.0.0")

BASE_STORAGE_DIR = Path(__file__).resolve().parent / "uploads"
BASE_STORAGE_DIR.mkdir(exist_ok=True, parents=True)

# Create a sample public file
(BASE_STORAGE_DIR / "sample.txt").write_text("Hello from public storage!", encoding="utf-8")


@app.get("/files/download")
def download_file(filename: str = Query(..., description="Target file name")):
    """Download stored document by filename.
    CRITICAL SECURITY VULNERABILITY: Path Traversal (CWE-22) allowing arbitrary system file reading (e.g. `../../etc/passwd`).
    """
    # VULNERABLE CODE: Direct os.path.join allows relative path traversal (../)
    file_path = os.path.join(str(BASE_STORAGE_DIR), filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)


@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload user file into storage.
    HIGH SECURITY VULNERABILITY: Unrestricted File Upload (CWE-434) allowing arbitrary extensions (.py, .sh, .exe, .html).
    """
    # VULNERABLE CODE: No file extension or mime-type validation
    dest_path = BASE_STORAGE_DIR / file.filename
    content = await file.read()
    dest_path.write_bytes(content)

    return {"filename": file.filename, "size_bytes": len(content), "status": "uploaded"}
