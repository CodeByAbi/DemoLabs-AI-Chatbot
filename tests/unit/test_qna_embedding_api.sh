#!/bin/bash

# Test script for QnA embedding endpoint
# This script tests the /api/v1/queue/submit/qna-embedding endpoint

API_URL="http://localhost:8000"
API_KEY="your-api-key-here"  # Update with your actual API key
TASK_ID="embed_qna_$(date +%s)"
USER_ID="test_user"
DATASET_ID="b993df02-5048-465a-8f69-e3bb00d507f3"  # Update with your dataset ID

echo "🚀 Testing QnA Embedding API Endpoint"
echo "API URL: $API_URL"
echo "Task ID: $TASK_ID"
echo ""

# Test 1: Health check for embedding worker
echo "1. Testing embedding worker health..."
curl -X POST "$API_URL/api/v1/queue/health-check/embedding" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -w "\nHTTP Status: %{http_code}\n" \
  | jq .

echo ""

# Test 2: Submit QnA embedding task
echo "2. Submitting QnA embedding task..."
RESPONSE=$(curl -s -X POST "$API_URL/api/v1/queue/submit/qna-embedding" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "taskId": "'$TASK_ID'",
    "userId": "'$USER_ID'",
    "datasetId": "'$DATASET_ID'",
    "qna_pairs": [
      {
        "question": "What are your business hours?",
        "answer": "We are open Monday to Friday, 9 AM to 5 PM.",
        "metadata": {"category": "general"}
      },
      {
        "question": "How do I contact support?",
        "answer": "You can reach support at support@company.com or call 1-800-SUPPORT.",
        "metadata": {"category": "support"}
      },
      {
        "question": "What is your return policy?",
        "answer": "We offer a 30-day return policy for all items in original condition.",
        "metadata": {"category": "policy"}
      }
    ],
    "batch_size": 50,
    "type": "qna_embedding"
  }' \
  -w "\nHTTP Status: %{http_code}")

echo "$RESPONSE" | jq .

# Extract task ID for status check
CELERY_TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id // empty')

echo ""

# Test 3: Check task status (if task ID was returned)
if [ ! -z "$CELERY_TASK_ID" ] && [ "$CELERY_TASK_ID" != "null" ]; then
  echo "3. Checking task status for task ID: $CELERY_TASK_ID"
  sleep 2  # Wait a moment for task to be processed
  
  curl -X GET "$API_URL/api/v1/queue/task/$CELERY_TASK_ID" \
    -H "X-API-Key: $API_KEY" \
    -w "\nHTTP Status: %{http_code}\n" \
    | jq .
else
  echo "3. ⚠️  No task ID returned, skipping status check"
fi

echo ""

# Test 4: List tasks in embedding queue
echo "4. Listing tasks in embedding.qna queue..."
curl -X GET "$API_URL/api/v1/queue/list?queue_name=embedding.qna" \
  -H "X-API-Key: $API_KEY" \
  -w "\nHTTP Status: %{http_code}\n" \
  | jq .

echo ""

# Test 5: Get queue statistics
echo "5. Getting embedding.qna queue statistics..."
curl -X GET "$API_URL/api/v1/queue/stats?queue_name=embedding.qna" \
  -H "X-API-Key: $API_KEY" \
  -w "\nHTTP Status: %{http_code}\n" \
  | jq .

echo ""
echo "🎉 QnA embedding endpoint testing completed!"
echo ""
echo "Next steps:"
echo "- Check your worker logs to see task processing"
echo "- Verify embeddings are stored in the bot.faq table"
echo "- Monitor queue statistics for processing metrics"