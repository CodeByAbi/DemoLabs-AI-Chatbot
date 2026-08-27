#!/usr/bin/env python3
"""
Test script for Context Management with Chat History

This script tests the context management layer that provides:
- Chat history storage in Redis
- Conversation context building
- Enhanced question generation for follow-ups
- Multi-turn conversation support

Usage:
    python scripts/test_context_management.py
"""

import sys
import os
import uuid
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.context_manager import context_manager


def test_basic_history():
    """Test basic chat history storage and retrieval."""
    print("=" * 80)
    print("TEST 1: Basic Chat History Storage and Retrieval")
    print("=" * 80)
    
    session_id = f"test_session_{uuid.uuid4().hex[:8]}"
    user_id = "test_user_001"
    
    print(f"Session ID: {session_id}")
    print(f"User ID: {user_id}")
    print()
    
    # Add user message
    print("1. Adding user message...")
    success = context_manager.add_message_to_history(
        session_id=session_id,
        user_id=user_id,
        role="user",
        message="What are your business hours?",
        metadata={"intent": "qna_search", "timestamp": datetime.utcnow().isoformat()}
    )
    print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    # Add assistant response
    print("\n2. Adding assistant response...")
    success = context_manager.add_message_to_history(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        message="We are open Monday to Friday, 9 AM to 5 PM.",
        metadata={"sources_count": 1, "confidence": 0.95}
    )
    print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    # Retrieve history
    print("\n3. Retrieving chat history...")
    history = context_manager.get_chat_history(session_id, user_id, max_messages=10)
    print(f"   Retrieved {len(history)} messages:")
    for i, msg in enumerate(history, 1):
        print(f"   [{i}] {msg['role']}: {msg['content'][:50]}...")
    
    # Get stats
    print("\n4. Getting session stats...")
    stats = context_manager.get_session_stats(session_id, user_id)
    print(f"   Message count: {stats['message_count']}")
    print(f"   Exists: {stats['exists']}")
    print(f"   TTL: {stats.get('ttl_seconds', 'N/A')} seconds")
    
    print("\n")
    return session_id, user_id


def test_multi_turn_conversation(session_id: str, user_id: str):
    """Test multi-turn conversation with context building."""
    print("=" * 80)
    print("TEST 2: Multi-Turn Conversation Context")
    print("=" * 80)
    print(f"Session ID: {session_id}")
    print()
    
    # Simulate a conversation
    conversation = [
        ("user", "Tell me about your products"),
        ("assistant", "We offer a wide range of software solutions including..."),
        ("user", "What about pricing?"),
        ("assistant", "Our pricing starts at $99/month for the basic plan..."),
        ("user", "Can I get a discount?"),
        ("assistant", "Yes, we offer 20% discount for annual subscriptions..."),
    ]
    
    print("1. Simulating conversation...")
    for role, message in conversation:
        context_manager.add_message_to_history(
            session_id=session_id,
            user_id=user_id,
            role=role,
            message=message
        )
        print(f"   Added: {role}: {message[:60]}...")
    
    # Build conversation context
    print("\n2. Building conversation context...")
    current_question = "And what about enterprise plans?"
    context_string, history = context_manager.build_conversation_context(
        session_id=session_id,
        user_id=user_id,
        current_question=current_question,
        max_history=5
    )
    
    print(f"\n   Context built ({len(history)} messages in context):")
    print("   " + "-" * 76)
    for line in context_string.split('\n')[:10]:  # Show first 10 lines
        print(f"   {line}")
    if len(context_string.split('\n')) > 10:
        print(f"   ... ({len(context_string.split('\n')) - 10} more lines)")
    print("   " + "-" * 76)
    
    print("\n")


