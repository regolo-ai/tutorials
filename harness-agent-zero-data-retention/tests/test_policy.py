from regolo_agent_stack.policy import redact_text, filter_files, scan_for_secrets
from pathlib import Path

def test_redact():
    text = "key=sk_live_abcdefghijklmnopqrstuvwx"
    assert "sk_live_" not in redact_text(text)

def test_filter_files():
    files = [Path(".env"), Path("src/main.py")]
    assert filter_files(files) == [Path("src/main.py")]
