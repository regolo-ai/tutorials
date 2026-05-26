import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Launch vLLM server configured for hidden states extraction")
    parser.add_argument("model", type=str)
    parser.add_argument("--target-layer-ids", nargs="+", required=True)
    # Raccoglie gli argomenti extra passati dopo '--'
    args, vllm_args = parser.parse_known_args()
    
    print(f"[STUB] Launching vLLM wrapper for model: {args.model}")
    print(f"[STUB] Extracting target layer IDs: {args.target-layer-ids}")
    print(f"[STUB] Raw arguments passed directly to vLLM: {vllm_args}")
    print("[NOTE] Replace this placeholder with the official implementation from vllm-project/speculators.")

if __name__ == "__main__":
    main()
