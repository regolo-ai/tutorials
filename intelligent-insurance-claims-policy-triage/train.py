#!/usr/bin/env python3
"""
Local Training Script for Insurance Claims & Policy Triage using SetFit.
Extracts and maps real insurance customer messages from Hugging Face:
'bitext/Bitext-insurance-llm-chatbot-training-dataset'
into our 5 canonical operational categories, trains in under 1 minute on CPU,
and saves the trained model to models/setfit-insurance-triage.
"""

import json
import os
import random
from collections import defaultdict
from pathlib import Path

from datasets import Dataset, load_dataset
from setfit import SetFitModel, Trainer, TrainingArguments
from sklearn.metrics import classification_report, accuracy_score

# Canonical categories and their integer IDs
CATEGORIES = [
    "claims_intake",
    "policy_change",
    "underwriting_support",
    "document_missing",
    "customer_query",
]
LABEL2ID = {cat: i for i, cat in enumerate(CATEGORIES)}
ID2LABEL = {i: cat for i, cat in enumerate(CATEGORIES)}

# Mapping from Bitext dataset intents to our 5 canonical categories
INTENT_MAPPING = {
    # 1. Claims Intake
    "file_claim": "claims_intake",
    "report_incident": "claims_intake",
    "track_claim": "claims_intake",
    "appeal_denied_insurance_claim": "claims_intake",
    "accept_settlement": "claims_intake",
    "negotiate_settlement": "claims_intake",
    "reject_settlement": "claims_intake",

    # 2. Policy Endorsements & Changes
    "change_personal_details": "policy_change",
    "change_coverage": "policy_change",
    "upgrade_coverage": "policy_change",
    "downgrade_coverage": "policy_change",
    "renew_insurance_policy": "policy_change",
    "cancel_insurance_policy": "policy_change",

    # 3. Underwriting Support & Risk Evaluation
    "calculate_insurance_quote": "underwriting_support",
    "buy_insurance_policy": "underwriting_support",
    "check_coverage": "underwriting_support",
    "compare_insurance_policies": "underwriting_support",

    # 4. Customer Queries & Billing
    "check_payments": "customer_query",
    "payment_methods": "customer_query",
    "pay": "customer_query",
    "receive_payment": "customer_query",
    "report_payment_issue": "customer_query",
    "schedule_payments": "customer_query",
    "dispute_invoice": "customer_query",
    "cancellation_fees": "customer_query",
    "general_information": "customer_query",
    "information_auto_insurance": "customer_query",
    "information_home_insurance": "customer_query",
    "information_life_insurance": "customer_query",
    "check_rates": "customer_query",
}

# Domain-specific synthetic enrichment for missing documents and complex claims
DOMAIN_SUPPLEMENT = [
    # Document missing examples
    ("I am attaching the official police report for the vehicle collision last Tuesday. Policy 99214.", "document_missing"),
    ("Please find attached the signed proof of loss statement and repair invoice from the certified contractor.", "document_missing"),
    ("Here are the photos of the water damage and the plumber invoice. Can you confirm if you received them?", "document_missing"),
    ("Following up on my open claim: you requested my driver license and medical bill copies, here they are.", "document_missing"),
    ("I have sent the property inspection report and appraisal certificate requested by your claims adjuster.", "document_missing"),
    ("Attaching the itemized receipts for the stolen jewelry and electronics as requested for claim CL-4019.", "document_missing"),
    ("Can you confirm whether my signed release form has been logged into the file?", "document_missing"),
    ("I cannot find the original claim form on your portal, where should I upload my damage photos?", "document_missing"),

    # Complex claims intake examples
    ("A pipe burst this morning and water is reaching the electrical panel. My policy number is 12345. I have photos.", "claims_intake"),
    ("A tree fell on our garage roof during the hail storm, punctured the shingles, and caused a leak.", "claims_intake"),
    ("Our delivery van was involved in a three-car highway pileup this afternoon. Driver is at the hospital.", "claims_intake"),
    ("Our kitchen had a major grease fire, the sprinkler system deployed and damaged the wood floors.", "claims_intake"),
    ("Someone broke into our commercial warehouse over the weekend and stole three pallet jacks and power tools.", "claims_intake"),
    ("A client slipped on our icy entrance steps and broke their wrist, threatening legal action for medical costs.", "claims_intake"),

    # Routine policy changes
    ("Hello, I recently moved. Please update the primary mailing and garaging address on our fleet policy FL-90210.", "policy_change"),
    ("We purchased a new 2026 Ford Transit van and need to add it to our commercial auto insurance immediately.", "policy_change"),
    ("Please increase our general commercial liability limit from 1 million to 2 million dollars for contract compliance.", "policy_change"),
    ("I need to remove an ex-employee from the designated authorized drivers list on policy POL-3312.", "policy_change"),

    # Underwriting support
    ("Submitting the commercial building risk survey and fire alarm certification requested for renewal review.", "underwriting_support"),
    ("Here is the updated audited revenue statement and payroll breakdown for our annual workers comp audit.", "underwriting_support"),
    ("Please find the geotechnical engineer soil inspection report required before binding the builders risk binder.", "underwriting_support"),

    # Customer billing query
    ("Why was my monthly premium billed twice on the 15th? Please check the payment statement.", "customer_query"),
    ("Can you issue a certificate of insurance listing Acme Corp as an additional insured for our upcoming job?", "customer_query"),
    ("We need a breakdown of the renewal premium calculation and payment schedule options.", "customer_query"),
]


