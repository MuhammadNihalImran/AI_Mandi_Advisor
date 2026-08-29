#!/usr/bin/env bash
# =============================================================================
# Production Readiness Check — AI Mandi Advisor
# =============================================================================
# Simulates what Render does on deploy:
#   1. Fresh venv + production deps only (no pytest/pytest-cov)
#   2. uvicorn without --reload
#   3. curl smoke-tests on /api/health, /api/predict, /api/advice
#
# Usage:
#   bash server/scripts/prod_check.sh
#
# Prerequisites:
#   - GROQ_API_KEY must be set in the environment (or in server/.env)
#   - Python 3.11+ available
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$SERVER_DIR/.." && pwd)"
CSV_PATH="$SERVER_DIR/app/data/faisalabad_tomato_dataset.csv"

VENV_DIR="$SERVER_DIR/.venv_prod_check"
PORT=8000
BASE="http://127.0.0.1:$PORT"
PID=""
PASS=0
FAIL=0
FAILURES=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
cleanup() {
    echo ""
    echo "--- Cleaning up ---"
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || true
        wait "$PID" 2>/dev/null || true
    fi
    echo "Removing test venv: $VENV_DIR"
    rm -rf "$VENV_DIR"
    # Remove the test database so it doesn't pollute the workspace
    rm -f "$SERVER_DIR/mandi.db"
}

trap cleanup EXIT

pass() {
    PASS=$((PASS + 1))
    echo -e "  ${GREEN}PASS${NC} — $1"
}

fail() {
    FAIL=$((FAIL + 1))
    FAILURES="${FAILURES}\n  - $1: $2"
    echo -e "  ${RED}FAIL${NC} — $1: $2"
}

