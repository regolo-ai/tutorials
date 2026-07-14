# Enterprise Code Review Architecture

## Overview

This architecture defines an enterprise-grade Code Review system that combines semantic codebase retrieval, reranking, deterministic verification, isolated execution, and persistent learning. Qdrant is used as the retrieval and indexing layer for code, diffs, technical documents, and historical review artifacts, while Qwen3-Reranker-4B is used as a second-stage reranker to improve context precision before the main reviewer model is invoked.[cite:64][cite:65][cite:66]

The system is designed around a simple principle: the reviewer model should never operate on raw repository scale if a narrower, better context can be assembled first. Qdrant handles broad candidate recall through vector and payload indexing, and the reranker compresses those candidates into the highest-value context window for the review agent.[cite:64][cite:66]

## Design goals

The system is optimized for five enterprise goals: review quality, auditability, operational safety, cost control, and organizational learning. Review quality improves when the model sees the right code and documentation instead of a large but noisy context; auditability improves when each retrieval, rerank, review, verification step, and decision is persisted as structured output.[cite:64][cite:66]

Operational safety requires verification boundaries beyond natural-language reasoning. For this reason, deterministic checks and optionally isolated runtime execution sit after the model step, not before it, and every state transition is persisted so a reviewer, security engineer, or platform owner can reconstruct what happened during a review run.[cite:66]

## High-level architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│                         ENTERPRISE CODE REVIEW                      │
└──────────────────────────────────────────────────────────────────────┘

  [1] SCM / PR Event / IDE Request
                  │
                  ▼
  ┌────────────────────────────────┐
  │ Review Orchestrator            │
  │ - request normalization        │
  │ - policy lookup                │
  │ - workflow state               │
  └───────────────┬────────────────┘
                  │
                  ├──────────────────────────────┐
                  ▼                              ▼
  ┌──────────────────────────────┐   ┌──────────────────────────────┐
  │ Retrieval Layer              │   │ Operational Store            │
  │ Qdrant                       │   │ review runs / state / costs │
  │ - code chunks                │   │ approvals / artifacts       │
  │ - docs / ADRs / runbooks     │   └──────────────────────────────┘
  │ - prior reviews / lessons    │
  └───────────────┬──────────────┘
                  │ top-k candidates
                  ▼
  ┌──────────────────────────────┐
  │ Rerank Layer                 │
  │ Qwen3-Reranker-4B            │
  │ - candidate scoring          │
  │ - context compression        │
  └───────────────┬──────────────┘
                  │ top-n context
                  ▼
  ┌──────────────────────────────┐
  │ Reviewer Model               │
  │ - issue detection            │
  │ - comment generation         │
  │ - optional fix proposal      │
  └───────────────┬──────────────┘
                  │
                  ▼
  ┌──────────────────────────────┐
  │ Verification Pipeline        │
  │ - parse / compile / lint     │
  │ - tests / SAST / policy      │
  │ - semantic checker           │
  └───────────────┬──────────────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
  PASS / advisory      FAIL / blocked / retry
        │                   │
        └─────────┬─────────┘
                  ▼
  ┌──────────────────────────────┐
  │ Feedback & Knowledge Update  │
  │ - persist outcomes           │
  │ - update review memory       │
  │ - propose doc changes        │
  └──────────────────────────────┘
