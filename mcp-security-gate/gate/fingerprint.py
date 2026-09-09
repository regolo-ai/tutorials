"""
REGOLO MCP Security Gate - Tool Fingerprinting & Rug-Pull Detection
Computes canonical cryptographic SHA-256 fingerprints of tool schemas and
detects behavioral rug pulls (post-approval modifications to tool definitions).
"""

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FingerprintDiff:
    is_modified: bool
    tool_name: str
    stored_fingerprint: str
    current_fingerprint: str
    field_changes: List[str]
    description_diff: Optional[Tuple[str, str]] = None


class ToolFingerprint:
    """Computes and compares cryptographic hashes of MCP tool schemas."""

    @staticmethod
    def canonicalize(tool: Dict[str, Any]) -> Dict[str, Any]:
        """Produces a deterministic, canonical representation of a tool definition."""
        # Extract core fields that dictate behavior and prompt context
        canonical: Dict[str, Any] = {
            "name": str(tool.get("name", "")).strip(),
            "description": str(tool.get("description", "")).strip(),
        }

        # Normalize inputSchema if present
        input_schema = tool.get("inputSchema")
        if isinstance(input_schema, dict):
            properties = input_schema.get("properties", {})
            norm_props: Dict[str, Any] = {}
            if isinstance(properties, dict):
                for k in sorted(properties.keys()):
                    prop_info = properties[k]
                    if isinstance(prop_info, dict):
                        norm_props[k] = {
                            "type": str(prop_info.get("type", "")),
                            "description": str(prop_info.get("description", "")).strip(),
                        }
            canonical["inputSchema"] = {
                "type": input_schema.get("type", "object"),
                "properties": norm_props,
                "required": sorted(input_schema.get("required", [])),
            }
        else:
            canonical["inputSchema"] = {}

        return canonical

    @classmethod
    def compute_hash(cls, tool: Dict[str, Any]) -> str:
        """Calculates SHA-256 hexadecimal digest of canonical tool dictionary."""
        canonical = cls.canonicalize(tool)
        canonical_bytes = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()

    @classmethod
    def diff(cls, stored_tool: Dict[str, Any], current_tool: Dict[str, Any]) -> FingerprintDiff:
        """Compares approved stored tool with current tool to detect drift / rug pulls."""
        tool_name = current_tool.get("name", stored_tool.get("name", "unknown"))
        hash_stored = cls.compute_hash(stored_tool)
        hash_current = cls.compute_hash(current_tool)

        if hash_stored == hash_current:
            return FingerprintDiff(
                is_modified=False,
                tool_name=tool_name,
                stored_fingerprint=hash_stored,
                current_fingerprint=hash_current,
                field_changes=[],
            )

        changes: List[str] = []
        c_stored = cls.canonicalize(stored_tool)
        c_current = cls.canonicalize(current_tool)

        desc_diff = None
        if c_stored.get("description") != c_current.get("description"):
            changes.append("description altered")
            desc_diff = (c_stored.get("description", ""), c_current.get("description", ""))

        if c_stored.get("name") != c_current.get("name"):
            changes.append("tool name altered")

        schema_stored = c_stored.get("inputSchema", {})
        schema_current = c_current.get("inputSchema", {})
        if schema_stored != schema_current:
            changes.append("input schema / parameters altered")

        return FingerprintDiff(
            is_modified=True,
            tool_name=tool_name,
            stored_fingerprint=hash_stored,
            current_fingerprint=hash_current,
            field_changes=changes,
            description_diff=desc_diff,
        )