info() {
    echo -e "${YELLOW}→${NC} $1"
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
echo "============================================================"
echo " AI Mandi Advisor — Production Readiness Check"
echo "============================================================"
echo ""

if ! command -v python3 &>/dev/null; then
    echo -e "${RED}ERROR: python3 not found in PATH${NC}"
    exit 1
fi

if ! command -v curl &>/dev/null; then
    echo -e "${RED}ERROR: curl not found in PATH${NC}"
    exit 1
fi

# Check CSV exists (needed for auto-seed)
if [ ! -f "$CSV_PATH" ]; then
    echo -e "${RED}ERROR: CSV not found at $CSV_PATH${NC}"
    echo "  The auto-seed on startup requires this file."
    exit 1
fi

# Check GROQ_API_KEY
if [ -z "${GROQ_API_KEY:-}" ]; then
    # Try loading from server/.env
    if [ -f "$SERVER_DIR/.env" ]; then
        info "GROQ_API_KEY not in env, loading from server/.env"
        set -a
        # shellcheck disable=SC1091
        source "$SERVER_DIR/.env"
        set +a
    fi
    if [ -z "${GROQ_API_KEY:-}" ]; then
        echo -e "${RED}ERROR: GROQ_API_KEY is not set${NC}"
        echo "  Set it in your environment or in server/.env"
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Step 1: Fresh venv + production deps only
# ---------------------------------------------------------------------------
info "Step 1/4: Creating fresh virtualenv..."
rm -rf "$VENV_DIR"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

info "Step 1/4: Installing production dependencies (requirements.txt only)..."
pip install --upgrade pip -q
pip install -r "$SERVER_DIR/requirements.txt" -q

# Verify pytest is NOT installed (dev-only package)
if python -c "import pytest" 2>/dev/null; then
    fail "Dev isolation" "pytest found in production venv — should not be in requirements.txt"
else
    pass "Dev isolation: pytest NOT in production venv"
fi

# ---------------------------------------------------------------------------
# Step 2: Start server (production mode — no --reload)
# ---------------------------------------------------------------------------
info "Step 2/4: Starting uvicorn (production mode, port $PORT)..."

cd "$SERVER_DIR"
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &
PID=$!

# Wait for server to be ready (up to 30 seconds)
info "Step 2/4: Waiting for server to become ready..."
READY=0
for i in $(seq 1 30); do
    if curl -sf "$BASE/api/health" > /dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 1
done

if [ "$READY" -eq 0 ]; then
    fail "Server startup" "Timed out after 30s"
    echo ""
    echo "--- Server logs ---"
    # Show any output
    exit 1
fi
pass "Server started successfully (PID: $PID)"

# ---------------------------------------------------------------------------
# Step 3: Smoke-test endpoints
# ---------------------------------------------------------------------------
echo ""
info "Step 3/4: Testing API endpoints..."
echo ""

# --- /api/health ---
echo "  [1/3] GET /api/health"
HTTP_CODE=$(curl -s -o /tmp/prod_check_health.json -w "%{http_code}" "$BASE/api/health" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    BODY=$(cat /tmp/prod_check_health.json)
    if echo "$BODY" | python -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ok'" 2>/dev/null; then
        pass "GET /api/health → 200, status=ok"
    else
        fail "GET /api/health" "Response body invalid: $BODY"
    fi
else
    fail "GET /api/health" "Expected 200, got $HTTP_CODE"
fi

# --- POST /api/predict ---
echo "  [2/3] POST /api/predict"
PREDICT_BODY='{"temperature":33,"rainfall":0.5,"humidity":65,"last_price":246}'
HTTP_CODE=$(curl -s -o /tmp/prod_check_predict.json -w "%{http_code}" \
    -X POST "$BASE/api/predict" \
    -H "Content-Type: application/json" \
    -d "$PREDICT_BODY" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    PRED_PRICE=$(python -c "import json; d=json.load(open('/tmp/prod_check_predict.json')); print(d.get('predicted_price', 'MISSING'))" 2>/dev/null)
    DELTA=$(python -c "import json; d=json.load(open('/tmp/prod_check_predict.json')); print(d.get('delta_pct', 'MISSING'))" 2>/dev/null)
    if [ "$PRED_PRICE" != "MISSING" ] && [ "$DELTA" != "MISSING" ]; then
        pass "POST /api/predict → 200 (price: Rs $PRED_PRICE/kg, delta: ${DELTA}%)"
    else
        fail "POST /api/predict" "Missing predicted_price or delta_pct in response"
    fi
else
    BODY=$(cat /tmp/prod_check_predict.json 2>/dev/null)
    fail "POST /api/predict" "Expected 200, got $HTTP_CODE — $BODY"
fi

# --- POST /api/advice ---
echo "  [3/3] POST /api/advice"
ADVICE_BODY='{"temperature":33,"rainfall":0.5,"humidity":65,"last_price":246}'
HTTP_CODE=$(curl -s -o /tmp/prod_check_advice.json -w "%{http_code}" \
    -X POST "$BASE/api/advice" \
    -H "Content-Type: application/json" \
    -d "$ADVICE_BODY" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    ADVICE=$(python -c "import json; d=json.load(open('/tmp/prod_check_advice.json')); print(d.get('advice', 'MISSING')[:80])" 2>/dev/null)
    if [ "$ADVICE" != "MISSING" ] && [ -n "$ADVICE" ]; then
        pass "POST /api/advice → 200 (advice: '${ADVICE}...')"
    else
        fail "POST /api/advice" "Missing advice text in response"
    fi
elif [ "$HTTP_CODE" = "429" ]; then
    fail "POST /api/advice" "Groq rate limit hit (429) — free tier quota exhausted, try later"
elif [ "$HTTP_CODE" = "503" ]; then
    fail "POST /api/advice" "AI service unavailable (503) — Groq models may be down"
else
    BODY=$(cat /tmp/prod_check_advice.json 2>/dev/null)
    fail "POST /api/advice" "Expected 200, got $HTTP_CODE — $BODY"
fi

# ---------------------------------------------------------------------------
# Step 4: Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo " RESULTS: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}"
echo "============================================================"

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}"
    echo ""
    echo " PRODUCTION CHECK FAILED"
    echo -e " Failures:${FAILURES}"
    echo -e "${NC}"
    exit 1
else
    echo -e "${GREEN}"
    echo ""
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║   PRODUCTION CHECK PASSED            ║"
    echo "  ║   All endpoints working correctly    ║"
    echo "  ╚══════════════════════════════════════╝"
    echo -e "${NC}"
    exit 0
fi
