#!/bin/bash

# Test script for PDF embedding endpoint
# This script tests the /api/v1/queue/submit/pdf-embedding endpoint

API_URL="http://localhost:8000"
API_KEY="your-api-key-here"  # Update with your actual API key
TASK_ID="embed_pdf_$(date +%s)"
USER_ID="test_user"
DATASET_ID="b993df02-5048-465a-8f69-e3bb00d507f3"  # Update with your dataset ID

echo "🚀 Testing PDF Embedding API Endpoint"
echo "API URL: $API_URL"
echo "Task ID: $TASK_ID"
echo ""

# Test 1: Health check for PDF embedding worker
echo "1. Testing PDF embedding worker health..."
curl -X POST "$API_URL/api/v1/queue/health-check/pdf-embedding" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -w "\nHTTP Status: %{http_code}\n" \
  | jq .

echo ""

# Test 2: Submit PDF embedding task
echo "2. Submitting PDF embedding task..."
RESPONSE=$(curl -s -X POST "$API_URL/api/v1/queue/submit/pdf-embedding" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "taskId": "'$TASK_ID'",
    "userId": "'$USER_ID'",
    "datasetId": "'$DATASET_ID'",
    "documents": [
      {
        "title": "Sample Technical Manual",
        "file_name": "technical_manual.pdf",
        "file_url": "https://storage.blob.core.windows.net/demo-lab/docs/sample.pdf",
        "metadata": {
          "category": "technical",
          "language": "en",
          "version": "2.0"
        }
      },
      {
        "title": "Product Guide",
        "file_name": "product_guide.pdf",
        "file_url": "https://storage.blob.core.windows.net/demo-lab/docs/guide.pdf",
        "metadata": {
          "category": "product",
          "language": "en"
        }
      }
    ],
    "chunking_config": {
      "strategy": "recursive",
      "chunk_size": 1000,
      "chunk_overlap": 200
    },
    "type": "pdf"
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

# Test 4: List tasks in PDF embedding queue
echo "4. Listing tasks in embedding.pdf queue..."
curl -X GET "$API_URL/api/v1/queue/list?queue_name=embedding.pdf" \
  -H "X-API-Key: $API_KEY" \
  -w "\nHTTP Status: %{http_code}\n" \
  | jq .

echo ""

# Test 5: Get queue statistics
echo "5. Getting embedding.pdf queue statistics..."
curl -X GET "$API_URL/api/v1/queue/stats?queue_name=embedding.pdf" \
  -H "X-API-Key: $API_KEY" \
  -w "\nHTTP Status: %{http_code}\n" \
  | jq .

echo ""

# Test 6: Test with different chunking strategies
echo "6. Testing with 'fixed' chunking strategy..."
curl -s -X POST "$API_URL/api/v1/queue/submit/pdf-embedding" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "taskId": "embed_pdf_fixed_'$(date +%s)'",
    "userId": "'$USER_ID'",
    "datasetId": "'$DATASET_ID'",
    "documents": [
      {
        "title": "Test Document - Fixed Chunking",
        "file_name": "test_fixed.pdf",
        "file_url": "https://storage.blob.core.windows.net/demo-lab/docs/test.pdf",
        "metadata": {"test": "fixed_chunking"}
      }
    ],
    "chunking_config": {
      "strategy": "fixed",
      "chunk_size": 500,
      "chunk_overlap": 100
    },
    "type": "pdf"
  }' \
  -w "\nHTTP Status: %{http_code}\n" \
  | jq .

echo ""

# Test 7: Test with page-based chunking
echo "7. Testing with 'page' chunking strategy..."
curl -s -X POST "$API_URL/api/v1/queue/submit/pdf-embedding" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "taskId": "embed_pdf_page_'$(date +%s)'",
    "userId": "'$USER_ID'",
    "datasetId": "'$DATASET_ID'",
    "documents": [
      {
        "title": "Test Document - Page Chunking",
        "file_name": "test_page.pdf",
        "file_url": "https://storage.blob.core.windows.net/demo-lab/docs/test.pdf",
        "metadata": {"test": "page_chunking"}
      }
    ],
    "chunking_config": {
      "strategy": "page",
      "chunk_size": 1000,
      "chunk_overlap": 0
    },
    "type": "pdf"
  }' \
  -w "\nHTTP Status: %{http_code}\n" \
  | jq .

echo ""
echo "🎉 PDF embedding endpoint testing completed!"
echo ""
echo "Next steps:"
echo "- Check your worker logs to see task processing"
echo "- Verify document chunks are stored in bot.document and bot.document_chunk tables"
echo "- Monitor queue statistics for processing metrics"
echo "- Use the embeddings for RAG (Retrieval Augmented Generation)"