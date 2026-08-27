#!/usr/bin/env python3
"""
Test script for PDF embedding worker

This script tests the PDF document embedding functionality:
1. Health check
2. Chunking strategies test
3. Submit PDF embedding task
4. Monitor task progress

Usage:
    python scripts/test_pdf_embedding.py
"""
import sys
import os
import json
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.workers.pdf_embedding_tasks import (
    health_check_pdf_embedding,
    test_pdf_chunking,
    process_pdf_embedding
)


def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def test_health():
    """Test PDF embedding worker health."""
    print_header("Test 1: Worker Health Check")
    
    try:
        result = health_check_pdf_embedding.apply_async(queue='embedding.pdf')
        response = result.get(timeout=10)
        
        print("✓ Worker is healthy!")
        print(json.dumps(response, indent=2))
        return True
    except Exception as e:
        print(f"✗ Health check failed: {str(e)}")
        return False


def test_chunking_strategies():
    """Test different chunking strategies."""
    print_header("Test 2: Chunking Strategies")
    
    test_text = """
    Chapter 1: Introduction
    
    This is a sample document for testing PDF chunking strategies.
    The document contains multiple paragraphs and sections.
    
    Section 1.1: Background
    
    Lorem ipsum dolor sit amet, consectetur adipiscing elit. 
    Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
    Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.
    
    Section 1.2: Objectives
    
    The main objectives of this document are:
    1. Test recursive chunking with hierarchical separators
    2. Test fixed-size chunking with overlap
    3. Test page-based chunking
    
    Each strategy has its own advantages and use cases.
    """ * 10  # Repeat to create larger document
    
    strategies = [
        {
            "name": "Recursive (Default)",
            "strategy": "recursive",
            "chunk_size": 500,
            "chunk_overlap": 100
        },
        {
            "name": "Fixed Size",
            "strategy": "fixed",
            "chunk_size": 500,
            "chunk_overlap": 100
        },
        {
            "name": "Page-based",
            "strategy": "page",
            "chunk_size": 0,
            "chunk_overlap": 0
        }
    ]
    
    for config in strategies:
        print(f"\n--- Testing {config['name']} Strategy ---")
        
        try:
            result = test_pdf_chunking.apply_async(
                kwargs={
                    "test_text": test_text,
                    "chunk_size": config["chunk_size"],
                    "chunk_overlap": config["chunk_overlap"],
                    "strategy": config["strategy"]
                },
                queue='embedding.pdf'
            )
            
            response = result.get(timeout=30)
            
            if response["status"] == "success":
                print(f"✓ {config['name']} chunking successful")
                print(f"  Input length: {response['input_length']} chars")
                print(f"  Chunks created: {response['num_chunks']}")
                print(f"  Strategy: {response['strategy']}")
                print(f"\n  Sample chunks:")
                for chunk in response.get('sample_chunks', []):
                    print(f"    - Chunk {chunk['index']}: {chunk['size']} chars")
                    print(f"      Preview: {chunk['text'][:80]}...")
            else:
                print(f"✗ Chunking failed: {response.get('message')}")
        except Exception as e:
            print(f"✗ Error testing {config['name']}: {str(e)}")


def test_pdf_embedding_task():
    """Test PDF embedding task submission."""
    print_header("Test 3: PDF Embedding Task")
    
    # Sample payload
    payload = {
        "taskId": "test_pdf_embed_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
        "userId": "test_user",
        "datasetId": "b993df02-5048-465a-8f69-e3bb00d507f3",
        "type": "pdf",
        "documents": [
            {
                "title": "Test Document - Sample Manual",
                "file_name": "test_manual.pdf",
                "file_url": "https://example.com/test_manual.pdf",
                "metadata": {
                    "category": "testing",
                    "language": "en",
                    "test": True
                }
            }
        ],
        "chunking_config": {
            "strategy": "recursive",
            "chunk_size": 1000,
            "chunk_overlap": 200
        }
    }
    
    print("Payload:")
    print(json.dumps(payload, indent=2))
    print("\n⚠️  NOTE: This will fail because PDF extraction is not implemented yet.")
    print("   To enable: Install pypdf2/pdfplumber and implement extraction in pdf_processor.py")
    print("\nSubmitting task...")
    
    try:
        result = process_pdf_embedding.apply_async(
            args=[payload],
            queue='embedding.pdf'
        )
        
        print(f"✓ Task submitted: {result.id}")
        print("  Waiting for result (timeout: 60s)...")
        
        response = result.get(timeout=60)
        
        print("\n✓ Task completed!")
        print(json.dumps(response, indent=2))
        
        # Print summary
        if response.get("status") == "success":
            print(f"\n📊 Summary:")
            print(f"  Documents processed: {response.get('documents_processed')}/{response.get('total_documents')}")
            print(f"  Total chunks created: {response.get('total_chunks_created')}")
            print(f"  Processing time: {response.get('processing_time_ms')}ms")
            print(f"  Strategy: {response.get('chunking_strategy')}")
        
    except Exception as e:
        print(f"\n✗ Task failed: {str(e)}")
        print("\nExpected behavior: Task will fail because PDF extraction is not implemented.")
        print("This is normal for testing without actual PDF files.")


def main():
    """Run all tests."""
    print("=" * 70)
    print(" PDF EMBEDDING WORKER TEST SUITE")
    print("=" * 70)
    print(f" Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Test 1: Health Check
    health_ok = test_health()
    if not health_ok:
        print("\n⚠️  Worker not healthy. Make sure the worker is running:")
        print("   docker-compose up -d celery_worker_pdf_embedding")
        print("\nOr start manually:")
        print("   celery -A app.workers.celery_app worker --loglevel=info --queues=embedding.pdf")
        return
    
    # Test 2: Chunking Strategies
    test_chunking_strategies()
    
    # Test 3: PDF Embedding Task
    test_pdf_embedding_task()
    
    # Final Summary
    print_header("Test Suite Complete")
    print("\n✅ All tests completed!")
    print("\nNext steps:")
    print("1. Implement PDF extraction in app/services/pdf_processor.py")
    print("2. Install PDF libraries: pip install pypdf2 pdfplumber pymupdf")
    print("3. Upload actual PDF files to Azure Blob Storage")
    print("4. Submit real PDF embedding tasks from your backend")
    print("\nDocumentation: docs/PDF_EMBEDDING_WORKER.md")


if __name__ == "__main__":
    main()
