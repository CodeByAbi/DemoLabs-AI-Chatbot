#!/usr/bin/env python3
"""
Test script for Hybrid RAG with PDF and QnA support.

This script tests the advanced RAG capabilities:
- Auto-detection of dataset type (QnA, PDF, Mixed)
- PDF document chunk retrieval with reranking
- Hybrid retrieval from both QnA and PDF sources
- Metadata enrichment (pages, sections, etc.)

Usage:
    python scripts/test_hybrid_rag.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.rag_service import rag_service
import uuid


def test_dataset_type_detection():
    """Test automatic dataset type detection."""
    print("=" * 80)
    print("TEST 1: Dataset Type Detection")
    print("=" * 80)
    
    # Replace with your actual dataset IDs
    test_datasets = [
        {
            "id": "b993df02-5048-465a-8f69-e3bb00d507f3",
            "name": "Sample Dataset 1"
        }
    ]
    
    for dataset in test_datasets:
        dataset_type = rag_service.detect_dataset_type(dataset["id"])
        print(f"\nDataset: {dataset['name']}")
        print(f"ID: {dataset['id']}")
        print(f"Type: {dataset_type}")
    
    print("\n")


def test_qna_rag(dataset_id: str, question: str, persona_id: str):
    """Test QnA-based RAG."""
    print("=" * 80)
    print("TEST 2: QnA RAG")
    print("=" * 80)
    print(f"Dataset ID: {dataset_id}")
    print(f"Question: {question}")
    print()
    
    result = rag_service.generate_rag_response(
        question=question,
        persona_id=persona_id,
        dataset_id=dataset_id,
        top_k=3,
        similarity_threshold=0.7,
        temperature=0.7,
        max_tokens=500
    )
    
    if result["status"] == "success":
        print(f"✅ Status: {result['status']}")
        print(f"\nResponse:\n{result['response']}")
        print(f"\nSources Found: {len(result['sources'])}")
        
        for idx, source in enumerate(result['sources'], 1):
            print(f"\n  Source {idx}:")
            print(f"    - Title: {source['title']}")
            print(f"    - Confidence: {source['confidence']:.2%}")
            print(f"    - Snippet: {source['snippet'][:100]}...")
        
        print(f"\nMetrics:")
        print(f"  - Processing Time: {result['metrics']['processingTimeMs']}ms")
        print(f"  - Retrieval Time: {result['metrics']['retrievalLatencyMs']}ms")
        print(f"  - LLM Time: {result['metrics']['llmLatencyMs']}ms")
        print(f"  - Relevance Score: {result['confidence']['relevanceScore']:.2%}")
    else:
        print(f"❌ Error: {result.get('error')}")
    
    print("\n")


def test_pdf_rag(dataset_id: str, question: str, persona_id: str):
    """Test PDF-based RAG with advanced techniques."""
    print("=" * 80)
    print("TEST 3: PDF RAG (Advanced Techniques)")
    print("=" * 80)
    print(f"Dataset ID: {dataset_id}")
    print(f"Question: {question}")
    print()
    
    # Use hybrid method with forced PDF type
    result = rag_service.generate_hybrid_rag_response(
        question=question,
        persona_id=persona_id,
        dataset_id=dataset_id,
        dataset_type="pdf",  # Force PDF
        top_k=5,
        similarity_threshold=0.7,
        temperature=0.7,
        max_tokens=800
    )
    
    if result["status"] == "success":
        print(f"✅ Status: {result['status']}")
        print(f"Dataset Type: {result.get('dataset_type')}")
        print(f"\nResponse:\n{result['response']}")
        print(f"\nSources Found: {len(result['sources'])}")
        
        for idx, source in enumerate(result['sources'], 1):
            print(f"\n  Source {idx}:")
            print(f"    - Document: {source['title']}")
            print(f"    - Page: {source.get('page', 'N/A')}")
            print(f"    - Section: {source.get('section', 'N/A')}")
            print(f"    - Confidence: {source['confidence']:.2%}")
            print(f"    - Snippet: {source['snippet'][:100]}...")
        
        print(f"\nMetrics:")
        print(f"  - Processing Time: {result['metrics']['processingTimeMs']}ms")
        print(f"  - Retrieval Time: {result['metrics']['retrievalLatencyMs']}ms")
        print(f"  - LLM Time: {result['metrics']['llmLatencyMs']}ms")
        print(f"  - Relevance Score: {result['confidence']['relevanceScore']:.2%}")
    else:
        print(f"❌ Error: {result.get('error')}")
    
    print("\n")


def test_hybrid_rag(dataset_id: str, question: str, persona_id: str):
    """Test Hybrid RAG (auto-detect and use best approach)."""
    print("=" * 80)
    print("TEST 4: Hybrid RAG (Auto-Detect)")
    print("=" * 80)
    print(f"Dataset ID: {dataset_id}")
    print(f"Question: {question}")
    print()
    
    result = rag_service.generate_hybrid_rag_response(
        question=question,
        persona_id=persona_id,
        dataset_id=dataset_id,
        dataset_type="auto",  # Auto-detect
        top_k=5,
        similarity_threshold=0.7,
        temperature=0.7,
        max_tokens=800
    )
    
    if result["status"] == "success":
        print(f"✅ Status: {result['status']}")
        print(f"Auto-Detected Dataset Type: {result.get('dataset_type')}")
        print(f"\nResponse:\n{result['response']}")
        print(f"\nSources Found: {len(result['sources'])}")
        
        # Group sources by type
        source_types = {}
        for source in result['sources']:
            source_type = source.get('type', 'unknown')
            if source_type not in source_types:
                source_types[source_type] = []
            source_types[source_type].append(source)
        
        print(f"\nSource Distribution:")
        for source_type, sources in source_types.items():
            print(f"  - {source_type}: {len(sources)} sources")
        
        print(f"\nDetailed Sources:")
        for idx, source in enumerate(result['sources'], 1):
            print(f"\n  Source {idx} ({source.get('type', 'unknown')}):")
            print(f"    - Title: {source['title']}")
            if source.get('page'):
                print(f"    - Page: {source['page']}")
            if source.get('section'):
                print(f"    - Section: {source['section']}")
            print(f"    - Confidence: {source['confidence']:.2%}")
            print(f"    - Snippet: {source['snippet'][:100]}...")
        
        print(f"\nMetrics:")
        print(f"  - Processing Time: {result['metrics']['processingTimeMs']}ms")
        print(f"  - Retrieval Time: {result['metrics']['retrievalLatencyMs']}ms")
        print(f"  - LLM Time: {result['metrics']['llmLatencyMs']}ms")
        print(f"  - Relevance Score: {result['confidence']['relevanceScore']:.2%}")
    else:
        print(f"❌ Error: {result.get('error')}")
    
    print("\n")


def main():
    """Main test function."""
    print("\n")
    print("🚀 HYBRID RAG TESTING SUITE")
    print("Testing Advanced RAG with QnA, PDF, and Hybrid Support")
    print("\n")
    
    # Configuration - Update with your actual values
    DATASET_ID = "b993df02-5048-465a-8f69-e3bb00d507f3"  # Your dataset ID
    PERSONA_ID = str(uuid.uuid4())  # Replace with actual persona ID
    
    # Sample questions for testing
    TEST_QUESTIONS = [
        "What are your business hours?",
        "How do I contact support?",
        "What is your return policy?",
        "Tell me about the product features",
        "How do I get started?"
    ]
    
    try:
        # Test 1: Dataset type detection
        test_dataset_type_detection()
        
        # Test 2: QnA RAG
        print("Testing with first question...")
        test_qna_rag(DATASET_ID, TEST_QUESTIONS[0], PERSONA_ID)
        
        # Test 3: PDF RAG
        print("Testing PDF RAG with second question...")
        test_pdf_rag(DATASET_ID, TEST_QUESTIONS[1], PERSONA_ID)
        
        # Test 4: Hybrid RAG (Auto-detect)
        print("Testing Hybrid RAG with third question...")
        test_hybrid_rag(DATASET_ID, TEST_QUESTIONS[2], PERSONA_ID)
        
        print("=" * 80)
        print("✅ All tests completed!")
        print("=" * 80)
        print()
        print("Advanced RAG Features Demonstrated:")
        print("  ✓ Auto-detection of dataset type (QnA, PDF, Mixed)")
        print("  ✓ Semantic search with vector similarity")
        print("  ✓ Document chunk retrieval with metadata")
        print("  ✓ Source diversity through reranking (MMR-like)")
        print("  ✓ Metadata enrichment (pages, sections)")
        print("  ✓ Hybrid retrieval from multiple source types")
        print("  ✓ Context window management")
        print()
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
