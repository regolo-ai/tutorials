# File Storage Microservice

Microservice handling document uploads and downloads.

## Current Open Issue #12:
- **Title**: `Security Vulnerability: Fix Directory Traversal in /files/download and restrict upload extensions`
- **Description**: Security penetration test discovered that `/files/download` accepts `../../` sequences leading to arbitrary file exposure (CWE-22). Additionally, `/files/upload` permits uploads of executable formats without validation (CWE-434).
- **Target**: Sanitize filenames with `Path(filename).name`, ensure target path resides strictly inside `uploads/`, and restrict uploads to allowed extensions (`.pdf`, `.png`, `.jpg`, `.txt`, `.csv`).
