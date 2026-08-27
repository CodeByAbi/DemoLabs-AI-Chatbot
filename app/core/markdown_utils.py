"""
Markdown Utilities

Provides utility functions for cleaning and formatting markdown content.
"""
import re
from typing import Optional


def clean_markdown_headings(text: str) -> str:
    """
    Remove bold syntax (**) from markdown headings.
    
    Converts patterns like:
    - ### **Title** → ### Title
    - ## **Section** → ## Section
    - # **Main** → # Main
    
    Args:
        text: Input text with potential bold headings
        
    Returns:
        Text with cleaned headings (bold syntax removed)
        
    Examples:
        >>> clean_markdown_headings("### **Introduction**\\nSome text")
        '### Introduction\\nSome text'
        
        >>> clean_markdown_headings("## **Chapter 1**\\n### **Section 1.1**")
        '## Chapter 1\\n### Section 1.1'
    """
    if not text:
        return text
    
    # Pattern to match markdown headings with bold syntax
    # Matches: # **text**, ## **text**, ### **text**, etc.
    pattern = r'^(#{1,6})\s+\*\*(.*?)\*\*\s*$'
    
    # Replace on each line
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Check if line is a heading with bold
        match = re.match(pattern, line)
        if match:
            # Extract heading level and content
            heading_level = match.group(1)
            content = match.group(2)
            # Reconstruct without bold
            cleaned_line = f"{heading_level} {content}"
            cleaned_lines.append(cleaned_line)
        else:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def clean_markdown_code_blocks(text: str) -> str:
    """
    Remove markdown code block syntax from text.
    
    Removes:
    - ```sql ... ```
    - ``` ... ```
    - Leading/trailing code block markers
    
    Args:
        text: Input text with potential code blocks
        
    Returns:
        Text with code block markers removed
    """
    if not text:
        return text
    
    text = text.strip()
    
    # Remove markdown code blocks if present
    if text.startswith("```sql"):
        text = text[6:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    
    return text.strip()


def clean_markdown_formatting(text: str, clean_headings: bool = True, clean_code_blocks: bool = True) -> str:
    """
    Clean various markdown formatting issues from text.
    
    Args:
        text: Input text to clean
        clean_headings: Whether to clean bold syntax from headings
        clean_code_blocks: Whether to remove code block markers
        
    Returns:
        Cleaned text
    """
    if not text:
        return text
    
    result = text
    
    if clean_headings:
        result = clean_markdown_headings(result)
    
    if clean_code_blocks:
        result = clean_markdown_code_blocks(result)
    
    return result
