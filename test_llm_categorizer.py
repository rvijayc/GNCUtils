#!/usr/bin/env python3
"""
Test script for LLM categorizer validation.
Extracts first 25 transactions from GNUCash and runs LLM categorization.
"""

import sys
import os
from pathlib import Path
from decimal import Decimal
from datetime import date

# Import GNUCash bindings
try:
    import gnucash
except ImportError:
    print("Error: GNUCash Python bindings not found.")
    print("Make sure to run this script with: ./gpython3 test_llm_categorizer.py")
    sys.exit(1)

from gnc_common import GnuCashSession
from core_models import GnuCashTransaction, TransactionType
from description_normalizer import normalize_description
from llm_categorizer import LLMTransactionCategorizer
from rules_engine import RulesEngine
from rich.console import Console
from rich.table import Table
import yaml


def load_config(config_path: str):
    """Load analyzer configuration."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def extract_sample_transactions(book_path: str, config: dict, limit: int = 25):
    """Extract first N transactions from GNUCash."""
    from gnc_common import get_credit_card_accounts

    transactions = []

    with GnuCashSession(book_path) as book:
        cc_accounts = get_credit_card_accounts(book, config.get('credit_card_accounts'))
        print(f"Found {len(cc_accounts)} credit card accounts")

        for account in cc_accounts:
            account_name = account.GetName()
            account_path = account.get_full_name()

            for split in account.GetSplitList():
                if len(transactions) >= limit:
                    break

                transaction = split.GetParent()
                guid = transaction.GetGUID().to_string()

                # Skip duplicates
                if any(t.guid == guid for t in transactions):
                    continue

                # Get transaction type
                split_value = split.GetValue()
                if split_value < 0:
                    txn_type = TransactionType.DEBIT
                else:
                    txn_type = TransactionType.CREDIT

                # Only DEBIT for now
                if txn_type != TransactionType.DEBIT:
                    continue

                # Find opposing split for actual category
                opposing_split = None
                for s in transaction.GetSplitList():
                    if s.GetAccount() != account:
                        opposing_split = s
                        break

                if opposing_split:
                    description = transaction.GetDescription()
                    normalized = normalize_description(description)

                    txn_data = GnuCashTransaction(
                        description=description,
                        normalized_description=normalized,
                        amount=Decimal(str(float(split_value))),
                        date=transaction.GetDate().date(),
                        transaction_type=txn_type,
                        memo=split.GetMemo() or None,
                        guid=guid,
                        credit_card_account=account_name,
                        credit_card_account_path=account_path,
                        actual_category_account=opposing_split.GetAccount().GetName(),
                        actual_category_full_path=opposing_split.GetAccount().get_full_name()
                    )
                    transactions.append(txn_data)

            if len(transactions) >= limit:
                break

    return transactions


def display_results(transactions, title="LLM Categorization Results"):
    """Display categorization results in a table."""
    console = Console()

    console.print(f"\n[bold cyan]{title}[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Description", style="white", width=30)
    table.add_column("Predicted", style="green", width=30)
    table.add_column("Actual", style="yellow", width=30)
    table.add_column("Match", style="cyan", width=5)
    table.add_column("Conf", style="blue", width=5)
    table.add_column("Source", style="magenta", width=10)

    correct = 0
    total = 0

    for i, txn in enumerate(transactions, 1):
        desc = txn.description[:30]
        actual = txn.actual_category_full_path[:30] if txn.actual_category_full_path else "N/A"

        if txn.categorization:
            predicted = txn.categorization.category[:30]
            confidence = f"{txn.categorization.confidence:.0%}"
            source = txn.categorization.source.value if txn.categorization.source else "?"

            # Check if prediction matches actual
            match = "✓" if predicted == txn.actual_category_full_path else "✗"
            if predicted == txn.actual_category_full_path:
                correct += 1
            total += 1
        else:
            predicted = "Uncategorized"
            confidence = "0%"
            source = "N/A"
            match = "✗"
            total += 1

        table.add_row(str(i), desc, predicted, actual, match, confidence, source)

    console.print(table)

    # Print accuracy
    if total > 0:
        accuracy = correct / total * 100
        console.print(f"\n[bold]Accuracy: {correct}/{total} ({accuracy:.1f}%)[/bold]")

    return correct, total


def main():
    # Check for required files
    book_path = "/home/vijayr/gnc/vijayr.gnucash"
    config_path = "analyze_config.yaml"
    categories_file = "categories.json"

    if not Path(book_path).exists():
        print(f"Error: GNUCash file not found: {book_path}")
        sys.exit(1)

    if not Path(config_path).exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)

    # Load configuration
    config = load_config(config_path)

    # Extract sample transactions
    print(f"\nExtracting first 25 transactions from GNUCash...")
    transactions = extract_sample_transactions(book_path, config, limit=25)
    print(f"Extracted {len(transactions)} transactions")

    # Initialize rules engine
    print("\nInitializing rules engine...")
    rules_engine = RulesEngine(
        manual_rules_file="manual_rules.yaml",
        history_rules_file="test_history_rules.yaml" if Path("test_history_rules.yaml").exists() else None,
        ai_rules_file="ai_rules.yaml"
    )

    # Initialize LLM categorizer
    print("\nInitializing LLM categorizer...")
    categorizer = LLMTransactionCategorizer(
        categories_file=categories_file,
        rules_engine=rules_engine,
        ai_rules_file="ai_rules.yaml"
    )

    # Categorize transactions
    print("\nCategorizing transactions...")
    print("(This may take a moment - LLM calls are being made)\n")

    categorizer.categorize_batch(transactions, verbose=False)

    # Display results
    correct, total = display_results(transactions)

    # Print statistics
    categorizer.print_stats()

    # Save new AI rules
    if categorizer.new_ai_rules:
        print(f"\nNew AI rules generated: {len(categorizer.new_ai_rules)}")
        categorizer.save_ai_rules()
    else:
        print("\nNo new AI rules generated (all handled by existing rules)")


if __name__ == "__main__":
    main()
