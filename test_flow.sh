#!/bin/bash
TOKEN=$(curl -s -X POST http://localhost:8081/api/v1/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@test.com", "password": "Admin123!"}' | jq -r .token)

JOB_ID=$(curl -s -X POST http://localhost:8081/api/v1/admin/generation/preview \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a simple calculator API",
    "languages": ["node"],
    "tiers": ["easy"],
    "scenariosPerTier": 1,
    "debugScenariosPerTier": 0
  }' | jq -r .id)

echo "Started job: $JOB_ID"

while true; do
  STATUS=$(curl -s -X GET http://localhost:8081/api/v1/admin/generation/$JOB_ID/status \
    -H "Authorization: Bearer $TOKEN" | jq -r .status)
  
  echo "Current status: $STATUS"
  
  if [ "$STATUS" = "AWAITING_APPROVAL" ]; then
    echo "Approving job..."
    curl -s -X POST http://localhost:8081/api/v1/admin/generation/$JOB_ID/approve \
      -H "Authorization: Bearer $TOKEN"
    break
  fi
  
  if [ "$STATUS" = "FAILED" ]; then
    echo "Job failed during design!"
    exit 1
  fi
  
  sleep 5
done

echo ""
echo "Waiting for generation to finish..."

while true; do
  STATUS=$(curl -s -X GET http://localhost:8081/api/v1/admin/generation/$JOB_ID/status \
    -H "Authorization: Bearer $TOKEN" | jq -r .status)
  
  echo "Current status: $STATUS"
  
  if [ "$STATUS" = "COMPLETED" ]; then
    echo "Job fully completed!"
    exit 0
  fi
  
  if [ "$STATUS" = "FAILED" ]; then
    echo "Job failed during generation!"
    exit 1
  fi
  
  sleep 5
done
