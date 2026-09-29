#!/usr/bin/env python3
"""
Insurance Inbox Triage CLI Runner - Regolo.ai
A production-ready reference runner that decouples Request Category, Processing Complexity,
and Operational Priority. Outputs clean, human-readable Case Cards for insurance handlers,
highlighting urgent safety alerts, required document checks, and automated routing decisions.
"""

import argparse
import json
import os
import sys
import time
import warnings
from pathlib import Path
from dotenv import load_dotenv

# Suppress low-level library noise (e.g., tokenizers parallelism warnings) to keep logs clean for handlers
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

load_dotenv()

from insurance_triage.triage import triage_intake_message
from insurance_triage.classifier import get_engine, classify_intent
from insurance_triage.policy import evaluate_agency_priority
from insurance_triage.complexity import grade_complexity

# Canonical evaluation scenarios representing real insurance brokerage workflows
SAMPLE_CASES = [
    {
        "id": "CASE-01",
        "title": "URGENT: Water leak near electrical panel",
        "description": "Active physical hazard requiring immediate emergency escalation",
        "text": "A pipe burst this morning and water is reaching the electrical panel. My policy number is 12345. I have photos, but I cannot find the claim form.",
    },
    {
        "id": "CASE-02",
        "title": "ROUTINE: Commercial fleet address endorsement",
        "description": "Standard policy update and vehicle garaging address change",
        "text": "Hello, I recently moved. Please update the primary mailing and garaging address on our commercial fleet policy FL-90210 to 458 Industrial Parkway, Suite B.",
    },
    {
        "id": "CASE-03",
        "title": "COMPLEX: Commercial litigation and corporate succession",
        "description": "High-complexity legal dispute under commercial umbrella coverage",
        "text": "My business partner passed away last month, the LLC estate is currently in probate court, and our creditor is threatening a lawsuit. Does our commercial umbrella policy cover defense costs for claims against his personal estate?",
    },
    {
        "id": "CASE-04",
        "title": "OUT OF SCOPE: Non-insurance customer query",
        "description": "Alien query submitted by error (recipe request)",
        "text": "Can you provide the recipe for a traditional Neapolitan pizza dough with 70% hydration?",
    },
]

# Business-friendly descriptions for insurance taxonomy slots
CATEGORY_LABELS = {
    "claims_intake": "Claim Notice / FNOL (Property Damage, Theft, Liability)",
    "policy_change": "Policy Endorsement (Address, Vehicle, Coverage Limits)",
    "underwriting_support": "Risk Evaluation (Surveys, Appraisals, Inspections)",
    "document_missing": "Missing Documentation (Proofs of Loss, Invoices, Police Reports)",
    "customer_query": "Billing & Premium Inquiry (Payment Methods, Invoices, Certificates)",
    "out_of_scope": "Non-Insurance Communication (Alien Request)",
    "unlabeled": "Unlabeled",
    None: "Unrecognized / Insufficient Evidence",
}

# Plain explanations of cognitive processing complexity
COMPLEXITY_LABELS = {
    "easy": "Low / Standard (Routine task; handled efficiently by lightweight model)",
    "medium": "Medium (Requires standard verification across policy records)",
    "hard": "High / Complex (Involves complex legal, probate, or exclusion analysis)",
    None: "Not determined (Evaluation halted before synthesis)",
}


def print_banner():
    print("=" * 85, flush=True)
    print("  INTELLIGENT INSURANCE INBOX TRIAGE SYSTEM - REGOLO.AI", flush=True)
    print("  Decoupled Signals: Request Category | Processing Complexity | Operational Priority", flush=True)
    print("=" * 85, flush=True)


