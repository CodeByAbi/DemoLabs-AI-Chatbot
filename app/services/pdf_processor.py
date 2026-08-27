"""
PDF Processing Service with Advanced Chunking

This service handles PDF text extraction and intelligent chunking strategies
for optimal RAG performance.

Supported Chunking Strategies:
1. Recursive Character Splitting - Hierarchical splitting with overlap
2. Semantic Chunking - Split by semantic similarity
3. Fixed Size - Simple fixed-size chunks
4. Page-based - One chunk per page
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import re
import json
from io import BytesIO
import requests
from pathlib import Path

# Try to import PDF libraries (in order of preference)
PDF_LIBRARY = None

try:
    import pdfplumber
    PDF_LIBRARY = 'pdfplumber'
    logger = logging.getLogger(__name__)
    logger.info("Using pdfplumber for PDF extraction")
except ImportError:
    try:
        import PyPDF2
        PDF_LIBRARY = 'pypdf2'
        logger = logging.getLogger(__name__)
        logger.info("Using PyPDF2 for PDF extraction")
    except ImportError:
        logger = logging.getLogger(__name__)
        logger.warning("No PDF library found. Install pypdf2 or pdfplumber")

logger = logging.getLogger(__name__)


class DocumentChunkMetadata:
    """Metadata for a document chunk."""
    
    def __init__(
        self,
        chunk_index: int,
        page_number: Optional[int] = None,
        page_range: Optional[str] = None,
        section_title: Optional[str] = None,
        chunk_size: int = 0,
        overlap_size: int = 0
    ):
        self.chunk_index = chunk_index
        self.page_number = page_number
        self.page_range = page_range
        self.section_title = section_title
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size


class PDFChunker:
    """
    Advanced PDF chunking with multiple strategies.
    
    Strategies:
    - recursive: Hierarchical chunking with separators (paragraphs, sentences, words)
    - fixed: Fixed-size chunks with overlap
    - semantic: Semantic similarity-based chunking (requires embeddings)
    - page: One chunk per page
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        strategy: str = "recursive"
    ):
        """
        Initialize PDF chunker.
        
        Args:
            chunk_size: Target size for each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            strategy: Chunking strategy (recursive, fixed, semantic, page)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
        
        # Separators for recursive splitting (in order of preference)
        self.separators = [
            "\n\n\n",  # Multiple line breaks (sections)
            "\n\n",    # Double line breaks (paragraphs)
            "\n",      # Single line breaks
            ". ",      # Sentences
            "! ",      # Exclamations
            "? ",      # Questions
            "; ",      # Semicolons
            ", ",      # Commas
            " ",       # Spaces
            ""         # Characters
        ]
    
    def chunk_text(
        self,
        text: str,
        page_number: Optional[int] = None
    ) -> List[Tuple[str, DocumentChunkMetadata]]:
        """
        Chunk text using the configured strategy.
        
        Args:
            text: Text to chunk
            page_number: Page number for metadata
            
        Returns:
            List of tuples (chunk_text, metadata)
        """
        if self.strategy == "recursive":
            return self._recursive_chunk(text, page_number)
        elif self.strategy == "fixed":
            return self._fixed_chunk(text, page_number)
        elif self.strategy == "page":
            return self._page_chunk(text, page_number)
        else:
            logger.warning(f"Unknown strategy '{self.strategy}', falling back to recursive")
            return self._recursive_chunk(text, page_number)
    
    
    def _recursive_chunk(
        self,
        text: str,
        page_number: Optional[int] = None,
        separator_index: int = 0
    ) -> List[Tuple[str, DocumentChunkMetadata]]:
        """
        Recursively split text using hierarchical separators.
        
        This method tries to split on larger semantic units first (paragraphs),
        then falls back to smaller units (sentences, words) if needed.
        """
        chunks = []
        chunk_index = 0
        
        # Determine separators to use
        current_separators = self.separators[separator_index:]
        
        # Split text using separators
        splits = self._split_text_recursive(text, current_separators)
        
        # Merge splits into chunks
        current_chunk = []
        current_size = 0
        
        for split in splits:
            split_size = len(split)
            
            # If adding this split exceeds chunk_size, save current chunk
            if current_size + split_size > self.chunk_size and current_chunk:
                chunk_text = "".join(current_chunk).strip()
                if chunk_text:
                    if len(chunk_text) > self.chunk_size and separator_index < len(self.separators) - 1:
                        sub_chunks = self._recursive_chunk(
                            chunk_text,
                            page_number,
                            separator_index=separator_index + 1
                        )
                        chunks.extend(sub_chunks)
                        chunk_index += len(sub_chunks)
                    else:
                        metadata = DocumentChunkMetadata(
                            chunk_index=chunk_index,
                            page_number=page_number,
                            chunk_size=len(chunk_text),
                            overlap_size=self.chunk_overlap if chunk_index > 0 else 0
                        )
                        chunks.append((chunk_text, metadata))
                        chunk_index += 1
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0:
                    overlap_text = chunk_text[-self.chunk_overlap:]
                    current_chunk = [overlap_text, split]
                    current_size = len(overlap_text) + split_size
                else:
                    current_chunk = [split]
                    current_size = split_size
            else:
                current_chunk.append(split)
                current_size += split_size
        
        # Add remaining chunk
        if current_chunk:
            chunk_text = "".join(current_chunk).strip()
            if chunk_text:
                # If this single chunk is still too big, we need to split it further
                # even if it's a single block from the current separator
                if len(chunk_text) > self.chunk_size and separator_index < len(self.separators) - 1:
                    # Recursively split this oversized chunk with finer separators
                    sub_chunks = self._recursive_chunk(
                        chunk_text, 
                        page_number, 
                        separator_index=separator_index + 1
                    )
                    chunks.extend(sub_chunks)
                    chunk_index += len(sub_chunks)
                else:
                    metadata = DocumentChunkMetadata(
                        chunk_index=chunk_index,
                        page_number=page_number,
                        chunk_size=len(chunk_text),
                        overlap_size=self.chunk_overlap if chunk_index > 0 else 0
                    )
                    chunks.append((chunk_text, metadata))
        
        return chunks
    
    def _split_text_recursive(
        self,
        text: str,
        separators: List[str]
    ) -> List[str]:
        """
        Recursively split text using a hierarchy of separators.
        
        Args:
            text: Text to split
            separators: List of separators to try (in order)
            
        Returns:
            List of text splits
        """
        if not separators:
            return [text]
        
        separator = separators[0]
        remaining_separators = separators[1:]
        
        if separator == "":
            # Character-level split
            return list(text)
        
        splits = text.split(separator)
        
        # If we got good splits, return them (with separator preserved)
        if len(splits) > 1:
            result = []
            for i, split in enumerate(splits):
                if i < len(splits) - 1:
                    result.append(split + separator)
                else:
                    result.append(split)
            return result
        
        # Try next separator
        return self._split_text_recursive(text, remaining_separators)
    
    def _fixed_chunk(
        self,
        text: str,
        page_number: Optional[int] = None
    ) -> List[Tuple[str, DocumentChunkMetadata]]:
        """
        Split text into fixed-size chunks with overlap.
        
        Simple but effective for uniform documents.
        """
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                metadata = DocumentChunkMetadata(
                    chunk_index=chunk_index,
                    page_number=page_number,
                    chunk_size=len(chunk_text),
                    overlap_size=self.chunk_overlap if chunk_index > 0 else 0
                )
                chunks.append((chunk_text, metadata))
                chunk_index += 1
            
            # Move start position with overlap
            start = end - self.chunk_overlap
            if start <= 0:
                start = end
        
        return chunks
    
    def _page_chunk(
        self,
        text: str,
        page_number: Optional[int] = None
    ) -> List[Tuple[str, DocumentChunkMetadata]]:
        """
        Create one chunk for the entire page.
        
        Useful for page-level retrieval.
        """
        if not text.strip():
            return []
        
        metadata = DocumentChunkMetadata(
            chunk_index=0,
            page_number=page_number,
            chunk_size=len(text),
            overlap_size=0
        )
        
        return [(text.strip(), metadata)]
    
    def detect_section_title(self, text: str) -> Optional[str]:
        """
        Attempt to detect section/chapter title from text.
        
        Uses heuristics like:
        - All caps short lines
        - Lines ending with numbers (Chapter 1, Section 2.1)
        - Lines with specific keywords
        
        Args:
            text: Text to analyze
            
        Returns:
            Detected section title or None
        """
        lines = text.strip().split('\n')
        if not lines:
            return None
        
        first_line = lines[0].strip()
        
        # Check if first line looks like a title
        if len(first_line) < 100 and (
            first_line.isupper() or
            re.match(r'^(Chapter|Section|Part|Article)\s+\d+', first_line, re.IGNORECASE) or
            re.match(r'^\d+\.?\s+[A-Z]', first_line)
        ):
            return first_line
        
        return None


class PDFProcessor:
    """
    PDF processing service for text extraction and chunking.
    
    Supports multiple PDF libraries: pdfplumber, PyPDF2
    """
    
    def __init__(self):
        """Initialize PDF processor."""
        self.chunker = None
        if PDF_LIBRARY is None:
            raise ImportError(
                "No PDF library installed. Please install one of: "
                "pypdf2 or pdfplumber"
            )
    
    def _download_pdf_if_url(self, file_path: str) -> BytesIO:
        """
        Download PDF if file_path is a URL.
        
        Args:
            file_path: Local path or URL to PDF
            
        Returns:
            BytesIO object with PDF content
        """
        if file_path.startswith('http://') or file_path.startswith('https://'):
            logger.info(f"Downloading PDF from URL: {file_path}")
            response = requests.get(file_path, timeout=30)
            response.raise_for_status()
            return BytesIO(response.content)
        else:
            # Read local file
            with open(file_path, 'rb') as f:
                return BytesIO(f.read())
    
    def _extract_with_pdfplumber(self, pdf_bytes: BytesIO) -> Tuple[str, int, Dict[str, Any]]:
        """Extract text using pdfplumber (best for tables and complex layouts)."""
        import pdfplumber
        
        full_text = []
        metadata = {
            "extractor": "pdfplumber",
            "pages": []
        }
        
        with pdfplumber.open(pdf_bytes) as pdf:
            num_pages = len(pdf.pages)
            
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    page_text = page.extract_text() or ""
                    
                    # Extract tables for better structured data
                    tables = page.extract_tables()
                    if tables:
                        table_content = []
                        table_content.append("\n\n### Structured Table Content")
                        for table in tables:
                            for row in table:
                                # Clean None values and join with pipe
                                clean_row = [str(cell) if cell is not None else "" for cell in row]
                                row_text = " | ".join(clean_row)
                                table_content.append(row_text)
                        
                        # Append structured table content to page text
                        page_text += "\n".join(table_content)
                    
                    full_text.append(page_text)
                    
                    # Extract page metadata
                    page_metadata = {
                        "page_number": page_num,
                        "width": page.width,
                        "height": page.height,
                        "char_count": len(page_text)
                    }
                    metadata["pages"].append(page_metadata)
                    
                except Exception as e:
                    logger.warning(f"Error extracting page {page_num}: {e}")
                    full_text.append(f"[Error extracting page {page_num}]")
        
        return "\n\n".join(full_text), num_pages, metadata
    
    def _extract_with_pypdf2(self, pdf_bytes: BytesIO) -> Tuple[str, int, Dict[str, Any]]:
        """Extract text using PyPDF2 (lightweight, fast)."""
        import PyPDF2
        
        full_text = []
        metadata = {
            "extractor": "pypdf2",
            "pages": []
        }
        
        pdf_reader = PyPDF2.PdfReader(pdf_bytes)
        num_pages = len(pdf_reader.pages)
        
        # Extract PDF metadata
        if pdf_reader.metadata:
            metadata["pdf_metadata"] = {
                "title": pdf_reader.metadata.get('/Title', ''),
                "author": pdf_reader.metadata.get('/Author', ''),
                "subject": pdf_reader.metadata.get('/Subject', ''),
                "creator": pdf_reader.metadata.get('/Creator', '')
            }
        
        for page_num, page in enumerate(pdf_reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
                full_text.append(page_text)
                
                page_metadata = {
                    "page_number": page_num,
                    "char_count": len(page_text)
                }
                metadata["pages"].append(page_metadata)
                
            except Exception as e:
                logger.warning(f"Error extracting page {page_num}: {e}")
                full_text.append(f"[Error extracting page {page_num}]")
        
        return "\n\n".join(full_text), num_pages, metadata
    
    def extract_text_from_pdf(
        self,
        file_path: str
    ) -> Tuple[str, int, Dict[str, Any]]:
        """
        Extract text from PDF file using available PDF library.
        
        Args:
            file_path: Path to PDF file or URL
            
        Returns:
            Tuple of (full_text, number_of_pages, metadata)
        """
        try:
            # Download or read PDF
            pdf_bytes = self._download_pdf_if_url(file_path)
            
            # Extract using available library
            if PDF_LIBRARY == 'pdfplumber':
                return self._extract_with_pdfplumber(pdf_bytes)
            elif PDF_LIBRARY == 'pypdf2':
                return self._extract_with_pypdf2(pdf_bytes)
            else:
                raise ImportError(
                    "No PDF library available. Install pypdf2 or pdfplumber"
                )
                
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            raise
    
    def process_and_chunk_pdf(
        self,
        file_path: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        strategy: str = "recursive"
    ) -> Tuple[str, int, List[Tuple[str, DocumentChunkMetadata]]]:
        """
        Extract text from PDF and create chunks.
        
        Args:
            file_path: Path to PDF file
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
            strategy: Chunking strategy
            
        Returns:
            Tuple of (full_text, number_of_pages, chunks_with_metadata)
        """
        # Extract text from PDF
        full_text, num_pages, metadata = self.extract_text_from_pdf(file_path)
        
        # Clean markdown formatting in extracted text
        from app.core.markdown_utils import clean_markdown_headings
        full_text = clean_markdown_headings(full_text)
        
        # Initialize chunker
        self.chunker = PDFChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            strategy=strategy
        )
        
        # Create chunks
        chunks = self.chunker.chunk_text(full_text)
        
        # Detect section titles for chunks
        for chunk_text, chunk_metadata in chunks:
            section_title = self.chunker.detect_section_title(chunk_text)
            if section_title:
                chunk_metadata.section_title = section_title
        
        return full_text, num_pages, chunks


# Global instance
pdf_processor = PDFProcessor()
