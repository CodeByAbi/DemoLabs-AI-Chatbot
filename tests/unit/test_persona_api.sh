#!/bin/bash
# Persona Preview API - cURL Command Examples
# Make this file executable: chmod +x scripts/test_persona_api.sh

# Configuration
BASE_URL="http://localhost:8000"
PERSONA_ID="123e4567-e89b-12d3-a456-426614174000"  # Replace with actual ID

echo "============================================================"
echo "PERSONA PREVIEW API - cURL EXAMPLES"
echo "============================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test 1: Get Persona Preview (Default Question)
echo -e "${BLUE}Test 1: Get Persona Preview (Default)${NC}"
echo "GET $BASE_URL/api/v1/persona/preview/$PERSONA_ID"
echo ""
curl -X GET "$BASE_URL/api/v1/persona/preview/$PERSONA_ID" \
  -H "Content-Type: application/json" \
  | jq '.'
echo ""
echo ""

# Test 2: Get Persona Details
echo -e "${BLUE}Test 2: Get Persona Details${NC}"
echo "GET $BASE_URL/api/v1/persona/$PERSONA_ID"
echo ""
curl -X GET "$BASE_URL/api/v1/persona/$PERSONA_ID" \
  -H "Content-Type: application/json" \
  | jq '.'
echo ""
echo ""

# Test 3: Get Custom Persona Preview
echo -e "${BLUE}Test 3: Get Custom Persona Preview${NC}"
echo "POST $BASE_URL/api/v1/persona/preview/$PERSONA_ID/custom"
echo ""
curl -X POST "$BASE_URL/api/v1/persona/preview/$PERSONA_ID/custom" \
  -H "Content-Type: application/json" \
  -d '{
    "custom_question": "What tools do you use for data analysis?"
  }' \
  | jq '.'
echo ""
echo ""

# Test 4: Health Check
echo -e "${BLUE}Test 4: Health Check${NC}"
echo "GET $BASE_URL/health"
echo ""
curl -X GET "$BASE_URL/health" \
  -H "Content-Type: application/json" \
  | jq '.'
echo ""
echo ""

echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}Tests completed!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "Note: Replace PERSONA_ID variable with an actual persona UUID"
echo "      You can get a persona ID by running:"
echo "      python scripts/test_persona_preview.py"
