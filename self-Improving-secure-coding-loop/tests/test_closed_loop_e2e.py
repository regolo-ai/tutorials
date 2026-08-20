"""End-to-End integration test for full closed-loop pipeline across multiple vulnerability classes."""

import pytest
import config
from core.regolo_client import RegoloClient
from core.cognee_memory import CogneeMemoryGraph
from core.open_swe import OpenSWEAgent
from core.deepsec import DeepsecSecurityHarness
from core.sandbox import SandboxEnvironment
from core.brick_governance import get_telemetry_summary, clear_telemetry


@pytest.mark.parametrize("repo_dir,issue_title,issue_body", [
    ("auth_service", "Fix SQL Injection & Insecure JWT Signature", "CWE-89 in search and CWE-287 in verify"),
    ("webhook_gateway", "Mitigate Blind SSRF & Command Injection", "CWE-918 in dispatch and CWE-78 in ping"),
    ("ecommerce_cart", "Resolve IDOR & Price Tampering", "CWE-639 in orders and CWE-20 in checkout"),
    ("file_storage_service", "Fix Path Traversal & File Upload", "CWE-22 in download and CWE-434 in upload"),
    ("analytics_query_engine", "Eliminate eval() RCE & pickle Deserialization", "CWE-94 in calculate and CWE-502 in cache load"),
    ("crypto_wallet_service", "Remove Hardcoded Secret & Enforce CSPRNG", "CWE-798 master key and CWE-338 random"),
    ("user_profile_api", "Prevent Stored XSS & Mass Assignment", "CWE-79 in card and CWE-915 in update"),
])
def test_full_closed_loop_pipeline(repo_dir, issue_title, issue_body):
    clear_telemetry()
    client = RegoloClient()
    memory = CogneeMemoryGraph()
    swe_agent = OpenSWEAgent(client=client, memory=memory)
    deepsec = DeepsecSecurityHarness(client=client)

    target_repo = config.SAMPLE_REPOS_DIR / repo_dir
    sandbox = SandboxEnvironment(source_repo_path=str(target_repo))

    try:
        # 1. Deepsec initial scan
        initial_scan = deepsec.run_security_scan(sandbox)
        assert len(initial_scan["findings"]) >= 1, f"Expected initial findings in {repo_dir}"

        # 2. Open SWE Plan
        analysis = swe_agent.analyze_and_plan(
            sandbox=sandbox,
            issue_title=issue_title,
            issue_body=issue_body,
        )
        assert "plan" in analysis
        assert "steps" in analysis["plan"]

        # 3. Open SWE Execute Remediation
        remediation = swe_agent.execute_remediation(
            sandbox=sandbox,
            issue_title=issue_title,
            plan_data=analysis["plan"],
        )
        assert len(remediation["modified_files"]) >= 1
        assert len(remediation["diff"]) > 0
        assert remediation["test_passed"] is True, f"Unit tests failed for {repo_dir}: {remediation['test_output']}"

        # 4. Deepsec Revalidation
        reval = deepsec.revalidate_patch(sandbox, initial_scan["findings"])
        assert reval["revalidation_passed"] is True
        assert len(reval["residual_findings"]) == 0
        assert reval["security_score"] >= 90

        # 5. Cognee Memory update
        learning = memory.record_learning(
            issue_id=f"ISSUE-{repo_dir}",
            issue_title=issue_title,
            files_modified=remediation["modified_files"],
            vulnerabilities_fixed=[f["title"] for f in initial_scan["findings"]],
            fix_summary=remediation["remediation_summary"],
            test_passed=remediation["test_passed"],
            human_decision="APPROVED",
            pattern_learned=f"Remediated {repo_dir} with verified tests",
        )
        assert learning["id"] in memory.nodes

        # 6. Brick Telemetry check
        telemetry = get_telemetry_summary()
        assert telemetry["total_tokens"] > 0
        assert telemetry["savings_percentage"] > 0

    finally:
        sandbox.cleanup()
