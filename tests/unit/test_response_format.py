#!/usr/bin/env python3
"""
Test script for the updated standardized response format
Tests that both question and answer are included in the response
"""
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/app')

from app.workers.chat_tasks import build_standardized_response


def test_response_format():
    """Test that the response includes both question and answer"""
    
    print("=" * 70)
    print("Testing Updated Standardized Response Format")
    print("=" * 70)
    print()
    
    # Test data
    message_data = {
        "user_id": "user-123",
        "message": "What is the refund policy?",
        "session_id": "session-456",
        "conversation_id": "conv-789",
        "persona_id": "persona-abc",
        "dataset_id": "dataset-xyz",
        "timezone": "UTC",
        "locale": "en_US",
        "channel": "web"
    }
    
    # Build success response
    print("Building success response...")
    response = build_standardized_response(
        status="success",
        message_data=message_data,
        response_text="We offer a 30-day money-back guarantee on all purchases.",
        task_id="task-123",
        quick_replies=[
            {"label": "Ask More", "value": "ask_more"},
            {"label": "Contact Support", "value": "contact_support"}
        ],
        intent="refund_policy",
        entities={"topic": "refund"},
        confidence_scores={
            "intent": 0.95,
            "response": 0.88,
            "relevance": 0.92
        },
        sources=[
            {
                "question": "What is your refund policy?",
                "answer": "We offer 30-day money-back guarantee...",
                "similarity": 0.95,
                "id": "faq-123"
            }
        ],
        suggestions=["Can I get a partial refund?", "How long does refund take?"],
        metrics={
            "processingTimeMs": 1250,
            "llmLatencyMs": 800,
            "retrievalLatencyMs": 150,
            "totalTokens": 350,
            "promptTokens": 200,
            "completionTokens": 150
        }
    )
    
    # Print formatted response
    print("\n✅ Success Response:")
    print(json.dumps(response, indent=2, ensure_ascii=False))
    print()
    
    # Validate structure
    print("Validating response structure...")
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Status is success
    tests_total += 1
    if response["status"] == "success":
        print("  ✅ Status is 'success'")
        tests_passed += 1
    else:
        print("  ❌ Status is not 'success'")
    
    # Test 2: Message has question field
    tests_total += 1
    if "question" in response["message"]:
        print("  ✅ Message has 'question' field")
        tests_passed += 1
    else:
        print("  ❌ Message missing 'question' field")
    
    # Test 3: Message has answer field
    tests_total += 1
    if "answer" in response["message"]:
        print("  ✅ Message has 'answer' field")
        tests_passed += 1
    else:
        print("  ❌ Message missing 'answer' field")
    
    # Test 4: Question matches original message
    tests_total += 1
    if response["message"]["question"] == message_data["message"]:
        print("  ✅ Question matches original message")
        tests_passed += 1
    else:
        print("  ❌ Question doesn't match original message")
    
    # Test 5: Answer is correct
    tests_total += 1
    if response["message"]["answer"] == "We offer a 30-day money-back guarantee on all purchases.":
        print("  ✅ Answer is correct")
        tests_passed += 1
    else:
        print("  ❌ Answer is incorrect")
    
    # Test 6: Backward compatibility - text field exists
    tests_total += 1
    if "text" in response["message"]:
        print("  ✅ Backward compatibility: 'text' field exists")
        tests_passed += 1
    else:
        print("  ❌ Backward compatibility: 'text' field missing")
    
    # Test 7: Text equals answer
    tests_total += 1
    if response["message"].get("text") == response["message"].get("answer"):
        print("  ✅ 'text' field equals 'answer' field")
        tests_passed += 1
    else:
        print("  ❌ 'text' field doesn't equal 'answer' field")
    
    # Test 8: Metadata is complete
    tests_total += 1
    required_metadata = ["sessionId", "personaId", "datasetId", "conversationId", 
                         "userId", "timestamp", "taskId"]
    if all(key in response["metadata"] for key in required_metadata):
        print("  ✅ All required metadata fields present")
        tests_passed += 1
    else:
        print("  ❌ Some metadata fields missing")
    
    # Test 9: Confidence scores present
    tests_total += 1
    if "confidence" in response and all(
        key in response["confidence"] 
        for key in ["intentConfidence", "responseConfidence", "relevanceScore"]
    ):
        print("  ✅ All confidence scores present")
        tests_passed += 1
    else:
        print("  ❌ Some confidence scores missing")
    
    # Test 10: Sources present
    tests_total += 1
    if "sources" in response and len(response["sources"]) > 0:
        print("  ✅ Sources present")
        tests_passed += 1
    else:
        print("  ❌ Sources missing or empty")
    
    print()
    print(f"Tests passed: {tests_passed}/{tests_total}")
    print()
    
    # Test error response
    print("\nBuilding error response...")
    error_response = build_standardized_response(
        status="error",
        message_data=message_data,
        response_text="",
        task_id="task-456",
        error_message="Failed to connect to database"
    )
    
    print("\n❌ Error Response:")
    print(json.dumps(error_response, indent=2, ensure_ascii=False))
    print()
    
    # Validate error response
    tests_total += 1
    if error_response["status"] == "error" and "error" in error_response:
        print("  ✅ Error response structure is correct")
        tests_passed += 1
    else:
        print("  ❌ Error response structure is incorrect")
    
    print()
    print("=" * 70)
    print(f"Final Result: {tests_passed}/{tests_total} tests passed")
    print("=" * 70)
    
    if tests_passed == tests_total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {tests_total - tests_passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = test_response_format()
    sys.exit(exit_code)
