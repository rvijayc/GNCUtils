#!/usr/bin/env python3
"""
Transaction Description Normalizer
Shared normalization logic for transaction descriptions from both GNUCash and QFX/OFX files.

This module provides a consistent way to normalize transaction descriptions to:
- Reduce the number of unique descriptions
- Improve pattern matching across different data sources
- Enable better rule generation and matching
"""

import re
from typing import Tuple, List


def normalize_description(desc: str) -> str:
    """
    Minimal normalization of transaction description.

    This approach is conservative - it removes obvious artifacts while preserving
    merchant-identifying information including numbers in merchant names.

    Normalization steps:
    - Convert to lowercase
    - Remove very long digit sequences (8+ digits) - likely auth/transaction codes
    - Remove trailing phone number patterns (XXX-XXX-XXXX or XXX-XXXX at end)
    - Remove date patterns (MM/DD/YYYY)
    - Remove multiple asterisks
    - Normalize whitespace (multiple spaces → single space)
    - Clean up stray dashes/hyphens

    PRESERVES:
    - Merchant names with numbers (1-800-CONTACTS, 76, 7-ELEVEN, 85C BAKERY)
    - Store/location numbers (#1234, STORE #5678)
    - Short digit sequences that are part of merchant identity

    Args:
        desc: Raw transaction description

    Returns:
        Normalized description string (lowercase, cleaned)
    """
    # Start with basic cleanup
    desc = desc.strip()

    # Remove very long digit sequences (8+ consecutive digits) - likely auth/transaction codes
    desc = re.sub(r'\b\d{8,}\b', '', desc)

    # Remove trailing phone number patterns
    # Pattern: XXX-XXX-XXXX or XXX-XXXX at the end of string
    desc = re.sub(r'\s+\d{3}-\d{3}-\d{4}\s*$', '', desc)
    desc = re.sub(r'\s+\d{3}-\d{4}\s*$', '', desc)

    # Remove date patterns (MM/DD/YYYY or MM/DD/YY)
    desc = re.sub(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', '', desc)

    # Clean up asterisks - reduce multiple to single
    desc = re.sub(r'\*+', '*', desc)

    # Clean up dashes/hyphens
    # Remove multiple dashes (---)
    desc = re.sub(r'-{3,}', ' ', desc)
    # Remove standalone dashes surrounded by spaces
    desc = re.sub(r'\s+-\s+', ' ', desc)
    # Remove trailing/leading dashes
    desc = re.sub(r'^\s*-\s*|\s*-\s*$', '', desc)

    # Normalize whitespace - multiple spaces to single space
    desc = re.sub(r'\s+', ' ', desc)

    # Final cleanup and convert to lowercase
    desc = desc.strip().lower()

    return desc


def normalize_description_with_numbers(desc: str) -> Tuple[str, List[str]]:
    """
    Normalize a transaction description and also extract number sequences.

    This is useful when you want to preserve the numbers for potential
    pattern matching (e.g., specific store numbers, phone numbers).

    Args:
        desc: Raw transaction description

    Returns:
        Tuple of (normalized_description, list_of_extracted_numbers)
    """
    # Start with basic cleanup
    desc = desc.strip().upper()
    desc = re.sub(r"\s+", " ", desc)
    desc = re.sub(r"\*+", "*", desc)

    # --- Dash cleanup (order matters) ---
    # 1) Dash runs followed by digits: keep digits, drop dashes
    desc = re.sub(r"-{2,}\s*(\d+)", r" \1", desc)

    # 2) Remove dash runs not followed by digits
    desc = re.sub(r"\s*-{2,}\s*", " ", desc)

    # 3) Remove standalone/dangling hyphens
    desc = re.sub(r"\s-\s", " ", desc)
    desc = re.sub(r"\s-\s*$", " ", desc)
    desc = re.sub(r"\s-$", "", desc)

    # 4) Preserve in-word hyphens
    desc = re.sub(r"(?<![A-Z0-9])-(?=[A-Z0-9])", " ", desc)
    desc = re.sub(r"(?<=[A-Z0-9])-(?![A-Z0-9])", " ", desc)

    # Extract and remove digit sequences (3+ digits) in one pass
    numbers: List[str] = []
    def _collect_and_remove(m: re.Match) -> str:
        numbers.append(m.group(0))
        return ""

    merchant_core = re.sub(r"\d{3,}", _collect_and_remove, desc).strip()

    # Remove dangling 1-2 digit tokens at the end
    merchant_core = re.sub(r"\s\d{1,2}$", "", merchant_core)

    # Final space normalization
    merchant_core = re.sub(r"\s+", " ", merchant_core).strip()

    # Return lowercase description and extracted numbers
    return merchant_core.lower(), numbers


def iterative_normalize(desc: str) -> str:
    """
    Apply normalization iteratively until the description stabilizes.

    This ensures that artifacts created by one normalization step
    are caught by subsequent passes.

    Args:
        desc: Raw transaction description

    Returns:
        Fully normalized description
    """
    prev = None
    current = desc

    while current != prev:
        prev = current
        current = normalize_description(current)

    return current


# Convenience function for backward compatibility
def clean_description(desc: str) -> str:
    """
    Alias for iterative_normalize for backward compatibility.

    Args:
        desc: Raw transaction description

    Returns:
        Fully normalized description
    """
    return iterative_normalize(desc)


if __name__ == "__main__":
    # Test the minimal normalizer
    test_descriptions = [
        "STARBUCKS STORE #12345 SAN DIEGO CA",
        "Netflix.com 408-540-3700",
        "UBER *TRIP 866-576-1039",
        "COSTCO WHSE #1234 92121",
        "PayPal *Netflix 402-935-7733",
        "INTERNET PAYMENT THANK YOU",
        "TST* RESTAURANT NAME 858-123-4567",
        "1-800-CONTACTS INC. 800-266-8888",
        "76 GAS STATION #5678",
        "7-ELEVEN STORE 12345678901234",  # Very long number should be removed
        "85C BAKERY CAFE SAN DIEGO",
        "99 RANCH MARKET 858-123-4567"
    ]

    print("Testing Minimal Description Normalizer:")
    print("=" * 80)

    for desc in test_descriptions:
        normalized = normalize_description(desc)

        print(f"Original:    {desc}")
        print(f"Normalized:  {normalized}")
        print("-" * 80)
