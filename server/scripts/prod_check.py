#!/usr/bin/env python3
"""
Production Readiness Check — AI Mandi Advisor (Python version)
──────────────────────────────────────────────────────────────
Works on Windows + Linux without bash.

Simulates what Render does on deploy:
  1. Fresh venv + production deps only (no pytest/pytest-cov)
  2. uvicorn without --reload
  3. HTTP smoke-tests on /api/health, /api/predict, /api/advice
  4. Cleanup

Usage:
    python server/scripts/prod_check.py
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
SERVER_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SERVER_DIR.parent
CSV_PATH = SERVER_DIR / "app" / "data" / "faisalabad_tomato_dataset.csv"
VENV_DIR = SERVER_DIR / ".venv_prod_check"
PORT = 8000
BASE = f"http://127.0.0.1:{PORT}"

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
_pass_count = 0
_fail_count = 0
_failures: list[str] = []
_server_proc = None

# Colors (ANSI — works on modern Windows Terminal + Linux)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
NC = "\033[0m"


def _pass(msg: str):
    global _pass_count
    _pass_count += 1
    print(f"  {GREEN}PASS{NC} — {msg}")


def _fail(name: str, detail: str):
    global _fail_count
    _fail_count += 1
    _failures.append(f"{name}: {detail}")
    print(f"  {RED}FAIL{NC} — {name}: {detail}")


def info(msg: str):
    print(f"{YELLOW}>>{NC} {msg}")


def http_get(url: str, timeout: float = 5) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 0, str(e)


def http_post(url: str, body: dict, timeout: float = 30) -> tuple[int, str]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 0, str(e)


def cleanup():
    print("\n--- Cleaning up ---")
    if _server_proc and _server_proc.poll() is None:
        _server_proc.terminate()
        try:
            _server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _server_proc.kill()
    if VENV_DIR.exists():
        print(f"Removing test venv: {VENV_DIR}")
        shutil.rmtree(VENV_DIR, ignore_errors=True)
    # Remove test database
    db_path = SERVER_DIR / "mandi.db"
    if db_path.exists():
        db_path.unlink()


def find_python() -> str:
    """Find a working python executable."""
    # On Windows, prefer 'python' over 'python3' (Store stub)
    candidates = ("python", "python3") if sys.platform == "win32" else ("python3", "python")
    for name in candidates:
        p = shutil.which(name)
        if p:
            # Verify it actually works
            try:
                subprocess.run(
                    [p, "-c", "import sys; sys.exit(0)"],
                    capture_output=True, timeout=5,
                )
                return p
            except Exception:
                continue
    print(f"{RED}ERROR: python not found in PATH{NC}")
    sys.exit(1)


def main():
    global _server_proc

    print("=" * 60)
    print(" AI Mandi Advisor — Production Readiness Check")
    print("=" * 60)
    print()

    python = find_python()

    # Pre-flight: CSV
    if not CSV_PATH.exists():
        print(f"{RED}ERROR: CSV not found at {CSV_PATH}{NC}")
        print("  The auto-seed on startup requires this file.")
        sys.exit(1)

    # Pre-flight: GROQ_API_KEY
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        env_file = SERVER_DIR / ".env"
        if env_file.exists():
            info("GROQ_API_KEY not in env, loading from server/.env")
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("GROQ_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        if not api_key:
            print(f"{RED}ERROR: GROQ_API_KEY is not set{NC}")
            print("  Set it in your environment or in server/.env")
            sys.exit(1)

    try:
        _run_checks(python, api_key)
    finally:
        cleanup()


def _run_checks(python: str, api_key: str):
    global _server_proc

    # ── Step 1: Fresh venv + prod deps ──
    info("Step 1/4: Creating fresh virtualenv...")
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR, ignore_errors=True)
    subprocess.run([python, "-m", "venv", str(VENV_DIR)], check=True, capture_output=True)

    venv_python = str(VENV_DIR / "Scripts" / "python.exe") if sys.platform == "win32" \
        else str(VENV_DIR / "bin" / "python")
    venv_pip = str(VENV_DIR / "Scripts" / "pip.exe") if sys.platform == "win32" \
        else str(VENV_DIR / "bin" / "pip")

    info("Step 1/4: Installing production dependencies (requirements.txt only)...")
    subprocess.run([venv_pip, "install", "--upgrade", "pip", "-q"], capture_output=True)
    result = subprocess.run(
        [venv_pip, "install", "-r", str(SERVER_DIR / "requirements.txt"), "-q"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        _fail("pip install", result.stderr[:500])
        print(f"\n{RED}Cannot continue without dependencies.{NC}")
        sys.exit(1)

    # Verify pytest NOT installed
    check = subprocess.run(
        [venv_python, "-c", "import pytest"],
        capture_output=True,
    )
    if check.returncode == 0:
        _fail("Dev isolation", "pytest found in production venv — should not be in requirements.txt")
    else:
        _pass("Dev isolation: pytest NOT in production venv")

    # ── Step 2: Start server ──
    info(f"Step 2/4: Starting uvicorn (production mode, port {PORT})...")

    env = os.environ.copy()
    env["GROQ_API_KEY"] = api_key
    env["DATABASE_URL"] = "sqlite:///./mandi.db"
    env["CORS_ORIGINS"] = '["*"]'

    _server_proc = subprocess.Popen(
        [venv_python, "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", str(PORT)],
        cwd=str(SERVER_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    info("Step 2/4: Waiting for server to become ready...")
    ready = False
    for _ in range(30):
        if _server_proc.poll() is not None:
            # Process died
            output = _server_proc.stdout.read().decode() if _server_proc.stdout else ""
            _fail("Server startup", f"Process exited with code {_server_proc.returncode}")
            print(f"\n--- Server output ---\n{output[:500]}")
            sys.exit(1)
        code, _ = http_get(f"{BASE}/api/health", timeout=2)
        if code == 200:
            ready = True
            break
        time.sleep(1)

    if not ready:
        _fail("Server startup", "Timed out after 30s")
        if _server_proc.stdout:
            print(f"\n--- Server output ---\n{_server_proc.stdout.read().decode()[:500]}")
        sys.exit(1)
    _pass(f"Server started successfully (PID: {_server_proc.pid})")

    # ── Step 3: Smoke-test endpoints ──
    print()
    info("Step 3/4: Testing API endpoints...")
    print()

    body = {"temperature": 33, "rainfall": 0.5, "humidity": 65, "last_price": 246}

    # 1/3: GET /api/health
    print("  [1/3] GET /api/health")
    code, resp = http_get(f"{BASE}/api/health")
    if code == 200:
        try:
            data = json.loads(resp)
            if data.get("status") == "ok":
                _pass("GET /api/health → 200, status=ok")
            else:
                _fail("GET /api/health", f"Unexpected body: {resp[:100]}")
        except json.JSONDecodeError:
            _fail("GET /api/health", f"Invalid JSON: {resp[:100]}")
    else:
        _fail("GET /api/health", f"Expected 200, got {code}")

    # 2/3: POST /api/predict
    print("  [2/3] POST /api/predict")
    code, resp = http_post(f"{BASE}/api/predict", body)
    if code == 200:
        try:
            data = json.loads(resp)
            price = data.get("predicted_price")
            delta = data.get("delta_pct")
            if price is not None and delta is not None:
                _pass(f"POST /api/predict → 200 (price: Rs {price}/kg, delta: {delta}%)")
            else:
                _fail("POST /api/predict", f"Missing fields in: {resp[:100]}")
        except json.JSONDecodeError:
            _fail("POST /api/predict", f"Invalid JSON: {resp[:100]}")
    else:
        _fail("POST /api/predict", f"Expected 200, got {code} — {resp[:100]}")

    # 3/3: POST /api/advice
    print("  [3/3] POST /api/advice")
    code, resp = http_post(f"{BASE}/api/advice", body)
    if code == 200:
        try:
            data = json.loads(resp)
            advice = data.get("advice", "")
            if advice:
                _pass(f"POST /api/advice → 200 (advice: '{advice[:60]}...')")
            else:
                _fail("POST /api/advice", "Missing advice text in response")
        except json.JSONDecodeError:
            _fail("POST /api/advice", f"Invalid JSON: {resp[:100]}")
    elif code == 429:
        _fail("POST /api/advice", "Groq rate limit hit (429) — free tier quota exhausted")
    elif code == 503:
        _fail("POST /api/advice", "AI service unavailable (503) — Groq models may be down")
    else:
        _fail("POST /api/advice", f"Expected 200, got {code} — {resp[:100]}")

    # ── Step 4: Summary ──
    print()
    print("=" * 60)
    print(f" RESULTS: {GREEN}{_pass_count} passed{NC}, {RED}{_fail_count} failed{NC}")
    print("=" * 60)

    if _fail_count > 0:
        print(f"\n{RED}")
        print(" PRODUCTION CHECK FAILED")
        for f in _failures:
            print(f"  - {f}")
        print(f"{NC}")
        sys.exit(1)
    else:
        print(f"\n{GREEN}")
        print("  +--------------------------------------+")
        print("  |   PRODUCTION CHECK PASSED            |")
        print("  |   All endpoints working correctly    |")
        print("  +--------------------------------------+")
        print(f"{NC}")
        sys.exit(0)


if __name__ == "__main__":
    main()