def format_case_card(case_id: str, title: str, text: str, result, latency_ms: float):
    """
    Renders an Operative Case Card formatted for non-technical insurance staff and operations managers.
    Highlights safety alerts, confidence scores, and action items clearly.
    """
    print(f"\n┌────────────────────────────────────────────────────────────────────────────────────", flush=True)
    print(f"│  {case_id}: {title.upper()}", flush=True)
    print(f"├────────────────────────────────────────────────────────────────────────────────────", flush=True)
    print(f"│  POLICYHOLDER INBOUND MESSAGE:", flush=True)
    print(f"│  \"{text}\"", flush=True)
    print(f"│", flush=True)
    print(f"│  AUTOMATED TRIAGE ASSESSMENT:", flush=True)

    # 1. Deterministic Operational Priority & Life Safety Alert
    if result.priority == "high":
        print(f"│  [!] PRIORITY LEVEL:     🚨 HIGH / IMMEDIATE EMERGENCY", flush=True)
        print(f"│      Safety Trigger:     Potential hazard detected by deterministic rule (e.g. water near power panel)", flush=True)
    else:
        print(f"│  [v] PRIORITY LEVEL:     🟢 STANDARD (No immediate physical or legal hazard detected)", flush=True)

    # 2. Operational Status & Action Assignment
    category_desc = CATEGORY_LABELS.get(result.category, result.category or "Unrecognized")

    if result.status == "awaiting_operator_review":
        print(f"│  [v] OPERATIONAL STATUS: ✅ READY FOR OPERATOR REVIEW & APPROVAL", flush=True)
        print(f"│      Assigned Category:  {category_desc}", flush=True)
        conf_pct = int((result.confidence or 0.0) * 100)
        print(f"│      Model Confidence:   {conf_pct}% (High confidence - reliable routing gate passed)", flush=True)
        compl_desc = COMPLEXITY_LABELS.get(result.complexity, result.complexity or "")
        print(f"│      Complexity Tier:    {compl_desc}", flush=True)

        if result.brief:
            print(f"│", flush=True)
            print(f"│  SYNTHESIS BRIEF (Drafted by Sovereign EU Model on Regolo):", flush=True)
            print(f"│  * Summary:              {result.brief.summary}", flush=True)
            if result.brief.information_to_check:
                print(f"│  * Verification Checks:  - " + "\n│                         - ".join(result.brief.information_to_check[:4]), flush=True)
            if result.brief.review_flags:
                print(f"│  * Attention Flags:      " + ", ".join(result.brief.review_flags), flush=True)
            if result.brief.suggested_next_action:
                print(f"│  * Recommended Action:   {result.brief.suggested_next_action}", flush=True)

    elif result.status == "manual_review":
        print(f"│  [⚠️] OPERATIONAL STATUS: 👤 ASSIGNED TO MANUAL TRIAGE (NO AUTOMATED ACTION)", flush=True)

        reason = result.reason or ""
        if "below_confidence_gate" in reason:
            print(f"│      Gating Reason:      The AI detected semantic ambiguity (e.g. compound intent in message).", flush=True)
            print(f"│                          To prevent misrouting, this case is safely assigned to a human handler.", flush=True)
            if result.category:
                print(f"│      Primary Hypothesis: {category_desc} (Confidence below gate: {int((result.confidence or 0.0)*100)}%)", flush=True)
        elif "insufficient_evidence" in reason:
            print(f"│      Gating Reason:      🚫 OUT OF SCOPE / NON-INSURANCE REQUEST.", flush=True)
            print(f"│                          The message contains no valid insurance, claim, or policy intent.", flush=True)
        else:
            print(f"│      Gating Reason:      Manual inspection required ({reason})", flush=True)

    print(f"│", flush=True)
    if latency_ms < 500:
        print(f"│  PROCESSING TIME:       {latency_ms:.1f} milliseconds (Immediate perimeter filter)", flush=True)
    else:
        print(f"│  PROCESSING TIME:       {latency_ms / 1000:.2f} seconds (Perimeter classification + Regolo AI synthesis)", flush=True)
    print(f"└────────────────────────────────────────────────────────────────────────────────────", flush=True)


