#!/usr/bin/env python3
"""
GNUCash Category Extractor
Extracts account categories from a GNUCash file with include/exclude filtering.
Generates category lists for use in LLM prompts and categorization rules.
"""

import sys
import json
import argparse
import fnmatch
from pathlib import Path
from typing import List, Set, Dict, Optional

try:
    import gnucash
except ImportError:
    print("Error: GNUCash Python bindings not found.")
    print("Make sure to run this script with: ./gpython3 category_extractor.py")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("Error: PyYAML not found. Install with: pip install PyYAML")
    sys.exit(1)

from gnc_common import GnuCashSession


class CategoryFilter:
    """Filter for including/excluding account categories based on patterns."""

    def __init__(self, include_patterns: List[str] = None, exclude_patterns: List[str] = None):
        """
        Initialize category filter.

        Args:
            include_patterns: List of patterns to include (e.g., ["Expenses:*"])
            exclude_patterns: List of patterns to exclude (e.g., ["Expenses:Miscellaneous:*"])
        """
        self.include_patterns = include_patterns or ["*"]
        self.exclude_patterns = exclude_patterns or []

    def matches(self, category: str) -> bool:
        """
        Check if a category matches the filter criteria.

        Args:
            category: Full category path (e.g., "Expenses:Groceries")

        Returns:
            True if category should be included, False otherwise
        """
        # First check if excluded
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(category, pattern):
                return False

        # Then check if included
        for pattern in self.include_patterns:
            if fnmatch.fnmatch(category, pattern):
                return True

        return False

    @classmethod
    def from_yaml(cls, yaml_file: str) -> 'CategoryFilter':
        """
        Load category filter from YAML file.

        Expected YAML format:
        ```yaml
        include:
          - "Expenses:*"
        exclude:
          - "Expenses:Miscellaneous:*"
          - "Expenses:Sowmya*"
        ```

        Args:
            yaml_file: Path to YAML configuration file

        Returns:
            CategoryFilter instance
        """
        with open(yaml_file, 'r') as f:
            config = yaml.safe_load(f)

        include_patterns = config.get('include', ['*'])
        exclude_patterns = config.get('exclude', [])

        return cls(include_patterns, exclude_patterns)


class CategoryExtractor:
    """Extract categories from a GNUCash file."""

    def __init__(self, book_path: str, category_filter: Optional[CategoryFilter] = None):
        """
        Initialize category extractor.

        Args:
            book_path: Path to GNUCash file
            category_filter: Optional filter for categories
        """
        self.book_path = book_path
        self.book = None
        self.category_filter = category_filter or CategoryFilter()
        self.categories: Set[str] = set()

    def extract_categories(self) -> List[str]:
        """
        Extract all categories from the GNUCash file that match the filter.

        Returns:
            Sorted list of category paths
        """
        root_account = self.book.get_root_account()
        self._traverse_accounts(root_account)

        # Sort and return
        sorted_categories = sorted(self.categories)
        return sorted_categories

    def _traverse_accounts(self, account) -> None:
        """
        Recursively traverse account hierarchy and collect categories.

        Args:
            account: GNUCash account object
        """
        # Get account type - we want expense and income accounts primarily
        account_type = account.GetType()
        account_path = account.get_full_name()

        # Skip root account
        if account_path == "Root Account":
            for child in account.get_children():
                self._traverse_accounts(child)
            return

        # Check if this account matches our filter
        if self.category_filter.matches(account_path):
            self.categories.add(account_path)

        # Traverse children
        for child in account.get_children():
            self._traverse_accounts(child)

    def save_to_json(self, output_file: str) -> None:
        """
        Save extracted categories to JSON file.

        Args:
            output_file: Path to output JSON file
        """
        sorted_categories = sorted(self.categories)

        output_data = {
            'source_file': self.book_path,
            'total_categories': len(sorted_categories),
            'filter': {
                'include': self.category_filter.include_patterns,
                'exclude': self.category_filter.exclude_patterns
            },
            'categories': sorted_categories
        }

        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"Saved {len(sorted_categories)} categories to {output_file}")

    def print_summary(self) -> None:
        """Print summary of extracted categories."""
        sorted_categories = sorted(self.categories)

        print("\n" + "="*60)
        print("CATEGORY EXTRACTION SUMMARY")
        print("="*60)
        print(f"Total categories found: {len(sorted_categories)}")
        print(f"Filter include patterns: {self.category_filter.include_patterns}")
        print(f"Filter exclude patterns: {self.category_filter.exclude_patterns}")

        print("\nExtracted categories:")
        for category in sorted_categories:
            print(f"  - {category}")


def create_sample_filter_config(filename: str = "category_filter.yaml") -> None:
    """
    Create a sample category filter configuration file.

    Args:
        filename: Name of the output file
    """
    sample_config = {
        'include': [
            'Expenses:*'  # Include all expense categories
        ],
        'exclude': [
            'Expenses:Miscellaneous:*',  # Exclude miscellaneous
            'Expenses:Sowmya*',          # Exclude personal subcategories
            'Expenses:*Uncategorized*'   # Exclude uncategorized
        ]
    }

    with open(filename, 'w') as f:
        yaml.dump(sample_config, f, default_flow_style=False, sort_keys=False, indent=2)

    print(f"Sample category filter created: {filename}")
    print("\nExample content:")
    print("```yaml")
    with open(filename, 'r') as f:
        print(f.read())
    print("```")


def main():
    parser = argparse.ArgumentParser(
        description="Extract categories from GNUCash file with filtering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract all categories
  ./gpython3 category_extractor.py ~/gnc/accounts.gnucash

  # Extract with filter
  ./gpython3 category_extractor.py ~/gnc/accounts.gnucash --filter category_filter.yaml

  # Save to JSON
  ./gpython3 category_extractor.py ~/gnc/accounts.gnucash --output categories.json

  # Create sample filter config
  ./gpython3 category_extractor.py --create-sample-filter

Note: The filter config uses glob patterns (* and ?).
  - "Expenses:*" matches all expenses
  - "Expenses:Miscellaneous:*" matches all miscellaneous subcategories
        """
    )

    parser.add_argument('book_path', nargs='?', help='Path to GNUCash file')
    parser.add_argument('--filter', '-f', help='Path to YAML filter configuration')
    parser.add_argument('--output', '-o', default='categories.json',
                       help='Output JSON file (default: categories.json)')
    parser.add_argument('--create-sample-filter', action='store_true',
                       help='Create a sample category filter configuration file')

    args = parser.parse_args()

    # Handle sample filter creation
    if args.create_sample_filter:
        create_sample_filter_config()
        return

    # Validate book path
    if not args.book_path:
        parser.error("book_path is required unless using --create-sample-filter")

    if not Path(args.book_path).exists():
        print(f"Error: GNUCash file not found: {args.book_path}")
        sys.exit(1)

    # Load filter if specified
    category_filter = None
    if args.filter:
        if not Path(args.filter).exists():
            print(f"Error: Filter file not found: {args.filter}")
            sys.exit(1)
        category_filter = CategoryFilter.from_yaml(args.filter)
        print(f"Loaded filter from: {args.filter}")

    # Extract categories
    extractor = CategoryExtractor(args.book_path, category_filter)

    with GnuCashSession(args.book_path) as book:
        extractor.book = book
        categories = extractor.extract_categories()

    # Save and display results
    extractor.save_to_json(args.output)
    extractor.print_summary()

    print(f"\nCategories saved to: {args.output}")
    print("You can use this JSON file in the LLM categorizer for category suggestions.")


if __name__ == "__main__":
    main()
