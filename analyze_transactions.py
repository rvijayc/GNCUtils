#!/usr/bin/env python3
"""
GNUCash Transaction Analyzer - Transaction-Based Architecture

Analyzes credit card transactions and generates high-confidence categorization rules
from historical data.

This version focuses on generating fewer, higher-quality rules since there is
an LLM-based fallback for transactions that don't match any rules.

Architecture:
- Returns uncategorized transactions as GnuCashTransaction objects
- No longer generates unique_descriptions.txt intermediate file
- Transaction objects can be directly passed to llm_categorizer or rules_engine
"""

import sys
import re
import argparse
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from decimal import Decimal
from typing import List, Dict, Optional

try:
    import gnucash
except ImportError:
    print("Error: GNUCash Python bindings not found.")
    print("Make sure to run this script with: ./gpython3 analyze_transactions.py")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("Error: PyYAML not found. Install with: pip install PyYAML")
    sys.exit(1)

from gnc_common import GnuCashSession, get_credit_card_accounts
from core_models import (
    GnuCashTransaction,
    CategorizationRule,
    RuleType,
    RuleSource,
    TransactionType
)
from rules_db import save_history_rules
from description_normalizer import normalize_description


class TransactionAnalyzer:
    """Analyzes GNUCash transactions to generate high-confidence categorization rules."""

    def __init__(self, book_path: str, config: Optional[Dict] = None):
        self.book_path = book_path
        self.book = None
        self.transactions: List[GnuCashTransaction] = []
        self.rules: List[CategorizationRule] = []
        self.config = config or {}

    def load_config(self, config_path: str) -> None:
        """Load YAML configuration file."""
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            print(f"Configuration loaded from: {config_path}")
        except Exception as e:
            print(f"Error loading configuration: {e}")
            sys.exit(1)

    def extract_transactions(self) -> List[GnuCashTransaction]:
        """Extract all debit transactions from credit card accounts."""
        cc_accounts = get_credit_card_accounts(
            self.book,
            self.config.get('credit_card_accounts')
        )
        print(f"Found {len(cc_accounts)} credit card accounts")

        transactions = []

        # Get date range from config if specified
        start_date = None
        end_date = None
        if self.config and 'date_range' in self.config:
            date_config = self.config['date_range']
            if date_config:
                if 'start_date' in date_config:
                    start_date = datetime.strptime(date_config['start_date'], '%Y-%m-%d').date()
                    print(f"Filtering transactions from: {start_date}")
                if 'end_date' in date_config:
                    end_date = datetime.strptime(date_config['end_date'], '%Y-%m-%d').date()
                    print(f"Filtering transactions until: {end_date}")

        for account in cc_accounts:
            account_name = account.GetName()
            account_path = account.get_full_name()
            print(f"Analyzing account: {account_path}")

            for split in account.GetSplitList():
                transaction = split.GetParent()

                # Skip if this transaction was already processed
                guid = transaction.GetGUID().to_string()
                if any(t.guid == guid for t in transactions):
                    continue

                # Apply date filtering if configured
                transaction_date = transaction.GetDate().date()
                if start_date and transaction_date < start_date:
                    continue
                if end_date and transaction_date > end_date:
                    continue

                # Determine transaction type based on the split value
                split_value = split.GetValue()
                # For credit card accounts (liabilities), negative values are debits (expenses)
                # and positive values are credits (payments/refunds)
                if split_value < 0:
                    txn_type = TransactionType.DEBIT
                else:
                    txn_type = TransactionType.CREDIT

                # ONLY process DEBIT transactions (expenses)
                # Credit transactions require manual handling
                if txn_type != TransactionType.DEBIT:
                    continue

                # Find the opposing split (the expense/income account)
                opposing_split = None
                for s in transaction.GetSplitList():
                    if s.GetAccount() != account:
                        opposing_split = s
                        break

                if opposing_split:
                    txn_data = GnuCashTransaction(
                        description=transaction.GetDescription(),
                        normalized_description="",  # Will be set during generate_rules()
                        amount=Decimal(str(float(split_value))),
                        date=transaction_date,
                        transaction_type=txn_type,
                        memo=split.GetMemo() or None,
                        guid=guid,
                        credit_card_account=account_name,
                        credit_card_account_path=account_path,
                        actual_category_account=opposing_split.GetAccount().GetName(),
                        actual_category_full_path=opposing_split.GetAccount().get_full_name()
                    )
                    transactions.append(txn_data)

        self.transactions = transactions
        print(f"Extracted {len(transactions)} DEBIT transactions for analysis")
        return transactions

    # Note: normalize_description is now imported from description_normalizer module

    def generate_rules(self) -> List[CategorizationRule]:
        """
        Generate high-confidence categorization rules using conservative thresholds.

        Since we have an LLM fallback, we prioritize precision over recall.
        This means we only generate rules we're confident about.
        """
        # Get rule settings from config with higher default thresholds
        rule_settings = self.config.get('rule_settings', {})
        min_transactions = rule_settings.get('minimum_transactions', 3)  # Increased from 2
        confidence_threshold = rule_settings.get('confidence_threshold', 0.65)  # Increased from 0.3
        min_pattern_length = rule_settings.get('min_pattern_length', 5)  # New: minimum pattern length

        print(f"\nRule generation settings:")
        print(f"  Minimum transactions: {min_transactions}")
        print(f"  Confidence threshold: {confidence_threshold}")
        print(f"  Minimum pattern length: {min_pattern_length}")

        # Normalize all descriptions first using shared normalizer
        for txn in self.transactions:
            txn.normalized_description = normalize_description(txn.description)

        # Group transactions by category
        category_transactions = defaultdict(list)
        for txn in self.transactions:
            category = txn.actual_category_full_path
            category_transactions[category].append(txn)

        rules = []

        for category, txns in category_transactions.items():
            if len(txns) < min_transactions:
                continue

            print(f"\nAnalyzing category: {category} ({len(txns)} transactions)")

            # Method 1: Exact normalized description matches
            # These are the highest confidence rules
            normalized_desc_counts = Counter()
            desc_examples = defaultdict(list)

            for txn in txns:
                norm_desc = txn.normalized_description
                if len(norm_desc) >= min_pattern_length:
                    normalized_desc_counts[norm_desc] += 1
                    desc_examples[norm_desc].append(txn.description)

            for norm_desc, count in normalized_desc_counts.items():
                if count >= min_transactions:
                    confidence = count / len(txns)

                    if confidence >= confidence_threshold:
                        rule = CategorizationRule(
                            rule_type=RuleType.EXACT_MATCH,
                            rule_source=RuleSource.HISTORY_BASED,
                            pattern=norm_desc,
                            category=category,
                            confidence=confidence,
                            transaction_count=count,
                            total_transactions=len(txns),
                            example_descriptions=desc_examples[norm_desc][:3]
                        )
                        rules.append(rule)
                        print(f"  ✓ EXACT: '{norm_desc}' (confidence: {confidence:.2%}, count: {count})")

            # Method 2: Word/phrase-based "contains" rules
            # Extract meaningful words from descriptions (skip very common/short words)
            skip_words = {
                'payment', 'purchase', 'debit', 'credit', 'card', 'auto', 'recurring',
                'online', 'mobile', 'pos', 'terminal', 'transaction', 'transfer',
                'www', 'com', 'net', 'org', 'http', 'https'
            }

            word_counts = Counter()
            word_examples = defaultdict(list)

            for txn in txns:
                words = txn.normalized_description.split()
                for word in words:
                    # Only consider words of sufficient length and not in skip list
                    if len(word) >= min_pattern_length and word not in skip_words:
                        word_counts[word] += 1
                        if len(word_examples[word]) < 3:
                            word_examples[word].append(txn.description)

            # Generate "contains" rules for top words with high frequency
            for word, count in word_counts.most_common(5):  # Top 5 words only
                # Higher threshold for contains rules: need 60%+ coverage
                if count >= max(min_transactions, len(txns) * 0.6):
                    confidence = count / len(txns)

                    if confidence >= confidence_threshold:
                        rule = CategorizationRule(
                            rule_type=RuleType.CONTAINS,
                            rule_source=RuleSource.HISTORY_BASED,
                            pattern=word,
                            category=category,
                            confidence=confidence,
                            transaction_count=count,
                            total_transactions=len(txns),
                            example_descriptions=word_examples[word]
                        )
                        rules.append(rule)
                        print(f"  ✓ CONTAINS: '{word}' (confidence: {confidence:.2%}, count: {count})")

        # Sort rules by confidence, then by transaction count
        rules.sort(key=lambda x: (x.confidence, x.transaction_count), reverse=True)

        self.rules = rules
        print(f"\n{'='*60}")
        print(f"Generated {len(rules)} high-confidence rules")
        print(f"{'='*60}")

        return rules

    def save_rules(self, filename: str = 'history_rules.yaml') -> None:
        """Save the generated rules to a YAML file."""
        # Prepare metadata
        metadata = {
            'book_path': self.book_path,
            'total_transactions_analyzed': len(self.transactions),
            'total_rules_generated': len(self.rules),
        }

        # Add config info to metadata if available
        if self.config:
            if 'date_range' in self.config:
                metadata['date_range'] = self.config['date_range']
            if 'credit_card_accounts' in self.config:
                metadata['analyzed_accounts'] = self.config['credit_card_accounts']
            if 'rule_settings' in self.config:
                metadata['generation_config'] = self.config['rule_settings']

        save_history_rules(self.rules, filename, metadata)

    def get_uncategorized_transactions(self) -> List[GnuCashTransaction]:
        """
        Get transactions that are NOT covered by generated rules.
        Returns GnuCashTransaction objects for downstream processing.
        """
        uncategorized = []

        for txn in self.transactions:
            norm_desc = txn.normalized_description
            if not norm_desc:
                continue

            # Check if this transaction matches any rule
            matched = False
            for rule in self.rules:
                if rule.rule_type == RuleType.EXACT_MATCH and norm_desc == rule.pattern:
                    matched = True
                    break
                elif rule.rule_type == RuleType.CONTAINS and rule.pattern in norm_desc:
                    matched = True
                    break

            if not matched:
                uncategorized.append(txn)

        return uncategorized

    def print_summary(self) -> None:
        """Print a summary of the analysis."""
        print("\n" + "="*60)
        print("TRANSACTION ANALYSIS SUMMARY")
        print("="*60)
        print(f"Total DEBIT transactions analyzed: {len(self.transactions)}")
        print(f"Total high-confidence rules generated: {len(self.rules)}")

        # Show top categories
        category_counts = Counter(txn.actual_category_full_path for txn in self.transactions)
        print(f"\nTop 10 transaction categories:")
        for category, count in category_counts.most_common(10):
            print(f"  {category}: {count} transactions")

        # Show rule type distribution
        rule_type_counts = Counter(rule.rule_type for rule in self.rules)
        print(f"\nRule type distribution:")
        for rule_type, count in rule_type_counts.items():
            print(f"  {rule_type.value}: {count} rules")

        # Show top rules
        print(f"\nTop 10 categorization rules:")
        for i, rule in enumerate(self.rules[:10], 1):
            print(f"  {i}. [{rule.rule_type.value}] '{rule.pattern}' → {rule.category}")
            print(f"     Confidence: {rule.confidence:.2%} ({rule.transaction_count}/{rule.total_transactions} transactions)")

        # Calculate coverage estimate
        if self.transactions:
            covered_txns = set()
            for rule in self.rules:
                for txn in self.transactions:
                    if txn.guid not in covered_txns:
                        # Simple match check
                        norm_desc = txn.normalized_description
                        if rule.rule_type == RuleType.EXACT_MATCH and norm_desc == rule.pattern:
                            covered_txns.add(txn.guid)
                        elif rule.rule_type == RuleType.CONTAINS and rule.pattern in norm_desc:
                            covered_txns.add(txn.guid)

            coverage = len(covered_txns) / len(self.transactions)
            print(f"\nEstimated rule coverage: {coverage:.1%} of transactions")
            print(f"  Covered: {len(covered_txns)} transactions")
            print(f"  Uncovered: {len(self.transactions) - len(covered_txns)} transactions")
            print(f"  (Uncovered transactions will use LLM-based categorization)")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze GNUCash credit card transactions and generate high-confidence categorization rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all credit card accounts
  ./gpython3 analyze_transactions.py ~/gnc/accounts.gnucash

  # Use configuration file to specify which accounts to analyze
  ./gpython3 analyze_transactions.py ~/gnc/accounts.gnucash --config analyze_config.yaml

  # Generate a sample configuration file first
  ./gpython3 list_accounts.py ~/gnc/accounts.gnucash --generate-config

