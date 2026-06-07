<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# DFlash Speculator Training & Serving Orchestrator

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![vLLM Compatible](https://img.shields.io/badge/vLLM-Compatible-blueviolet)](https://github.com/vllm-project/vllm)
[![Powered by Regolo](https://img.shields.io/badge/Powered%20by-Regolo%20GPU-green)](https://regolo.ai)

This repository contains all the code from the article [Train & Run DFlash Speculative Decoding with vLLM](https://regolo.ai/train-run-dflash-speculative-decoding-vllm/).

This project provides an orchestration pipeline to train and serve a **DFlash** speculative decoding speculator using the `vllm-project/speculators` library and `vLLM`.

Unlike traditional speculative decoding algorithms (e.g., EAGLE) that draft candidate tokens autoregressively (one-by-one), **DFlash** leverages a non-causal transformer draft model to generate an entire block of candidate tokens in a single parallel step (block diffusion). This parallelized drafting step can deliver a 3× to 5× throughput increase depending on your hardware, model size, and prompt structure, while keeping the output mathematically lossless.

---

## Repository Structure

Running the setup script initializes the following workspace structure:

```text
├── scripts/
│   ├── prepare_data.py       # Preprocesses raw text datasets (e.g., ShareGPT)
│   ├── launch_vllm.py        # Wrapper script to expose verifier hidden states
│   └── train.py              # Orchestrates DFlash block diffusion online training
├── output/                   # Target directory for preprocessed dataset files
├── checkpoints/              # Output directory for trained speculator checkpoints
├── run_online_training.sh    # Main bash script to manage multi-GPU online training
└── run_inference.sh          # Server utility to deploy your trained speculator
```

*Note: The scripts inside `scripts/` are configured as architectural templates. For actual execution, integrate this repository with the official code from the [vllm-project/speculators](https://github.com/vllm-project/speculators) repository.*

---

## Context: Why DFlash?

Standard speculative decoding uses a smaller, causal autoregressive draft model. While this reduces computation compared to the main verifier model, the sequential generation of draft tokens remains a latency bottleneck. 

DFlash addresses this limitation by deploying a **bidirectional draft model**. 
1. **Parallel Draft Generation:** The speculator takes the hidden states from the verifier model and generates up to 15+ candidate tokens simultaneously in one forward pass.
2. **Efficient Verification:** The verifier model processes the entire drafted block in parallel, accepting the longest valid match.
3. **Decoupled System Architecture:** The verifier's weights are completely unchanged, preserving accuracy, license compliance, and baseline model safety behaviors.

---

## Prerequisites

Before running the training or serving scripts, ensure you have installed the required dependencies in a GPU-enabled environment:

```bash
pip install vllm
# Clone and install the speculators library
git clone https://github.com/vllm-project/speculators.git
pip install -e speculators/
```

---

## How to Use

### 1. Initialize the Workspace
If you have not done so already, run the helper script to generate the folder structure and configuration templates:

```bash
python setup_project.py
```

### 2. Configure Hardware Resource Allocation
During DFlash training, the verifier model runs on-the-fly to stream intermediate hidden states to the speculator training process (Online Training). Running both operations concurrently on the same GPU can easily cause Out-Of-Memory (OOM) errors. 

Open `run_online_training.sh` and allocate separate GPU indices for the vLLM server and the PyTorch training run:

```bash
# Example for a 4-GPU system:
VLLM_GPUS="0,1"   # GPUs dedicated to the verifier (vLLM)
TRAIN_GPUS="2,3"  # GPUs dedicated to speculator training (torchrun)
```

### 3. Launch the Online Training Pipeline
The orchestration script automatically handles data preprocessing, boots the vLLM hidden states server with correct layer IDs (`--target-layer-ids`), waits for initialization, and kicks off the speculator training loop.

```bash
./run_online_training.sh
```

### 4. Deploy the Accelerated Model
Once training completes and the speculator checkpoint is saved to `./checkpoints/dflash_speculator`, launch the production server using the following utility:

```bash
./run_inference.sh
```

This starts a vLLM server exposing your model with DFlash speculative decoding enabled:
```bash
vllm serve Qwen/Qwen3-8B \
  --tensor-parallel-size 2 \
  --speculative-config '{"method": "dflash", "model": "./checkpoints/dflash_speculator", "num_speculative_tokens": 15}' \
  --attention-backend flash_attn \
  --dtype bfloat16
```

---

## Technical Details & Common Pitfalls

* **Speculator Layer Count:** While Eagle-style speculators usually require only 1 layer, DFlash models are deeper (typically 5 layers) to adequately manage bidirectional parallel context representation.
* **Target Layer Matching:** The `--target-layer-ids` passed to `launch_vllm.py` must exactly match the `--target-layer-ids` specified in the `train.py` configuration. If they diverge, the speculator will receive incompatible feature shapes, causing execution failures.
* **Quantization Support:** DFlash accommodates quantized verifiers (such as AWQ or GPTQ) for inference, as long as the serving backend supports extracting the appropriate intermediate hidden states.

---

## Quick Start

```bash
# Clone and enter the project
git clone https://github.com/Regolo-AI/tutorials.git
cd tutorials/accelerate-llm-inference-dflash

# Install dependencies (GPU-enabled environment required)
pip install vllm
git clone https://github.com/vllm-project/speculators.git
pip install -e speculators/

# Run training pipeline
./run_online_training.sh

# Deploy the accelerated server
./run_inference.sh
```

---

## Related Article

- [Train & Run DFlash Speculative Decoding with vLLM](https://regolo.ai/train-run-dflash-speculative-decoding-vllm/)

---

## Powered by Regolo

Run DFlash speculative decoding on cloud GPUs instead of managing local hardware — no setup required.

[Get Started](https://regolo.ai) · [**Free Trial**](https://regolo.ai/pricing)

Questions? [Open an issue](https://github.com/Regolo-AI/tutorials/issues) or join our [Discord](https://discord.gg/wHxwWCC8).