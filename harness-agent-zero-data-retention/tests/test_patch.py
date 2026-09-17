from regolo_agent_stack.patch import parse_unified_diff, extract_patch_for_file

def test_parse_diff():
    diff = "diff --git a/foo.py b/foo.py\n--- a/foo.py\n+++ b/foo.py\n@@ -1,2 +1,3 @@\n line1\n+line2\n"
    parsed = parse_unified_diff(diff)
    assert "foo.py" in parsed