Note: This version generates high-confidence rules only. Transactions that don't
      match any rules should be categorized using the LLM-based agent.
        """
    )

    parser.add_argument('book_path', help='Path to GNUCash file')
    parser.add_argument('--config', '-c', help='Path to YAML configuration file')
    parser.add_argument('--output', '-o', default='history_rules.yaml',
                       help='Output file for rules (default: history_rules.yaml)')

    args = parser.parse_args()

    if not Path(args.book_path).exists():
        print(f"Error: GNUCash file not found: {args.book_path}")
        sys.exit(1)

    # Initialize analyzer
    analyzer = TransactionAnalyzer(args.book_path)

    # Load configuration if specified
    if args.config:
        if not Path(args.config).exists():
            print(f"Error: Configuration file not found: {args.config}")
            sys.exit(1)
        analyzer.load_config(args.config)

    # Use context manager to ensure proper session cleanup
    with GnuCashSession(args.book_path) as book:
        analyzer.book = book

        # Extract transactions
        analyzer.extract_transactions()

        # Generate rules
        analyzer.generate_rules()

    # Save rules (done outside session since we don't need the book anymore)
    analyzer.save_rules(args.output)

    # Get uncategorized transactions (for potential downstream processing)
    uncategorized = analyzer.get_uncategorized_transactions()
    print(f"\nUncategorized transactions: {len(uncategorized)}")
    print(f"  These can be processed using LLM categorizer with Transaction objects")

    # Print summary
    analyzer.print_summary()

    print(f"\n{'='*60}")
    print(f"Analysis complete! Rules saved to '{args.output}'")
    print(f"{'='*60}")

    if not args.config:
        print(f"\nTip: To analyze specific accounts only, run:")
        print(f"  ./gpython3 list_accounts.py {args.book_path} --generate-config")
        print(f"  # Edit the generated analyze_config.yaml file")
        print(f"  ./gpython3 analyze_transactions.py {args.book_path} --config analyze_config.yaml")


if __name__ == "__main__":
    main()
