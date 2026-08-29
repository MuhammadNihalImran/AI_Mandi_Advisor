#!/usr/bin/env python3
"""
Groq API Verification Script
─────────────────────────────
Tests the GROQ_API_KEY against Groq's API and confirms:
  1. Key is valid (no 401/403)
  2. Model responds successfully
  3. Response contains no <think> tags (reasoning is hidden)

Usage:
    python server/scripts/verify_groq.py
"""

import os
import re
import sys
import time

# ---------------------------------------------------------------------------
# Resolve API key
# ---------------------------------------------------------------------------
api_key = os.environ.get("GROQ_API_KEY")

if not api_key:
    # Try loading from server/.env
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("GROQ_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

if not api_key:
    print("ERROR: GROQ_API_KEY not found")
    print("  Set it in your environment or in server/.env")
    sys.exit(1)

print(f"API key: ...{api_key[-8:]}")
print()

# ---------------------------------------------------------------------------
# Import Groq SDK
# ---------------------------------------------------------------------------
try:
    from groq import Groq, APIStatusError
except ImportError:
    print("ERROR: groq package not installed")
    print("  Run: pip install groq")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Test call
# ---------------------------------------------------------------------------
MODEL = "qwen/qwen3.6-27b"
FALLBACK = "openai/gpt-oss-20b"
SYSTEM = "Tum ek Pakistani mandi price advisor ho."
USER = "Aaj temperature 33C hai, rate Rs 246/kg hai. Bechna chahiye ya rukna? 2 line mein jawab do."

client = Groq(api_key=api_key)

for model_id in (MODEL, FALLBACK):
    print(f"Testing model: {model_id}")
    print(f"  reasoning_format = hidden")
    print(f"  reasoning_effort = none")
    print()

    try:
        t0 = time.perf_counter()
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": USER},
            ],
            max_tokens=256,
            temperature=0.7,
            reasoning_format="hidden",
            reasoning_effort="none",
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000)

        content = response.choices[0].message.content or ""
        usage = response.usage

        # Check for <think> tags
        has_think = bool(re.search(r"<think>", content, re.IGNORECASE))
        has_closing_think = bool(re.search(r"</think>", content, re.IGNORECASE))

        print(f"  Response time: {elapsed_ms}ms")
        print(f"  Tokens: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}")
        print(f"  Response text:")
        for line in content.split("\n"):
            print(f"    {line}")
        print()

        # Verdict
        if has_think or has_closing_think:
            print(f"  FAIL: <think> tags found in response!")
            continue
        else:
            print(f"  PASS: No <think> tags in response")

        print(f"  PASS: Model responded successfully")
        print()
        print("=" * 50)
        print("  GROQ API VERIFICATION PASSED")
        print("=" * 50)
        sys.exit(0)

    except APIStatusError as exc:
        print(f"  FAIL: API error {exc.status_code} — {exc.message}")
        if exc.status_code == 401:
            print("  -> API key is INVALID or expired")
            print("  -> Rotate your key at https://console.groq.com/keys")
            sys.exit(1)
        elif exc.status_code == 404:
            print(f"  -> Model {model_id} not available, trying fallback...")
            print()
            continue
        elif exc.status_code == 429:
            print("  -> Rate limited (free tier quota)")
            print("  -> Key is valid but quota is exhausted")
            sys.exit(1)
        else:
            print(f"  -> Unexpected error: {exc}")
            sys.exit(1)
    except Exception as exc:
        print(f"  FAIL: {type(exc).__name__}: {exc}")
        sys.exit(1)

# Both models failed
print()
print("=" * 50)
print("  GROQ API VERIFICATION FAILED")
print("  All models unavailable")
print("=" * 50)
sys.exit(1)