def prepare_datasets(samples_per_class: int = 25, test_samples_per_class: int = 15):
    """
    Downloads and filters the Bitext insurance dataset, maps intents,
    and returns balanced train and test Dataset objects.
    """
    print("[1/5] Loading Bitext Insurance dataset from Hugging Face...")
    hf_dataset = load_dataset("bitext/Bitext-insurance-llm-chatbot-training-dataset", split="train")

    class_pool = defaultdict(list)

    # 1. Ingest mapped Bitext rows
    for row in hf_dataset:
        intent = row.get("intent", "")
        mapped_cat = INTENT_MAPPING.get(intent)
        if mapped_cat:
            clean_instruction = row.get("instruction", "").strip()
            # Clean profanity tags in Bitext synthetic set for clean enterprise training
            clean_instruction = clean_instruction.replace("fucking ", "").replace("fuciing ", "").replace("fucing ", "")
            if len(clean_instruction) > 15:
                class_pool[mapped_cat].append(clean_instruction)

    # 2. Add domain supplements
    for text, cat in DOMAIN_SUPPLEMENT:
        class_pool[cat].append(text)

    # 3. Create balanced train and test splits
    random.seed(42)
    train_rows = []
    test_rows = []

    for cat in CATEGORIES:
        pool = list(set(class_pool[cat]))
        random.shuffle(pool)
        
        train_slice = pool[:samples_per_class]
        test_slice = pool[samples_per_class:samples_per_class + test_samples_per_class]

        label_id = LABEL2ID[cat]
        for t in train_slice:
            train_rows.append({"text": t, "label": label_id, "category": cat})
        for t in test_slice:
            test_rows.append({"text": t, "label": label_id, "category": cat})

    random.shuffle(train_rows)
    random.shuffle(test_rows)

    print(f"      Extracted {len(train_rows)} training samples ({samples_per_class}/class)")
    print(f"      Extracted {len(test_rows)} testing samples ({test_samples_per_class}/class)")

    # 4. Save JSONL files locally for offline inspection and CLI batch evaluation
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    with open(data_dir / "insurance_train.jsonl", "w") as f:
        for r in train_rows:
            f.write(json.dumps(r) + "\n")

    with open(data_dir / "insurance_test.jsonl", "w") as f:
        for r in test_rows:
            f.write(json.dumps(r) + "\n")

    # Curate benchmark evaluation set including out-of-scope queries
    benchmark_cases = list(test_rows)
    benchmark_cases.extend([
        {"text": "A pipe burst this morning and water is reaching the electrical panel. Policy 12345.", "label": 0, "category": "claims_intake"},
        {"text": "Can you provide the recipe for a traditional Neapolitan pizza dough?", "label": -1, "category": "out_of_scope"},
        {"text": "What is the capital of Australia and the population of Canberra?", "label": -1, "category": "out_of_scope"},
    ])
    with open(data_dir / "insurance_benchmark_eval.jsonl", "w") as f:
        for r in benchmark_cases:
            f.write(json.dumps(r) + "\n")

    print(f"      Saved: data/insurance_train.jsonl, data/insurance_test.jsonl, data/insurance_benchmark_eval.jsonl")

    train_ds = Dataset.from_list([{"text": r["text"], "label": r["label"]} for r in train_rows])
    test_ds = Dataset.from_list([{"text": r["text"], "label": r["label"]} for r in test_rows])

    return train_ds, test_ds, test_rows


def train_setfit():
    train_ds, test_ds, raw_test_rows = prepare_datasets(samples_per_class=30, test_samples_per_class=15)

    model_id = "sentence-transformers/all-MiniLM-L6-v2"
    print(f"\n[2/5] Initializing SetFit model backbone: {model_id}...")
    model = SetFitModel.from_pretrained(
        model_id,
        labels=CATEGORIES,
    )

    args = TrainingArguments(
        batch_size=16,
        num_epochs=1,
        num_iterations=20,  # Generate 20 contrastive pairs per sample
        seed=42,
        show_progress_bar=True,
    )

    print("\n[3/5] Starting contrastive fine-tuning on CPU (typically ~45 seconds)...")
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=test_ds,
        metric="accuracy",
    )

    trainer.train()

    print("\n[4/5] Evaluating trained model on held-out test split...")
    test_texts = [r["text"] for r in raw_test_rows]
    true_labels = [r["label"] for r in raw_test_rows]

    preds = model.predict(test_texts)
    # Convert preds to integer list
    pred_labels = [int(p) if not isinstance(p, str) else LABEL2ID.get(p, 0) for p in preds]

    acc = accuracy_score(true_labels, pred_labels)
    print(f"\n=======================================================")
    print(f"  SETFIT HELD-OUT TEST ACCURACY: {acc * 100:.2f}%")
    print(f"=======================================================")
    
    report = classification_report(
        true_labels,
        pred_labels,
        labels=list(range(len(CATEGORIES))),
        target_names=CATEGORIES,
        digits=4,
        zero_division=0,
    )
    print("\nClassification Report:\n", report)

    # 5. Export model
    output_dir = Path("models/setfit-insurance-triage")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[5/5] Saving fine-tuned model to {output_dir}...")
    model.save_pretrained(str(output_dir))

    # Also save label metadata
    with open(output_dir / "categories.json", "w") as f:
        json.dump({"categories": CATEGORIES, "id2label": ID2LABEL, "label2id": LABEL2ID}, f, indent=2)

    print("\nTraining completed successfully! Model is ready for inference in main.py.")


if __name__ == "__main__":
    train_setfit()
