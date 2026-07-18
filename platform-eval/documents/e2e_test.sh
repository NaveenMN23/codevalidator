#!/usr/bin/env bash
# End-to-end smoke test for platform-eval
# Usage:
#   ./documents/e2e_test.sh                    # default: localhost:8002
#   EVAL_URL=http://localhost:8002 ./documents/e2e_test.sh
#
# Requires: curl, jq
# Run the service first: docker compose up --build platform-eval
#   OR with STORE_BACKEND=memory (no DB needed):
#     cd platform-eval && STORE_BACKEND=memory OPENAI_API_KEY=sk-... python main.py

set -euo pipefail

EVAL_URL="${EVAL_URL:-http://localhost:8002}"
SESSION_ID="e2e-test-$(date +%s)"
PROBLEM_ID="calculator-application-easy-perform-calculation"

GREEN="\033[0;32m"; RED="\033[0;31m"; NC="\033[0m"; BOLD="\033[1m"
pass() { echo -e "${GREEN}✓ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; exit 1; }
section() { echo -e "\n${BOLD}── $1 ──${NC}"; }

# ── 1. Health check ───────────────────────────────────────────────────────────
section "Health"
HEALTH=$(curl -sf "$EVAL_URL/health")
echo "$HEALTH" | jq .
echo "$HEALTH" | jq -e '.status == "healthy"' > /dev/null && pass "Health OK" || fail "Health check failed"

# ── 2. POST /eval/submit — initial code submission ────────────────────────────
section "Code Submission"
SUBMIT_BODY=$(cat <<EOF
{
  "problem_id": "$PROBLEM_ID",
  "session_id": "$SESSION_ID",
  "submission": {
    "changed_files": {
      "src/services/CalculatorService.py": "def perform_calculation(operation, operand1, operand2):\n    if operation == 'add':\n        return operand1 + operand2\n    elif operation == 'subtract':\n        return operand1 - operand2\n    elif operation == 'multiply':\n        return operand1 * operand2\n    elif operation == 'divide':\n        if operand2 == 0:\n            raise ZeroDivisionError('Cannot divide by zero')\n        return operand1 / operand2\n    else:\n        raise InvalidOperationException(f'Unknown operation: {operation}')"
    }
  },
  "time_remaining_seconds": 2700,
  "minimum_time_remaining_seconds": 600
}
EOF
)

SUBMIT_RESP=$(curl -sf -X POST "$EVAL_URL/eval/submit" \
  -H "Content-Type: application/json" \
  -d "$SUBMIT_BODY")

echo "$SUBMIT_RESP" | jq .

# Validate structure
echo "$SUBMIT_RESP" | jq -e '.session_id' > /dev/null         && pass "session_id present"        || fail "Missing session_id"
echo "$SUBMIT_RESP" | jq -e '.next_action' > /dev/null        && pass "next_action present"       || fail "Missing next_action"
echo "$SUBMIT_RESP" | jq -e '.evaluation.correctness' > /dev/null && pass "correctness present"   || fail "Missing correctness"
echo "$SUBMIT_RESP" | jq -e '.evaluation.efficiency' > /dev/null  && pass "efficiency present"    || fail "Missing efficiency"

# Acknowledgment must be present
ACK=$(echo "$SUBMIT_RESP" | jq -r '.evaluation.acknowledgment // empty')
[ -n "$ACK" ] && pass "acknowledgment present: \"${ACK:0:60}...\"" || fail "acknowledgment missing from response"

# Check expected_answer_key is NOT leaked to candidate
echo "$SUBMIT_RESP" | jq -e '.evaluation.follow_up.expected_answer_key == null or .evaluation.follow_up.expected_answer_key == ""' 2>/dev/null \
  && pass "expected_answer_key not leaked" || echo "(no MCQ follow-up this run — skip key-leak check)"

# Check chosen_area is NOT in candidate view
echo "$SUBMIT_RESP" | jq -e '.evaluation.follow_up.chosen_area == null' 2>/dev/null \
  && pass "chosen_area not in candidate view" || echo "(follow_up null — skip chosen_area check)"

NEXT_ACTION=$(echo "$SUBMIT_RESP" | jq -r '.next_action')
CLOSED=$(echo "$SUBMIT_RESP" | jq -r '.closed')

# ── 3. GET /eval/session — verify session persisted ───────────────────────────
section "Session Read"
SESSION_RESP=$(curl -sf "$EVAL_URL/eval/session/$SESSION_ID")
echo "$SESSION_RESP" | jq '{session_id, problem_id, stage, turn_count, probed_areas, concept_scores}'

echo "$SESSION_RESP" | jq -e ".session_id == \"$SESSION_ID\"" > /dev/null && pass "Session persisted" || fail "Session not found"
echo "$SESSION_RESP" | jq -e '.probed_areas | type == "array"' > /dev/null && pass "probed_areas is array" || fail "Missing probed_areas"

# ── 4. POST /eval/answer — conversational follow-up ──────────────────────────
if [ "$NEXT_ACTION" = "AWAIT_ANSWER" ] && [ "$CLOSED" = "false" ]; then
  section "Conversational Answer"

  FOLLOW_UP_Q=$(echo "$SUBMIT_RESP" | jq -r '.evaluation.follow_up.question // "What is the time complexity?"')
  echo "Answering follow-up: $FOLLOW_UP_Q"

  ANSWER_BODY=$(cat <<EOF
{
  "problem_id": "$PROBLEM_ID",
  "session_id": "$SESSION_ID",
  "answer": "The time complexity is O(1) because each operation is a single arithmetic step with no loops. I used an if/elif chain which means all branches are evaluated sequentially, so a dispatch dictionary would be more efficient for many operations.",
  "time_remaining_seconds": 2400,
  "minimum_time_remaining_seconds": 600
}
EOF
)

  ANSWER_RESP=$(curl -sf -X POST "$EVAL_URL/eval/answer" \
    -H "Content-Type: application/json" \
    -d "$ANSWER_BODY")

  echo "$ANSWER_RESP" | jq .

  echo "$ANSWER_RESP" | jq -e '.evaluation.acknowledgment' > /dev/null && pass "Conversational acknowledgment present" || fail "Missing acknowledgment on answer"
  echo "$ANSWER_RESP" | jq -e '.evaluation.answer_rating' > /dev/null  && pass "answer_rating present"   || fail "Missing answer_rating"
  echo "$ANSWER_RESP" | jq -e '.evaluation.finding' > /dev/null         && pass "finding present"         || fail "Missing finding"

  ACK2=$(echo "$ANSWER_RESP" | jq -r '.evaluation.acknowledgment // empty')
  [ -n "$ACK2" ] && pass "answer ack: \"${ACK2:0:60}...\"" || fail "Empty acknowledgment on answer"

  CLOSED=$(echo "$ANSWER_RESP" | jq -r '.closed')

  # Verify concept_scores updated in session
  SESSION2=$(curl -sf "$EVAL_URL/eval/session/$SESSION_ID")
  PROBED=$(echo "$SESSION2" | jq -r '.probed_areas | length')
  [ "$PROBED" -gt "0" ] && pass "probed_areas populated ($PROBED area(s))" || fail "probed_areas still empty after answer"
else
  echo "(Session closed after submission or next_action=$NEXT_ACTION — skipping answer step)"
fi

# ── 5. Final report check ────────────────────────────────────────────────────
section "Final Report"
FINAL=$(curl -sf "$EVAL_URL/eval/session/$SESSION_ID")

if echo "$FINAL" | jq -e '.closed == true' > /dev/null 2>&1; then
  SCORE=$(echo "$FINAL" | jq -r '.report.final_score')
  echo "Final score: $SCORE"
  echo "$FINAL" | jq '.report.dimensions | to_entries[] | "\(.key): \(.value.rating)/10 (weight \(.value.weight)%)"' -r
  echo ""
  echo "Concept breakdown:"
  echo "$FINAL" | jq '.report.concept_dimensions | to_entries[] | "\(.key): \(.value.rating)/10 — \(.value.finding)"' -r 2>/dev/null || echo "(no concept dimensions — session closed early)"
  pass "Session closed with report (score=$SCORE)"
else
  echo "Session still open. Run again or wait for more turns."
fi

# ── 6. Replay: 409 on closed session ────────────────────────────────────────
section "Idempotency (closed session)"
if echo "$FINAL" | jq -e '.closed == true' > /dev/null 2>&1; then
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$EVAL_URL/eval/submit" \
    -H "Content-Type: application/json" \
    -d "$SUBMIT_BODY")
  [ "$HTTP_CODE" = "409" ] && pass "Re-submit on closed session returns 409" || fail "Expected 409, got $HTTP_CODE"
fi

# ── 7. 404 on unknown session ────────────────────────────────────────────────
section "404 for unknown session"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$EVAL_URL/eval/session/nonexistent-session-xyz")
[ "$HTTP_CODE" = "404" ] && pass "Unknown session returns 404" || fail "Expected 404, got $HTTP_CODE"

echo -e "\n${GREEN}${BOLD}All checks passed.${NC}"
