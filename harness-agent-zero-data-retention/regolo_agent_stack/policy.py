import re
from pathlib import Path
from typing import Iterable

DEFAULT_SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk_live_[0-9a-zA-Z]{24,}"),
    re.compile(r"ghp_[0-9a-zA-Z]{36}"),
    re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"),
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)token\s*[:=]\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)password\s*[:=]\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)secret\s*[:=]\s*['\"][^'\"]+['\"]"),
]

DEFAULT_IGNORE_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
]

def _is_ignored(path: Path, patterns: Iterable[str]) -> bool:
    name = path.name
    rel = str(path)
    for pat in patterns:
        if pat.startswith("*."):
            if name.endswith(pat[2:]):
                return True
        elif pat.endswith("*"):
            prefix = pat[:-1]
            if rel.startswith(prefix):
                return True
        else:
            if pat in rel:
                return True
    return False

def redact_text(text: str, patterns=None) -> str:
    patterns = patterns or DEFAULT_SECRET_PATTERNS
    redacted = text
    for pat in patterns:
        redacted = pat.sub("[REDACTED]", redacted)
    return redacted

def filter_files(files, ignore_patterns=None) -> list[Path]:
    ignore_patterns = ignore_patterns or DEFAULT_IGNORE_PATTERNS
    return [p for p in files if not _is_ignored(p, ignore_patterns)]

def scan_for_secrets(text: str, patterns=None) -> list[str]:
    patterns = patterns or DEFAULT_SECRET_PATTERNS
    hits = []
    for pat in patterns:
        for match in pat.finditer(text):
            hits.append(match.group(0))
    return hits
