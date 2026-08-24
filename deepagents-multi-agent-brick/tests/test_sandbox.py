"""Tests for Sandbox Environment Manager."""

import pytest
from core.sandbox import SandboxEnvironment
import config


def test_sandbox_lifecycle():
    sample_path = config.SAMPLE_REPOS_DIR / "ai_tool_nexus"
    sandbox = SandboxEnvironment(source_repo_path=str(sample_path))

    files = sandbox.list_files()
    assert len(files) > 0

    # Test write file
    sandbox.write_file("test_artifact.txt", "Hello Deep Agents")
    read_content = sandbox.read_file("test_artifact.txt")
    assert read_content == "Hello Deep Agents"

    # Test diff
    diff = sandbox.compute_diff()
    assert "test_artifact.txt" in diff

    # Cleanup
    sandbox.cleanup()
    assert not sandbox.sandbox_path.exists()
