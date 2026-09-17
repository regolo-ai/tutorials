import subprocess
from pathlib import Path

from regolo_agent_stack.context import select_staged_context

def test_no_diff(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    ctx = select_staged_context(tmp_path)
    assert ctx["diff"] == ""
    assert ctx["files"] == []
