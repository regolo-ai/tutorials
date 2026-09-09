"""
REGOLO MCP Security Gate - Static Analysis & Injection Detection Rules
Inspects MCP tool definitions, descriptions, and input schemas for hidden
instructions, zero-width payloads, imperative injections, and exfiltration vectors.
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class Finding:
    rule_id: str
    severity: Severity
    title: str
    description: str
    target_field: str
    line_number: Optional[int]
    line_content: Optional[str]
    matched_text: str
    remediation: str


class RuleEngine:
    """Core security rule engine for static MCP tool inspection."""

    # Zero-width / invisible Unicode characters often used in steganographic prompt injection
    ZERO_WIDTH_CHARS = {
        "\u200B": "Zero-width space (U+200B)",
        "\u200C": "Zero-width non-joiner (U+200C)",
        "\u200D": "Zero-width joiner (U+200D)",
        "\uFEFF": "Byte order mark / zero-width no-break (U+FEFF)",
        "\u2060": "Word joiner (U+2060)",
        "\u200E": "Left-to-right mark (U+200E)",
        "\u200F": "Right-to-left mark (U+200F)",
        "\u202A": "Left-to-right embedding (U+202A)",
        "\u202B": "Right-to-left embedding (U+202B)",
        "\u202D": "Left-to-right override (U+202D)",
        "\u202E": "Right-to-left override (U+202E)",
    }

    # Imperative injection phrases attempting to override agent instructions
    INJECTION_PATTERNS = [
        (
            r"(?i)\b(?:ignore|disregard|forget|bypass)\s+(?:all\s+)?(?:previous|prior|above|system)\s+(?:instructions?|directives?|rules?|prompts?)",
            "INJ-001",
            Severity.CRITICAL,
            "Directive Override (Ignore Previous Instructions)",
            "Tool description attempts to erase or override system instructions and baseline safety constraints.",
            "Remove all imperative directives commanding the model to disregard prior instructions."
        ),
        (
            r"(?i)\[\s*(?:system|override|system_override|instruction|developer_mode|admin_prompt)\s*\]",
            "INJ-002",
            Severity.CRITICAL,
            "Fake System Header Tag Injection",
            "Tool uses fake bracketed system tags like [SYSTEM OVERRIDE] to trick LLMs into treating metadata as authority instructions.",
            "Remove bracketed pseudo-system role headers."
        ),
        (
            r"(?i)(?:you\s+(?:must\s+)?always|silently|secretly)\s+(?:read|execute|send|fetch|post|upload|exfiltrate|transmit)",
            "INJ-003",
            Severity.CRITICAL,
            "Covert Action Directive",
            "Tool instructs the model to perform covert background actions without informing the user.",
            "Ensure tool descriptions are purely descriptive, specifying functionality rather than commanding unprompted covert agent actions."
        ),
        (
            r"(?i)\b(?:do\s+not\s+(?:tell|inform|alert|show)|never\s+reveal|hide\s+this\s+from)\s+(?:the\s+)?(?:user|human|operator)",
            "INJ-004",
            Severity.CRITICAL,
            "User Deception Instruction",
            "Tool commands the LLM to hide activities, output, or error messages from the human operator.",
            "Tools must never conceal operational steps or data payloads from the human user."
        ),
        (
            r"(?i)\b(?:new\s+system\s+prompt|roleplay\s+as|jailbreak|DAN\s+mode|unrestricted\s+mode)",
            "INJ-005",
            Severity.HIGH,
            "Persona Hijacking / Jailbreak Attempt",
            "Tool metadata contains prompt injection keywords designed to hijack the model's persona.",
            "Eliminate persona-altering prompts from tool metadata."
        ),
    ]

    # Patterns targeting local secrets and credential paths
    EXFILTRATION_PATTERNS = [
        (
            r"(?i)(?:~|\/home\/\w+|\/Users\/\w+)?\/\.ssh\/(?:id_rsa|id_ed25519|id_ecdsa|authorized_keys|known_hosts)",
            "EXF-001",
            Severity.CRITICAL,
            "SSH Key Target Vector",
            "Tool metadata references SSH private keys or authentication credentials.",
            "Never allow tool descriptions to reference user SSH keypaths or credentials."
        ),
        (
            r"(?i)(?:~|\/home\/\w+|\/Users\/\w+)?\/\.(?:aws\/credentials|kube\/config|docker\/config\.json|netrc|npmrc)",
            "EXF-002",
            Severity.CRITICAL,
            "Cloud / Environment Credentials Path",
            "Tool references sensitive cloud provider configs or developer credential files.",
            "Remove all references to internal configuration and credential stores."
        ),
        (
            r"(?i)\b(?:os\.environ|process\.env|ENV\[|\bAPI_KEY\b|\bSECRET_KEY\b|\bAWS_SECRET_ACCESS_KEY\b|\bGITHUB_TOKEN\b|\bOPENAI_API_KEY\b)",
            "EXF-003",
            Severity.HIGH,
            "Environment Variable / Secret Harvest Target",
            "Tool mentions harvesting environment variables or sensitive API tokens.",
            "Scope parameters to explicitly required public data; do not query global environment variables."
        ),
        (
            r"(?i)\/etc\/(?:passwd|shadow|hosts|sudoers)",
            "EXF-004",
            Severity.CRITICAL,
            "OS Sensitive Filesystem Path",
            "Tool description mentions core operating system files (/etc/passwd, shadow, etc.).",
            "Remove operating system file references."
        ),
        (
            r"(?i)https?:\/\/(?:webhook\.site|requestbin\.net|pipedream\.net|ngrok\.io|pastebin\.com)\/[a-zA-Z0-9_\-\/]+",
            "EXF-005",
            Severity.HIGH,
            "Known Exfiltration Endpoint",
            "Tool metadata points to a common disposable webhook or payload drop service.",
            "Restrict network destinations to explicitly audited and allowed corporate endpoints."
        ),
    ]

    # Hidden HTML/XML comments and suspicious markup
    MARKUP_PATTERNS = [
        (
            r"<!--[\s\S]*?-->",
            "TAG-001",
            Severity.HIGH,
            "Hidden HTML Comment",
            "HTML comments in tool descriptions can hide instructions from rendered documentation while remaining in the LLM context window.",
            "Remove all HTML comments from tool definitions."
        ),
        (
            r"<\/?(?:system|prompt|instruction|context|command|meta)[^>]*>",
            "TAG-002",
            Severity.HIGH,
            "XML System Prompt Tag Injection",
            "Tool uses XML prompt boundaries like <system> or <instruction> to spoof prompt framing.",
            "Do not use XML prompt control tags inside tool descriptions."
        ),
    ]

    @classmethod
    def analyze_text(cls, text: str, field_name: str) -> List[Finding]:
        """Performs static checks on a string field and tracks line numbers."""
        findings: List[Finding] = []
        if not text or not isinstance(text, str):
            return findings

        lines = text.splitlines()

        # 1. Check for Zero-Width Characters
        for char, char_name in cls.ZERO_WIDTH_CHARS.items():
            if char in text:
                # Find line number
                for line_idx, line in enumerate(lines, start=1):
                    if char in line:
                        findings.append(
                            Finding(
                                rule_id="ZWC-001",
                                severity=Severity.CRITICAL,
                                title="Zero-Width Invisible Characters Detected",
                                description=f"Found invisible Unicode character {char_name}. This is a signature for stealth steganographic prompt injection.",
                                target_field=field_name,
                                line_number=line_idx,
                                line_content=line.replace(char, "[ZERO_WIDTH]"),
                                matched_text=char_name,
                                remediation="Strip all non-printable and zero-width Unicode characters from tool metadata."
                            )
                        )

        # 2. Check Markup Patterns (HTML comments, XML tags)
        for pattern, rule_id, severity, title, desc, remediation in cls.MARKUP_PATTERNS:
            for match in re.finditer(pattern, text):
                matched_str = match.group(0)
                line_idx = text[:match.start()].count("\n") + 1
                line_content = lines[line_idx - 1] if line_idx - 1 < len(lines) else matched_str
                findings.append(
                    Finding(
                        rule_id=rule_id,
                        severity=severity,
                        title=title,
                        description=desc,
                        target_field=field_name,
                        line_number=line_idx,
                        line_content=line_content.strip(),
                        matched_text=matched_str,
                        remediation=remediation
                    )
                )

        # 3. Check Injection Patterns
        for pattern, rule_id, severity, title, desc, remediation in cls.INJECTION_PATTERNS:
            for match in re.finditer(pattern, text):
                matched_str = match.group(0)
                line_idx = text[:match.start()].count("\n") + 1
                line_content = lines[line_idx - 1] if line_idx - 1 < len(lines) else matched_str
                findings.append(
                    Finding(
                        rule_id=rule_id,
                        severity=severity,
                        title=title,
                        description=desc,
                        target_field=field_name,
                        line_number=line_idx,
                        line_content=line_content.strip(),
                        matched_text=matched_str,
                        remediation=remediation
                    )
                )

        # 4. Check Exfiltration Patterns
        for pattern, rule_id, severity, title, desc, remediation in cls.EXFILTRATION_PATTERNS:
            for match in re.finditer(pattern, text):
                matched_str = match.group(0)
                line_idx = text[:match.start()].count("\n") + 1
                line_content = lines[line_idx - 1] if line_idx - 1 < len(lines) else matched_str
                findings.append(
                    Finding(
                        rule_id=rule_id,
                        severity=severity,
                        title=title,
                        description=desc,
                        target_field=field_name,
                        line_number=line_idx,
                        line_content=line_content.strip(),
                        matched_text=matched_str,
                        remediation=remediation
                    )
                )

        # 5. Anomalous length heuristic
        if field_name == "description" and len(text) > 1200:
            findings.append(
                Finding(
                    rule_id="ANO-001",
                    severity=Severity.MEDIUM,
                    title="Anomalous Tool Description Length",
                    description=f"Tool description length is unusually high ({len(text)} characters). Extended descriptions frequently harbor hidden payload instructions.",
                    target_field=field_name,
                    line_number=1,
                    line_content=text[:100] + "...",
                    matched_text=f"{len(text)} chars",
                    remediation="Condense tool description to concise functional specification (under 500 characters)."
                )
            )

        return findings

    @classmethod
    def inspect_tool(cls, tool: Dict[str, Any]) -> List[Finding]:
        """Deeply inspects an entire tool dictionary (name, description, schema)."""
        findings: List[Finding] = []

        # Name inspection
        name = tool.get("name", "")
        findings.extend(cls.analyze_text(name, "name"))

        # Description inspection
        description = tool.get("description", "")
        findings.extend(cls.analyze_text(description, "description"))

        # Schema inspection
        input_schema = tool.get("inputSchema", {})
        if isinstance(input_schema, dict):
            properties = input_schema.get("properties", {})
            if isinstance(properties, dict):
                for prop_name, prop_data in properties.items():
                    if isinstance(prop_data, dict):
                        prop_desc = prop_data.get("description", "")
                        findings.extend(cls.analyze_text(prop_desc, f"inputSchema.properties.{prop_name}.description"))

        return findings