def test_enhanced_question(session_id: str, user_id: str):
    """Test enhanced question generation for follow-ups."""
    print("=" * 80)
    print("TEST 3: Enhanced Question for Follow-ups")
    print("=" * 80)
    print(f"Session ID: {session_id}")
    print()
    
    # Add context messages
    print("1. Adding context messages...")
    context_manager.add_message_to_history(
        session_id=session_id,
        user_id=user_id,
        role="user",
        message="What is the architecture of your system?"
    )
    context_manager.add_message_to_history(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        message="Our system uses a microservices architecture with Docker containers..."
    )
    
    # Test follow-up questions
    follow_up_questions = [
        "How does it work?",
        "What about scalability?",
        "Can you explain this?",
        "Tell me more about the database design"  # Not a follow-up
    ]
    
    print("\n2. Testing enhanced question generation...")
    for question in follow_up_questions:
        enhanced = context_manager.build_enhanced_question(
            session_id=session_id,
            user_id=user_id,
            current_question=question,
            max_history=3
        )
        
        is_enhanced = enhanced != question
        print(f"\n   Original:  {question}")
        print(f"   Enhanced:  {enhanced if is_enhanced else '(no enhancement needed)'}")
        print(f"   Status:    {'🔄 Enhanced' if is_enhanced else '✓ Standalone'}")
    
    print("\n")


def test_context_summary(session_id: str, user_id: str):
    """Test context summary storage and retrieval."""
    print("=" * 80)
    print("TEST 4: Context Summary Storage")
    print("=" * 80)
    print(f"Session ID: {session_id}")
    print()
    
    # Store summary
    print("1. Storing context summary...")
    summary = {
        "main_topic": "product_inquiry",
        "sub_topics": ["pricing", "features", "enterprise"],
        "user_intent": "purchase_consideration",
        "sentiment": "positive",
        "key_entities": ["pricing", "discount", "enterprise_plan"]
    }
    
    success = context_manager.store_context_summary(
        session_id=session_id,
        user_id=user_id,
        summary=summary,
        ttl_hours=24
    )
    print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    # Retrieve summary
    print("\n2. Retrieving context summary...")
    retrieved_summary = context_manager.get_context_summary(session_id, user_id)
    
    if retrieved_summary:
        print("   ✅ Summary retrieved:")
        for key, value in retrieved_summary.items():
            print(f"      - {key}: {value}")
    else:
        print("   ❌ No summary found")
    
    print("\n")


def test_session_management(session_id: str, user_id: str):
    """Test session management (clear, stats)."""
    print("=" * 80)
    print("TEST 5: Session Management")
    print("=" * 80)
    print(f"Session ID: {session_id}")
    print()
    
    # Get stats before clear
    print("1. Session stats before clear...")
    stats = context_manager.get_session_stats(session_id, user_id)
    print(f"   Message count: {stats['message_count']}")
    print(f"   Exists: {stats['exists']}")
    
    # Clear session
    print("\n2. Clearing session history...")
    success = context_manager.clear_session_history(session_id, user_id)
    print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    # Get stats after clear
    print("\n3. Session stats after clear...")
    stats = context_manager.get_session_stats(session_id, user_id)
    print(f"   Message count: {stats['message_count']}")
    print(f"   Exists: {stats['exists']}")
    
    print("\n")


def main():
    """Main test function."""
    print("\n")
    print("🚀 CONTEXT MANAGEMENT TESTING SUITE")
    print("Testing Chat History and Conversation Context with Redis")
    print("\n")
    
    try:
        # Test 1: Basic history
        session_id, user_id = test_basic_history()
        
        # Test 2: Multi-turn conversation
        test_multi_turn_conversation(session_id, user_id)
        
        # Test 3: Enhanced questions
        test_enhanced_question(session_id, user_id)
        
        # Test 4: Context summary
        test_context_summary(session_id, user_id)
        
        # Test 5: Session management
        test_session_management(session_id, user_id)
        
        print("=" * 80)
        print("✅ All tests completed!")
        print("=" * 80)
        print()
        print("Context Management Features Demonstrated:")
        print("  ✓ Chat history storage in Redis")
        print("  ✓ Multi-turn conversation tracking")
        print("  ✓ Conversation context building")
        print("  ✓ Enhanced question generation for follow-ups")
        print("  ✓ Context summary storage and retrieval")
        print("  ✓ Session statistics and management")
        print("  ✓ Automatic TTL expiration (24 hours)")
        print()
        print("Integration Benefits:")
        print("  • Better understanding of follow-up questions")
        print("  • Improved context-aware RAG retrieval")
        print("  • Conversation continuity across multiple turns")
        print("  • User intent tracking over time")
        print("  • Enhanced user experience with contextual responses")
        print()
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