```

## Core components

### 1. Review Orchestrator

The Review Orchestrator is the control plane of the system. It receives events from pull requests, merge requests, CLI tools, or IDE integrations, normalizes the request, computes policy context, selects the correct workflow, and persists the run state in an operational store.[cite:66]

This component should remain deterministic and policy-driven. It decides whether the review is advisory-only, verification-backed, or autofix-enabled, and it enforces limits on cost, timeout, branch scope, and approval requirements before any model call happens.[cite:66]

### 2. Codebase indexing with Qdrant

Qdrant is the semantic memory layer for the system. It stores code chunks, symbol-level fragments, API contracts, architecture decision records, runbooks, troubleshooting guides, postmortems, accepted patches, rejected patches, and prior review outcomes as searchable vectors with structured payload metadata.[cite:64][cite:71]

Qdrant supports both vector indexes and payload indexes. This is critical because enterprise code review queries are not only semantic; they also need structured filters such as repository, tenant, path, branch, language, symbol type, owner team, service name, review status, or document type.[cite:64]

### 3. Second-stage reranking with Qwen3-Reranker-4B

Qwen3-Reranker-4B should be used after initial retrieval, not instead of retrieval. Regolo’s rerank documentation explicitly positions reranking as a second-stage step that takes previously retrieved candidates and reorders them by relevance to the task, which is exactly the right pattern for code review.[cite:66]

This design improves precision when the initial Qdrant recall returns many plausible chunks from the same service or repository. The reranker can prioritize the best implementation examples, the closest prior bug patterns, the most relevant ADR, and the exact coding standard sections to include in the review context.[cite:65][cite:66]

### 4. Reviewer model

The reviewer model receives a compressed, high-value context package instead of raw repository content. Its responsibilities are to analyze the diff, detect likely defects, identify architectural or policy violations, generate review comments, and optionally produce a candidate fix or patch proposal.[cite:66]

The reviewer should not be treated as the final authority. In an enterprise system, its output is a proposal that must pass downstream verification boundaries before it is allowed to mark an issue as confirmed or to generate an auto-remediation path.[cite:66]

### 5. Verification pipeline

The verification pipeline converts model suggestions into evidence-backed results. Depending on the language and repository type, this layer can include AST parsing, compilation, linting, type checking, unit tests, dependency checks, SAST scanning, license policy validation, and an independent semantic checker.[cite:66]

This is the main difference between an AI comment generator and an enterprise review system. The system must be able to label findings as speculative, verified, blocked, or safe-to-apply based on observable execution results rather than on model confidence alone.[cite:66]

### 6. Knowledge and feedback layer

Every completed review should create two kinds of persistence: operational history and reusable knowledge. Operational history stores workflow state, timing, model usage, retrieved document IDs, rerank scores, verification logs, sandbox artifacts, and final disposition; reusable knowledge stores normalized bug patterns, accepted fixes, rejected suggestions, reviewer notes, and technical documentation updates that can influence future retrieval and review quality.[cite:64][cite:66]

This is the feedback loop that connects code review with engineering memory. Over time, the system stops behaving like a stateless assistant and starts behaving like a review platform that remembers what the organization already learned.[cite:64]

## Retrieval and context selection flow

The retrieval flow should be staged. A single wide-context prompt is the wrong design because it wastes tokens and increases irrelevance. The better pattern is recall first, precision second, generation third.[cite:64][cite:66]

```text
1. Receive PR/MR event with changed files and metadata
2. Build query package:
   - diff summary
   - touched paths
   - language
   - service / team / repo / branch
   - issue labels and policies
3. Query Qdrant with vector search + payload filters
4. Return top-k candidates from code, docs, ADRs, prior reviews
5. Pass candidates to Qwen3-Reranker-4B
6. Select top-n reranked context items
7. Assemble prompt package for reviewer model
8. Generate review comments and optional fix proposals
9. Send findings into verification pipeline
```

The main retrieval collections should be separated logically even if the underlying Qdrant deployment is shared. Typical collections are `code_chunks`, `tech_docs`, `adr_records`, `review_memory`, and `incident_knowledge`, each with embeddings plus payload metadata designed for filtering and routing.[cite:64][cite:71]

## Recommended Qdrant payload schema

Qdrant indexing works best when payload indexes are created for fields that will be used in filters. Qdrant documents this explicitly and recommends creating payload indexes before importing points when filtered search performance matters.[cite:64]

| Field | Type | Purpose |
|---|---|---|
| `tenant_id` | keyword / uuid | multi-tenant isolation [cite:64] |
| `repo_id` | keyword | repository filter [cite:64] |
| `branch` | keyword | branch-scoped review context [cite:64] |
| `commit_sha` | keyword | traceability to source revision |
| `path` | text / keyword | file path filtering and search [cite:64] |
| `language` | keyword | language-specific routing [cite:64] |
| `symbol` | text | function/class/module context |
| `owner_team` | keyword | ownership-aware retrieval [cite:64] |
| `doc_type` | keyword | ADR, runbook, style guide, postmortem [cite:64] |
| `service_name` | keyword | service-level retrieval [cite:64] |
| `review_outcome` | keyword | accepted / rejected / false positive memory |
| `updated_at` | datetime | freshness ranking [cite:64] |
| `source_kind` | keyword | code, doc, review, incident |

## Persistence model

The persistence model should use two stores rather than overloading the vector database. Qdrant is the right place for semantic memory and rerankable knowledge artifacts, but workflow state, retries, approvals, idempotency keys, and compliance audit trails belong in a transactional operational store.[cite:64][cite:71]

A practical split is shown below.

| Store | Purpose |
|---|---|
| Operational database | review runs, queue state, locks, approvals, costs, model calls, verification results |
| Object storage | sandbox logs, test artifacts, build reports, diff bundles |
| Qdrant | semantic memory for code, docs, review outcomes, approved fixes, incidents [cite:64][cite:71] |

This separation keeps the system easier to scale and audit. The operational database governs workflow correctness, while Qdrant improves future retrieval quality and institutional memory.[cite:64]

## Feedback loop between review and technical documentation

The feedback loop should be explicit rather than incidental. A review that finds a recurring issue should not end as a one-off PR comment; it should create a candidate knowledge artifact that can be approved and published back into the organization’s technical memory.[cite:64]

The recommended flow is:

```text
Review outcome -> normalize finding -> classify pattern -> persist evidence ->
propose knowledge update -> human approval if needed -> publish to docs ->
re-embed -> re-index in Qdrant -> available for future reviews
```

Examples include updating coding standards after repeated concurrency bugs, adding a runbook note after a deployment-related failure pattern, or inserting a new ADR summary after an architectural anti-pattern is detected across multiple reviews. Because Qdrant is already storing technical documentation and prior review memory, those updates become immediately available for future retrieval once re-indexed.[cite:64]

## Sandbox evaluation

A sandbox is not always required, but it is strongly recommended for any workflow that executes code, runs tests, compiles artifacts, or evaluates third-party dependencies. The risk is not only malicious code; even trusted internal code can consume excessive CPU, memory, disk, or network resources, or can behave nondeterministically when run in the shared control plane.[cite:66]

The decision should be based on execution depth.

| Review mode | Sandbox requirement | Rationale |
|---|---|---|
| Static-only review | Optional | No execution, mainly retrieval + generation + policy checks |
| Parse / lint / compile | Recommended | Isolates toolchain and filesystem side effects |
| Unit / integration tests | Required | Runs untrusted repository code and dependencies |
| Autofix with verification | Required | Needs strong rollback, reproducibility, and containment |

### Recommended sandbox design

The minimum enterprise-safe design is a per-review isolated container or microVM with an ephemeral filesystem, non-root user, resource quotas, network disabled by default, short execution timeouts, and a tightly controlled list of mounted inputs and allowed tools. If the system runs customer code, external contributions, or code from multiple business units, a stronger isolation layer such as microVMs is preferable to plain shared containers.[cite:66]

A good sandbox contract is:

```text
Input:
- checked-out repository snapshot
- selected diff / branch / commit metadata
- allowed toolchain image
- execution policy

