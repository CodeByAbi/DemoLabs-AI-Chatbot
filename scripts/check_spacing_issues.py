"""
Script to check for spacing issues in text responses
Usage: python scripts/check_spacing_issues.py
"""
import re
import sys
from typing import Dict, List


def check_spacing_issues(text: str) -> Dict:
    """
    Check for common spacing issues in text.
    
    Args:
        text: Text to check
        
    Returns:
        Dict with issue analysis
    """
    issues = []
    examples = {}
    
    # Pattern 1: lowercase followed by uppercase (e.g., "areaYang")
    pattern1 = re.findall(r'([a-z])([A-Z])', text)
    if pattern1:
        issues.append(f"Missing space between lowercase-uppercase: {len(pattern1)} cases")
        examples['lowercase_uppercase'] = pattern1[:5]
    
    # Pattern 2: letter followed by number without space (e.g., "Step1")
    pattern2 = re.findall(r'([a-zA-Z])(\d)', text)
    if pattern2:
        issues.append(f"Missing space before numbers: {len(pattern2)} cases")
        examples['letter_number'] = pattern2[:5]
    
    # Pattern 3: punctuation followed by letter without space (e.g., "word.Another")
    pattern3 = re.findall(r'([.!?:,])([A-Za-z])', text)
    if pattern3:
        issues.append(f"Missing space after punctuation: {len(pattern3)} cases")
        examples['punctuation_letter'] = pattern3[:5]
    
    # Pattern 4: Check for excessive newlines
    excessive_newlines = text.count('\n\n\n')
    if excessive_newlines > 0:
        issues.append(f"Excessive newlines (3+): {excessive_newlines} occurrences")
    
    # Pattern 5: Check for missing newlines (very long lines)
    lines = text.split('\n')
    long_lines = [i for i, line in enumerate(lines) if len(line) > 200]
    if long_lines:
        issues.append(f"Very long lines (>200 chars): {len(long_lines)} lines")
        examples['long_lines'] = long_lines[:3]
    
    return {
        "has_issues": len(issues) > 0,
        "issues": issues,
        "examples": examples,
        "total_issues": len(pattern1) + len(pattern2) + len(pattern3),
        "text_length": len(text),
        "newline_count": text.count('\n')
    }


def print_analysis(text: str, label: str = "Text"):
    """Print detailed analysis of text"""
    print("=" * 80)
    print(f"ANALYZING: {label}")
    print("=" * 80)
    print(f"Length: {len(text)} characters")
    print(f"Newlines: {text.count(chr(10))}")
    print(f"Preview (first 200 chars): {text[:200]}")
    print(f"Repr (first 200 chars): {repr(text[:200])}")
    print()
    
    result = check_spacing_issues(text)
    
    if result["has_issues"]:
        print(f"❌ ISSUES FOUND: {result['total_issues']} spacing problems")
        print()
        for issue in result["issues"]:
            print(f"  • {issue}")
        
        if result["examples"]:
            print()
            print("Examples:")
            for pattern, examples in result["examples"].items():
                print(f"  {pattern}: {examples}")
    else:
        print("✅ NO SPACING ISSUES DETECTED")
    
    print("=" * 80)
    print()


def main():
    """Run tests on sample responses"""
    
    # Test cases
    test_cases = [
        ("Bad spacing #1", "Halo!Berikut informasi yang Anda butuhkan:1.Langkah pertama"),
        ("Bad spacing #2", "adapertanyaan lain tentang areayang tersedia?"),
        ("Bad spacing #3", "Step1adalah membuka aplikasi.Kemudian pilih menu"),
        ("Good spacing", "Halo! Berikut informasi yang Anda butuhkan:\n\n1. Langkah pertama\n2. Langkah kedua"),
        ("Mixed", "Berikut adalah langkah-langkahnya:\n1.Buka aplikasi\n2.Pilih menu Settings"),
    ]
    
    print("🔍 SPACING ISSUE CHECKER")
    print("=" * 80)
    print()
    
    for label, text in test_cases:
        print_analysis(text, label)
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total test cases: {len(test_cases)}")
    
    results = [check_spacing_issues(text) for _, text in test_cases]
    issues_found = sum(1 for r in results if r["has_issues"])
    
    print(f"Cases with issues: {issues_found}")
    print(f"Cases without issues: {len(test_cases) - issues_found}")
    print()
    
    if issues_found > 0:
        print("⚠️  Some test cases have spacing issues!")
        return 1
    else:
        print("✅ All test cases look good!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
