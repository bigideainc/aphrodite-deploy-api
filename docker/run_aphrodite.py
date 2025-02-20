#!/usr/bin/env python3
import os
import subprocess
import sys

def ensure_huggingface_cache_dir():
    hf_cache_dir = "/root/.cache/huggingface/hub"
    os.makedirs(hf_cache_dir, exist_ok=True)
    print(f"Ensured directory exists: {hf_cache_dir}")

def run_aphrodite():
    model_id = os.environ.get("MODEL_ID", "gpt2")
    cmd = ["aphrodite", "run", "--device", "openvino", "--host", "0.0.0.0", model_id]
    print("Running command:", " ".join(cmd))
    
    env = os.environ.copy()
    env["APHRODITE_OPENVINO_KVCACHE_SPACE"] = os.environ.get("APHRODITE_OPENVINO_KVCACHE_SPACE", "8")
    
    subprocess.check_call(cmd, env=env)

def main():
    huggingface_token = os.environ.get("HUGGINGFACE_TOKEN")
    if huggingface_token:
        os.environ["HUGGINGFACE_TOKEN"] = huggingface_token
        print("Hugging Face token is set.")
    
    print("Detected device: cpu (using OpenVINO backend)")
    ensure_huggingface_cache_dir()
    run_aphrodite()

if __name__ == "__main__":
    main()