Output:
- compile / lint / test results
- logs and artifacts
- resource usage metrics
- normalized verification verdict
```

The sandbox should never have implicit write access back to the source of truth. Deployment, patch application, or pull request commenting should happen only through the orchestrator after the verification result has been collected and policy checks have passed.[cite:66]

## End-to-end workflow

```text
1. PR/MR or IDE action triggers review request
2. Orchestrator normalizes request and policy context
3. Code and docs retrieved from Qdrant using vector search + payload filters
4. Qwen3-Reranker-4B reranks candidates for precise context selection
5. Reviewer model generates findings and optional fix proposals
6. Verification pipeline validates findings with deterministic checks
7. If execution is required, sandbox runs compile/test/lint in isolation
8. Final verdict is persisted in operational store
9. Approved knowledge updates are written to docs / review memory
10. Updated artifacts are embedded and re-indexed in Qdrant
```

This architecture creates a closed loop between code review, verification, and organizational memory. The system becomes more valuable over time because every verified review outcome can improve future retrieval, reduce repeated false positives, and enrich technical documentation at the point where engineers need it.[cite:64][cite:66]

## Implementation priorities

The recommended rollout order is deliberate. Start with repository ingestion, Qdrant retrieval, reranking, and advisory review comments; then add deterministic verification; then add sandboxed execution; and only after those controls are stable should autofix or auto-apply features be introduced.[cite:64][cite:66]

A practical implementation sequence is:

1. Build Qdrant ingestion for code and docs.[cite:64]
2. Add filtered retrieval on PR events.[cite:64]
3. Insert Qwen3-Reranker-4B before the reviewer call.[cite:65][cite:66]
4. Persist review context, scores, and outputs.
5. Add compile/lint/test verification.
6. Add sandbox isolation for executable checks.
7. Add feedback publishing into documentation and review memory.
8. Add approval-gated autofix for narrow classes of defects.

## Recommended decision

The recommended enterprise design is to combine Qdrant for codebase and documentation retrieval, Qwen3-Reranker-4B for second-stage context precision, a reviewer model for issue generation, a verification layer for deterministic evidence, and a sandbox for all executable validation paths. This architecture minimizes irrelevant context, improves review quality, strengthens auditability, and creates a durable feedback loop between reviews and technical documentation.[cite:64][cite:65][cite:66]
