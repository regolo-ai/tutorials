from langchain_core.documents import Document

POLICY_DOCUMENTS = [
    Document(page_content="Activation rate is activated workspaces divided by signed-up workspaces. A workspace is activated after its first data source is connected and its first dashboard is viewed. Compare complete calendar weeks only.", metadata={"source": "metrics_glossary.md"}),
    Document(page_content="When activation falls by more than 5 percentage points week over week, investigate by plan and acquisition channel. Escalate only after checking sample size and tracking changes.", metadata={"source": "growth_playbook.md"}),
    Document(page_content="CRM action policy: creating a follow-up list is allowed. Sending messages, changing an account owner, or changing CRM records requires explicit human approval outside this assistant.", metadata={"source": "crm_policy.md"}),
]
