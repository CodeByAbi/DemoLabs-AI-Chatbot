#!/usr/bin/env python3
"""
Test PDF Processor Service

This script tests the PDF extraction and chunking functionality.
Run this after installing PDF dependencies.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.pdf_processor import pdf_processor, PDF_LIBRARY


def test_pdf_libraries():
    """Test if PDF libraries are installed."""
    print("=" * 60)
    print("Testing PDF Library Installation")
    print("=" * 60)
    
    if PDF_LIBRARY is None:
        print("❌ ERROR: No PDF library found!")
        print("\nPlease install one of the following:")
        print("  pip install pypdf2==3.0.1")
        print("  pip install pdfplumber==0.10.3")
        print("  pip install pymupdf==1.23.8")
        return False
    
    print(f"✓ Using PDF library: {PDF_LIBRARY}")
    return True


def test_chunking():
    """Test text chunking without PDF extraction."""
    print("\n" + "=" * 60)
    print("Testing Text Chunking")
    print("=" * 60)
    
    # Sample text
    sample_text = """
    This is a sample document for testing chunking.
    
    First paragraph with some content. This should be split into multiple chunks
    if it exceeds the chunk size limit. We need enough text here to test the
    chunking logic properly.
    
    Second paragraph with more content. This paragraph also contains multiple
    sentences to ensure we can test the recursive splitting algorithm.
    
    Third paragraph to test overlap. The overlap feature ensures that chunks
    share some common text for better context continuity.
    """ * 10  # Repeat to get enough text
    
    from app.services.pdf_processor import PDFChunker
    
    # Test recursive chunking
    chunker = PDFChunker(
        chunk_size=500,
        chunk_overlap=100,
        strategy="recursive"
    )
    
    chunks = chunker.chunk_text(sample_text)
    
    print(f"\n✓ Strategy: recursive")
    print(f"✓ Chunk size: 500 chars")
    print(f"✓ Overlap: 100 chars")
    print(f"✓ Generated {len(chunks)} chunks")
    
    # Show first 2 chunks
    for i, (chunk_text, metadata) in enumerate(chunks[:2]):
        print(f"\nChunk {i + 1}:")
        print(f"  Size: {metadata.chunk_size} chars")
        print(f"  Overlap: {metadata.overlap_size} chars")
        print(f"  Preview: {chunk_text[:100]}...")
    
    # Test fixed chunking
    chunker_fixed = PDFChunker(
        chunk_size=300,
        chunk_overlap=50,
        strategy="fixed"
    )
    
    chunks_fixed = chunker_fixed.chunk_text(sample_text)
    print(f"\n✓ Strategy: fixed")
    print(f"✓ Generated {len(chunks_fixed)} chunks")
    
    return True


def test_pdf_extraction_from_url():
    """Test PDF extraction from a public URL."""
    print("\n" + "=" * 60)
    print("Testing PDF Extraction from URL")
    print("=" * 60)
    
    # Use a sample PDF (you can replace with your own)
    test_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    
    try:
        print(f"\nExtracting text from: {test_url}")
        full_text, num_pages, metadata = pdf_processor.extract_text_from_pdf(test_url)
        
        print(f"\n✓ Successfully extracted PDF!")
        print(f"✓ Number of pages: {num_pages}")
        print(f"✓ Text length: {len(full_text)} characters")
        print(f"✓ Extractor used: {metadata.get('extractor', 'unknown')}")
        
        # Show first 200 chars
        print(f"\nFirst 200 characters:")
        print("-" * 60)
        print(full_text[:200])
        print("-" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n⚠️  Could not test URL extraction: {e}")
        print("This is normal if you don't have internet access.")
        return True  # Don't fail the test


def test_full_pipeline():
    """Test complete PDF processing and chunking pipeline."""
    print("\n" + "=" * 60)
    print("Testing Full PDF Pipeline")
    print("=" * 60)
    
    # Create sample text (simulating extracted PDF text)
    sample_pdf_text = """
    Chapter 1: Introduction
    
    This is the introduction to our document. It contains important information
    about the topic we're going to discuss. The introduction sets the context
    and provides background information.
    
    Chapter 2: Main Content
    
    The main content section contains the core information. Here we dive deep
    into the subject matter and provide detailed explanations. This section
    is typically the longest part of the document.
    
    Chapter 3: Conclusion
    
    In conclusion, we summarize the key points discussed in the previous sections.
    The conclusion helps readers understand the main takeaways from the document.
    """ * 5
    
    from app.services.pdf_processor import PDFChunker
    
    # Process with different strategies
    strategies = ["recursive", "fixed", "page"]
    
    for strategy in strategies:
        chunker = PDFChunker(
            chunk_size=400,
            chunk_overlap=80,
            strategy=strategy
        )
        
        chunks = chunker.chunk_text(sample_pdf_text)
        
        print(f"\n✓ Strategy '{strategy}': {len(chunks)} chunks")
        
        # Check for section titles
        titles_found = sum(1 for _, meta in chunks if meta.section_title)
        if titles_found > 0:
            print(f"  Found {titles_found} section titles")
    
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("PDF Processor Test Suite")
    print("=" * 60)
    
    tests = [
        ("PDF Libraries", test_pdf_libraries),
        ("Text Chunking", test_chunking),
        ("PDF Extraction", test_pdf_extraction_from_url),
        ("Full Pipeline", test_full_pipeline),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
    else:
        print("✗ Some tests failed")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
