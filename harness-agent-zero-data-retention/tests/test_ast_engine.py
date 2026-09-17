import tempfile
from pathlib import Path
import pytest

from regolo_agent_stack.ast_engine import (
    parse_diff_modified_lines,
    extract_called_symbols_from_diff,
    extract_enclosing_scopes,
    extract_file_ast_skeleton,
    build_project_symbol_index,
    resolve_targeted_skeletons,
    find_associated_tests,
)

SAMPLE_DIFF = """diff --git a/app/controllers.py b/app/controllers.py
index 1111111..2222222 100644
--- a/app/controllers.py
+++ b/app/controllers.py
@@ -10,3 +10,4 @@ def handle_request():
     user = get_user()
-    return user.is_valid()
+    auth = AuthService()
+    return auth.verify_session(user.id)
"""

def test_parse_diff_modified_lines():
    line_map = parse_diff_modified_lines(SAMPLE_DIFF)
    assert "app/controllers.py" in line_map
    # Lines 11 and 12 were added
    assert 11 in line_map["app/controllers.py"]
    assert 12 in line_map["app/controllers.py"]

def test_extract_called_symbols_from_diff():
    symbols = extract_called_symbols_from_diff(SAMPLE_DIFF)
    assert "AuthService" in symbols
    assert "verify_session" in symbols

def test_extract_enclosing_scopes(tmp_path):
    source_code = (
        "import os\n\n"
        "def unrelated_func():\n"
        "    return 42\n\n"
        "class Controller:\n"
        "    def __init__(self):\n"
        "        self.active = True\n\n"
        "    def handle_request(self, user_id: str) -> bool:\n"
        "        # line 10\n"
        "        # line 11 (modified line)\n"
        "        return True\n"
    )
    f = tmp_path / "controller.py"
    f.write_text(source_code, encoding="utf-8")

    # Modified line is 11
    scope = extract_enclosing_scopes(f, {11})
    assert "def handle_request" in scope
    assert "user_id: str" in scope
    # Unrelated function should not be in the enclosing scope
    assert "def unrelated_func" not in scope

def test_extract_file_ast_skeleton(tmp_path):
    code = (
        "class SessionManager:\n"
        "    def __init__(self, ttl: int = 3600):\n"
        "        self.ttl = ttl\n"
        "        self._cache = {}\n"
        "    def is_valid(self, token: str) -> bool:\n"
        "        # complex body\n"
        "        return token in self._cache\n\n"
        "def generate_token(length: int = 32) -> str:\n"
        "    return 'xyz'\n"
    )
    f = tmp_path / "session.py"
    f.write_text(code, encoding="utf-8")

    skeletons = extract_file_ast_skeleton(f)
    assert "SessionManager" in skeletons
    assert "class SessionManager:" in skeletons["SessionManager"]
    assert "def is_valid(self, token: str) -> bool: ..." in skeletons["SessionManager"]
    assert "generate_token" in skeletons
    assert "def generate_token(length: int) -> str: ..." in skeletons["generate_token"]

def test_resolve_targeted_skeletons_cross_file(tmp_path):
    # Setup project with two files: controller.py and auth_service.py
    auth_file = tmp_path / "auth_service.py"
    auth_file.write_text(
        "class AuthService:\n"
        "    def verify_session(self, user_id: str) -> bool:\n"
        "        # 100 lines of implementation\n"
        "        return True\n",
        encoding="utf-8"
    )

    diff = (
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -5,1 +5,2 @@\n"
        "+    auth = AuthService()\n"
        "+    return auth.verify_session('u123')\n"
    )

    targeted = resolve_targeted_skeletons(
        repo_root=tmp_path,
        diff_text=diff,
        modified_files=["app.py"]
    )
    assert "auth_service.py" in targeted
    assert "class AuthService:" in targeted
    assert "def verify_session" in targeted

def test_find_associated_tests(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)

    test_file = tests_dir / "test_auth.py"
    test_file.write_text(
        "def test_verify_session_success():\n"
        "    '''Checks valid session.'''\n"
        "    assert True\n\n"
        "def test_verify_session_expired():\n"
        "    '''Checks expired session.'''\n"
        "    assert True\n",
        encoding="utf-8"
    )

    contracts = find_associated_tests(
        repo_root=tmp_path,
        modified_files=["auth.py"]
    )
    assert "test_auth.py" in contracts
    assert "def test_verify_session_success(): ..." in contracts
    assert "Checks valid session." in contracts