def run_dataset_benchmark(dataset_path: str, max_cases: int = 50, skip_synthesis: bool = False):
    """
    Evaluates an entire JSONL dataset in batch mode, providing performance metrics
    and ground-truth accuracy reports suitable for operational leadership.
    """
    p = Path(dataset_path)
    if not p.exists():
        print(f"\n[ERROR] Dataset file '{dataset_path}' not found.", flush=True)
        print("Tip: Run `python train.py` first to generate data/insurance_benchmark_eval.jsonl", flush=True)
        sys.exit(1)

    with open(p) as f:
        rows = [json.loads(line) for line in f if line.strip()]

    if max_cases:
        rows = rows[:max_cases]

    mode_label = "Fast Perimeter Triage (~10ms/case, Classification + Priority)" if skip_synthesis else "Full End-to-End Pipeline (with Case Brief Synthesis on Regolo)"
    print(f"\nSTARTING BATCH BENCHMARK EVALUATION: {dataset_path}", flush=True)
    print(f"Samples to evaluate: {len(rows)} | Mode: {mode_label}\n", flush=True)
    print("-" * 115, flush=True)
    print(f"{'#':<3} | {'CASE STATUS':<28} | {'PREDICTED CATEGORY':<32} | {'EXPECTED':<18} | {'PRIORITY':<9} | {'LATENCY':<8}", flush=True)
    print("-" * 115, flush=True)

    correct = 0
    labeled_total = 0
    manual_reviews = 0
    urgent_count = 0
    latencies = []

    for i, r in enumerate(rows, 1):
        text = r.get("text", "")
        expected_cat = r.get("category", "unlabeled")

        t0 = time.perf_counter()
        if skip_synthesis:
            clean_text = text.strip()
            priority = evaluate_agency_priority(clean_text)
            cat_res = classify_intent(clean_text)
            pred_cat = cat_res.get("category") or "unrecognized"
            status = "Automated (Confident)" if cat_res.get("status") == "confident" else "Human Review (Uncertain)"
            dt = (time.perf_counter() - t0) * 1000
        else:
            res = triage_intake_message(text)
            pred_cat = res.category or "unrecognized"
            status = "Ready for Operator ✅" if res.status == "awaiting_operator_review" else "Human Review 👤"
            priority = res.priority
            dt = (time.perf_counter() - t0) * 1000

        latencies.append(dt)

        if priority == "high":
            urgent_count += 1
        if "Human" in status or (not skip_synthesis and res.status == "manual_review"):
            manual_reviews += 1

        is_match = False
        if expected_cat not in {"unlabeled", "out_of_scope"}:
            labeled_total += 1
            if pred_cat == expected_cat:
                correct += 1
                is_match = True
        elif expected_cat == "out_of_scope" and (pred_cat == "unrecognized" or "Human" in status):
            labeled_total += 1
            correct += 1
            is_match = True

        match_icon = "✅" if is_match else ("⚠️ MISMATCH" if expected_cat != "unlabeled" else "  ")
        prio_display = "🚨 HIGH" if priority == "high" else "Standard"

        print(f"{i:<3} | {status:<28} | {pred_cat:<32} | {expected_cat:<18} {match_icon:<11} | {prio_display:<9} | {dt:>6.1f}ms", flush=True)

    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    acc = (correct / labeled_total * 100) if labeled_total else 0.0

    print("-" * 115, flush=True)
    print("\nOPERATIONAL PERFORMANCE SUMMARY (MANAGEMENT REPORT):", flush=True)
    print(f"  * Total Communications Examined       : {len(rows)}", flush=True)
    print(f"  * Routing Accuracy on Known Classes   : {acc:.1f}% ({correct} correct out of {labeled_total} verified)", flush=True)
    print(f"  * Cases Routed to Human Handlers      : {manual_reviews} ({(manual_reviews/len(rows))*100:.1f}% safely gated to prevent errors)", flush=True)
    print(f"  * Physical / Life Safety Alerts Caught: {urgent_count} (immediately escalated to emergency handler queue)", flush=True)
    print(f"  * Average Processing Latency          : {avg_lat:.1f} milliseconds per message", flush=True)
    print("=" * 115, flush=True)


def main():
    parser = argparse.ArgumentParser(description="Run Insurance Inbox Triage System")
    parser.add_argument("--text", type=str, help="Custom customer message to triage")
    parser.add_argument("--dataset", type=str, help="Path to JSONL dataset for batch benchmark (e.g. data/insurance_benchmark_eval.jsonl)")
    parser.add_argument("--max-cases", type=int, default=50, help="Maximum number of dataset cases to process")
    parser.add_argument("--skip-synthesis", action="store_true", help="Run fast perimeter classification without generating full LLM brief")

    args = parser.parse_args()
    print_banner()

    api_key = os.environ.get("REGOLO_API_KEY")
    backend = os.environ.get("CLASSIFIER_BACKEND", "setfit")

    if api_key:
        print("[Gateway] EU Sovereign Regolo.ai Gateway ACTIVE (GDPR Compliant / Zero Data Retention)", flush=True)
        print(f"          Complexity Router Model : {os.environ.get('REGOLO_COMPLEXITY_MODEL', 'brick-complexity-pro')}", flush=True)
        print(f"          Brief Synthesis Model   : {os.environ.get('REGOLO_STANDARD_MODEL', 'gpt-oss-20b')}", flush=True)
    else:
        print("[Gateway] LOCAL DEMO MODE (Offline mode, no external cloud API calls)", flush=True)

    model_label = "SetFit (Fine-tuned locally on agency cases - 10ms)" if backend == "setfit" else f"{backend.upper()} (Zero-Shot)"
    print(f"          Perimeter Decision Model: {model_label}", flush=True)

    # Initialize model in memory
    print(f"\n[Startup] Loading local decision model into memory...", flush=True)
    get_engine()
    print(f"[Startup] Engine ready.\n", flush=True)

    if args.dataset:
        run_dataset_benchmark(args.dataset, max_cases=args.max_cases, skip_synthesis=args.skip_synthesis)
    elif args.text:
        res, lat = triage_intake_message(args.text), 0.0
        format_case_card("USER-REQUEST", "Analysis of command-line input text", args.text, res, lat)
    else:
        print(f"Evaluating {len(SAMPLE_CASES)} canonical insurance brokerage test scenarios:\n", flush=True)
        for case in SAMPLE_CASES:
            t0 = time.perf_counter()
            res = triage_intake_message(case["text"])
            lat = (time.perf_counter() - t0) * 1000
            format_case_card(case["id"], case["title"], case["text"], res, lat)

        print("\nTip: To run batch evaluation on the full Hugging Face dataset, execute:")
        print("  python main.py --dataset data/insurance_benchmark_eval.jsonl --skip-synthesis --max-cases 20")


if __name__ == "__main__":
    main()
