"""Unit tests for Sandbox Environment Manager."""

import config
from core.sandbox import SandboxEnvironment


def test_sandbox_lifecycle():
    auth_repo = config.SAMPLE_REPOS_DIR / "auth_service"
    sandbox = SandboxEnvironment(source_repo_path=str(auth_repo))

    try:
        files = sandbox.list_files()
        assert "app.py" in files

        # Read original
        content = sandbox.read_file("app.py")
        assert "FastAPI" in content

        # Modify file
        sandbox.write_file("app.py", content + "\n# Sandbox comment test")
        diff = sandbox.generate_diff()
        assert "+# Sandbox comment test" in diff

    finally:
        sandbox.cleanup()
