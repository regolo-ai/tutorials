#!/bin/bash
# Script per avviare il server di produzione vLLM con la decodifica speculativa DFlash

vllm serve Qwen/Qwen3-8B \
  --tensor-parallel-size 2 \
  --max-model-len 16384 \
  --speculative-config '{
    "method": "dflash",
    "model": "./checkpoints/dflash_speculator",
    "num_speculative_tokens": 15
  }' \
  --attention-backend flash_attn \
  --dtype bfloat16
