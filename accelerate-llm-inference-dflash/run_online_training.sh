#!/bin/bash
# Script per l'addestramento online di DFlash con vLLM Speculators.
# Assicurati di eseguire questo script in un ambiente in cui sia installato 'speculators'.

set -euo pipefail

# ============ CONFIGURAZIONE ============
MODEL="Qwen/Qwen3-8B"  # Modello target (verifier)
DATASET="sharegpt"     # Dataset per il training
OUTPUT_DIR="./output/dflash_qwen3_8b_sharegpt"
VLLM_PORT=8000

# Parametri DFlash
SPECULATOR_TYPE="dflash"
BLOCK_SIZE=8
MAX_ANCHORS=3072
NUM_LAYERS=5
DRAFT_VOCAB_SIZE=32000
# Target Layer IDs cruciali per estrarre hidden states dal verifier
TARGET_LAYER_IDS="2 10 18 26 34"

# Assegnazione GPU (Evita OOM separando server vLLM e training)
VLLM_GPUS="0,1"
TRAIN_GPUS="2,3"
NUM_TRAIN_GPUS=2

echo "=== FASE 1: Preparazione dei dati ==="
CUDA_VISIBLE_DEVICES=$TRAIN_GPUS python scripts/prepare_data.py \
  --model "$MODEL" \
  --data "$DATASET" \
  --output "$OUTPUT_DIR" \
  --seq-length 8192

echo "=== FASE 2: Avvio server vLLM (Estrazione Hidden States) ==="
# Lancio tramite wrapper launch_vllm.py
CUDA_VISIBLE_DEVICES=$VLLM_GPUS python scripts/launch_vllm.py "$MODEL" \
  --target-layer-ids $TARGET_LAYER_IDS \
  -- \
  --port $VLLM_PORT \
  --gpu-memory-utilization 0.9 \
  --tensor-parallel-size 1 \
  --data-parallel-size 2 &

VLLM_PID=$!

cleanup() {
  echo "Arresto del server vLLM (PID: $VLLM_PID)..."
  kill -9 $VLLM_PID || true
}
# Assicura la chiusura del server in caso di interruzione o errore dello script
trap cleanup EXIT

echo "In attesa dell'avvio completo del server vLLM..."
sleep 60

echo "=== FASE 3: Avvio Addestramento Online ==="
# Lancio con torchrun distribuito sulle GPU dedicate al training
CUDA_VISIBLE_DEVICES=$TRAIN_GPUS torchrun \
  --standalone \
  --nproc_per_node=$NUM_TRAIN_GPUS \
  scripts/train.py \
  --verifier-name-or-path "$MODEL" \
  --speculator-type "$SPECULATOR_TYPE" \
  --num-layers $NUM_LAYERS \
  --data-path "$OUTPUT_DIR" \
  --vllm-endpoint "http://localhost:$VLLM_PORT/v1" \
  --save-path "./checkpoints/dflash_speculator" \
  --epochs 3 \
  --lr 0.0006 \
  --total-seq-len 8192 \
  --on-missing generate \
  --on-generate delete \
  --seed 42 \
  --draft-vocab-size $DRAFT_VOCAB_SIZE \
  --target-layer-ids $TARGET_LAYER_IDS \
  --scheduler-type cosine \
  --max-anchors $MAX_ANCHORS

echo "Training completato con successo."
