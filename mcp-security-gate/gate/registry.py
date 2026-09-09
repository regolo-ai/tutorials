"""
REGOLO MCP Security Gate - Approved Tools Registry & Version Locking
Enforces supply chain version locking, prevents stealth updates (rug pulls),
and maintains an immutable record of verified and audited MCP tools.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .fingerprint import FingerprintDiff, ToolFingerprint


class ToolStatus(str, Enum):
    APPROVED = "APPROVED"
    REVOKED = "REVOKED"
    FLAGGED = "FLAGGED"
    UNAPPROVED = "UNAPPROVED"


class VerificationResult(str, Enum):
    VALID = "VALID"
    NEW_TOOL = "NEW_TOOL"
    RUG_PULL = "RUG_PULL"
    REVOKED = "REVOKED"


@dataclass
class ApprovedRecord:
    tool_name: str
    server_name: str
    version: str
    fingerprint: str
    approved_at: str
    approved_by: str
    status: ToolStatus
    canonical_schema: Dict[str, Any]


class Registry:
    """Manages the vetted MCP tool registry and version lockfile."""

    DEFAULT_PATH = Path(".mcp-gate/registry.json")

    def __init__(self, registry_path: Optional[Path] = None):
        self.path = registry_path or self.DEFAULT_PATH
        self.records: Dict[str, ApprovedRecord] = {}
        self.load()

    def load(self) -> None:
        """Loads registry from disk."""
        if not self.path.exists():
            self.records = {}
            return

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.records = {}
                for key, val in data.get("tools", {}).items():
                    self.records[key] = ApprovedRecord(
                        tool_name=val["tool_name"],
                        server_name=val.get("server_name", "default"),
                        version=val.get("version", "1.0.0"),
                        fingerprint=val["fingerprint"],
                        approved_at=val.get("approved_at", ""),
                        approved_by=val.get("approved_by", "admin"),
                        status=ToolStatus(val.get("status", ToolStatus.APPROVED)),
                        canonical_schema=val.get("canonical_schema", {}),
                    )
        except Exception as e:
            self.records = {}

    def save(self) -> None:
        """Persists registry to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "tools": {
                k: {
                    "tool_name": r.tool_name,
                    "server_name": r.server_name,
                    "version": r.version,
                    "fingerprint": r.fingerprint,
                    "approved_at": r.approved_at,
                    "approved_by": r.approved_by,
                    "status": r.status.value,
                    "canonical_schema": r.canonical_schema,
                }
                for k, r in self.records.items()
            },
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def get_tool_key(self, server_name: str, tool_name: str) -> str:
        return f"{server_name}:{tool_name}"

    def approve_tool(
        self,
        tool: Dict[str, Any],
        server_name: str = "default",
        version: str = "1.0.0",
        approved_by: str = "developer",
    ) -> ApprovedRecord:
        """Adds or updates a verified tool in the approved registry."""
        tool_name = tool.get("name", "unnamed")
        key = self.get_tool_key(server_name, tool_name)
        fingerprint = ToolFingerprint.compute_hash(tool)
        canonical = ToolFingerprint.canonicalize(tool)

        record = ApprovedRecord(
            tool_name=tool_name,
            server_name=server_name,
            version=version,
            fingerprint=fingerprint,
            approved_at=datetime.now(timezone.utc).isoformat(),
            approved_by=approved_by,
            status=ToolStatus.APPROVED,
            canonical_schema=canonical,
        )
        self.records[key] = record
        self.save()
        return record

    def revoke_tool(self, server_name: str, tool_name: str) -> bool:
        """Revokes an approved tool."""
        key = self.get_tool_key(server_name, tool_name)
        if key in self.records:
            self.records[key].status = ToolStatus.REVOKED
            self.save()
            return True
        return False

    def verify_tool(
        self,
        tool: Dict[str, Any],
        server_name: str = "default",
    ) -> Tuple[VerificationResult, Optional[FingerprintDiff], Optional[ApprovedRecord]]:
        """
        Verifies a tool definition against the registry.
        Detects unapproved tools, revocations, and rug-pull modifications.
        """
        tool_name = tool.get("name", "unnamed")
        key = self.get_tool_key(server_name, tool_name)

        if key not in self.records:
            # Check if same tool name exists under any server
            matching_keys = [k for k in self.records if k.endswith(f":{tool_name}")]
            if not matching_keys:
                return VerificationResult.NEW_TOOL, None, None
            key = matching_keys[0]

        record = self.records[key]

        if record.status == ToolStatus.REVOKED:
            return VerificationResult.REVOKED, None, record

        # Check fingerprint match
        diff = ToolFingerprint.diff(record.canonical_schema, tool)
        if diff.is_modified:
            return VerificationResult.RUG_PULL, diff, record

        return VerificationResult.VALID, diff, record

    def export_lockfile(self, lockfile_path: Path = Path("mcp-lock.json")) -> None:
        """Exports an immutable mcp-lock.json for CI and pre-commit verification."""
        current_tools = {
            k: {
                "tool": r.tool_name,
                "server": r.server_name,
                "version": r.version,
                "sha256": r.fingerprint,
                "status": r.status.value,
            }
            for k, r in self.records.items()
            if r.status == ToolStatus.APPROVED
        }

        generated_at = datetime.now(timezone.utc).isoformat()
        if lockfile_path.exists():
            try:
                with open(lockfile_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    if existing.get("tools") == current_tools:
                        generated_at = existing.get("generated_at", generated_at)
            except Exception:
                pass

        lock_data = {
            "$schema": "https://regolo.ai/schemas/mcp-lock-v1.json",
            "generated_at": generated_at,
            "tools": current_tools,
        }
        with open(lockfile_path, "w", encoding="utf-8") as f:
            json.dump(lock_data, f, indent=2)
