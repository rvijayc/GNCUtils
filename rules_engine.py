#!/usr/bin/env python3
"""
Transaction Categorization Rules Engine

Applies categorization rules in priority order:
1. Manual rules (highest priority)
2. Credit transaction check (return "Unspecified" for credits)
3. History-based rules + AI-generated rules (by confidence)
4. Falls back to LLM if no match

Supports flexible rule database configuration for different use cases.
"""

import re
from typing import Optional, List, Tuple
from pathlib import Path

from core_models import (
    CategorizationRule,
    CategorizationResult,
    RuleType,
    RuleSource,
    Transaction,
    TransactionType
)
from rules_db import load_manual_rules, load_history_rules, load_ai_rules


class RuleMatchResult:
    """Result of a rule matching operation."""

    def __init__(
        self,
        matched: bool,
        rule: Optional[CategorizationRule] = None,
        reason: str = ""
    ):
        self.matched = matched
        self.rule = rule
        self.reason = reason

    def __bool__(self) -> bool:
        return self.matched


class RulesEngine:
    """
    Rules engine for transaction categorization.

    Matches transactions against rules in priority order:
    1. Manual rules (user-defined, highest priority)
    2. Credit transaction filter (auto-return "Unspecified")
    3. History + AI rules (combined by confidence)
    """

    def __init__(
        self,
        manual_rules_file: Optional[str] = None,
        history_rules_file: Optional[str] = None,
        ai_rules_file: Optional[str] = None,
        use_history: bool = True,
        use_ai: bool = True
    ):
        """
        Initialize rules engine.

        Args:
            manual_rules_file: Path to manual rules YAML
            history_rules_file: Path to history rules YAML
            ai_rules_file: Path to AI rules YAML
            use_history: Whether to use history-based rules
            use_ai: Whether to use AI-generated rules
        """
        # Load or create empty rule databases
        self.manual_rules: List[CategorizationRule] = []
        self.history_rules: List[CategorizationRule] = []
        self.ai_rules: List[CategorizationRule] = []

        # Load manual rules
        if manual_rules_file and Path(manual_rules_file).exists():
            try:
                self.manual_rules = load_manual_rules(manual_rules_file)
            except Exception as e:
                print(f"Warning: Could not load manual rules: {e}")

        # Load history rules if enabled
        if use_history and history_rules_file and Path(history_rules_file).exists():
            try:
                self.history_rules = load_history_rules(history_rules_file)
            except Exception as e:
                print(f"Warning: Could not load history rules: {e}")

        # Load AI rules if enabled
        if use_ai and ai_rules_file and Path(ai_rules_file).exists():
            try:
                self.ai_rules = load_ai_rules(ai_rules_file)
            except Exception as e:
                print(f"Warning: Could not load AI rules: {e}")

        # Statistics
        print(f"Rules engine initialized:")
        print(f"  Manual rules: {len(self.manual_rules)}")
        print(f"  History rules: {len(self.history_rules)}")
        print(f"  AI rules: {len(self.ai_rules)}")

    def match_rule(
        self,
        description: str,
        rule: CategorizationRule
    ) -> bool:
        """
        Check if a description matches a single rule.

        Args:
            description: Normalized transaction description
            rule: Rule to match against

        Returns:
            True if the description matches the rule (and doesn't match regex_exclude if specified)
        """
        pattern = rule.pattern

        # First, check if the main pattern matches
        matched = False
        if rule.rule_type == RuleType.EXACT_MATCH:
            matched = description == pattern

        elif rule.rule_type == RuleType.CONTAINS:
            matched = pattern in description

        elif rule.rule_type == RuleType.REGEX:
            try:
                matched = bool(re.search(pattern, description, re.IGNORECASE))
            except re.error:
                print(f"Warning: Invalid regex pattern: {pattern}")
                return False

        # If main pattern matched, check regex_exclude
        if matched and rule.regex_exclude:
            try:
                if re.search(rule.regex_exclude, description, re.IGNORECASE):
                    # Matched the exclude pattern, so this rule doesn't apply
                    return False
            except re.error:
                print(f"Warning: Invalid regex_exclude pattern: {rule.regex_exclude}")
                # If exclude pattern is invalid, ignore it and keep the match

        return matched

    def find_best_match(
        self,
        description: str,
        rules: List[CategorizationRule]
    ) -> Optional[CategorizationRule]:
        """
        Find the best matching rule from a list of rules.

        Returns the first matching rule (rules should be pre-sorted by priority).
        If multiple rules match, returns the one with highest confidence.

        Args:
            description: Normalized transaction description
            rules: List of rules to check

        Returns:
            Best matching rule or None
        """
        matching_rules = []

        for rule in rules:
            if self.match_rule(description, rule):
                matching_rules.append(rule)

        if not matching_rules:
            return None

        # Return rule with highest confidence
        matching_rules.sort(key=lambda r: r.confidence, reverse=True)
        return matching_rules[0]

    def categorize_transaction(
        self,
        transaction: Transaction
    ) -> Transaction:
        """
        Categorize a transaction using rules engine.

        Updates the transaction's categorization field if a match is found.

        Args:
            transaction: Transaction object to categorize

        Returns:
            Same transaction object with categorization populated (if matched)
        """
        match_result = self._match_internal(
            transaction.normalized_description,
            transaction.transaction_type
        )

        if match_result.matched:
            transaction.categorization = CategorizationResult(
                category=match_result.rule.category,
                confidence=match_result.rule.confidence,
                matched_rule=match_result.rule,
                source=match_result.rule.rule_source,
                reasoning=match_result.reason
            )

        return transaction

    def match_transaction(
        self,
        transaction: Transaction
    ) -> RuleMatchResult:
        """
        Match a transaction against rules (for compatibility).

        Args:
            transaction: Transaction object

        Returns:
            RuleMatchResult with matched rule or None
        """
        return self._match_internal(
            transaction.normalized_description,
            transaction.transaction_type
        )

    def _match_internal(
        self,
        description: str,
        transaction_type: TransactionType
    ) -> RuleMatchResult:
        """
        Internal method to match description and type against rules.

        Priority order:
        1. Manual rules (highest priority)
        2. Credit transaction filter (return "Unspecified" for credits)
        3. History + AI rules combined (by confidence)

        Args:
            description: Normalized transaction description
            transaction_type: DEBIT or CREDIT

        Returns:
            RuleMatchResult with matched rule or None
        """
        # Priority 1: Check manual rules first
        manual_match = self.find_best_match(description, self.manual_rules)
        if manual_match:
            return RuleMatchResult(
                matched=True,
                rule=manual_match,
                reason="Matched manual rule"
            )

        # Priority 2: Auto-handle credit transactions
        # Credits should not be auto-categorized (return "Unspecified")
        if transaction_type == TransactionType.CREDIT:
            # Create a synthetic rule for credits
            credit_rule = CategorizationRule(
                rule_type=RuleType.EXACT_MATCH,
                rule_source=RuleSource.MANUAL,
                pattern=description,
                category="Unspecified",
                confidence=1.0,
                description="Credit transactions are not auto-categorized"
            )
            return RuleMatchResult(
                matched=True,
                rule=credit_rule,
                reason="Credit transaction - returning Unspecified"
            )

        # Priority 3: Check history + AI rules combined
        # Combine both lists and find best match by confidence
        combined_rules = self.history_rules + self.ai_rules
        combined_match = self.find_best_match(description, combined_rules)

        if combined_match:
            source_name = "history" if combined_match.rule_source == RuleSource.HISTORY_BASED else "AI"
            return RuleMatchResult(
                matched=True,
                rule=combined_match,
                reason=f"Matched {source_name} rule"
            )

        # No match found
        return RuleMatchResult(
            matched=False,
            rule=None,
            reason="No matching rule found"
        )

    def get_stats(self) -> dict:
        """Get statistics about loaded rules."""
        return {
            'manual_rules': len(self.manual_rules),
            'history_rules': len(self.history_rules),
            'ai_rules': len(self.ai_rules),
            'total_rules': len(self.manual_rules) + len(self.history_rules) + len(self.ai_rules)
        }


def create_empty_rules_file(filename: str, rule_source: RuleSource) -> None:
    """
    Create an empty rules file with proper structure.

    Args:
        filename: Path to create file at
        rule_source: Source type for the rules file
    """
    from rules_db import save_history_rules

    source_descriptions = {
        RuleSource.MANUAL: "Manually specified rules (highest priority)",
        RuleSource.HISTORY_BASED: "Rules generated from historical GNUCash data",
        RuleSource.AI_GENERATED: "Rules generated by AI/LLM agent"
    }

    metadata = {
        'description': source_descriptions.get(rule_source, "Categorization rules"),
        'total_rules': 0,
        'created_at': str(Path(filename).absolute())
    }

    save_history_rules([], filename, metadata)
    print(f"Created empty rules file: {filename}")


if __name__ == "__main__":
    # Test the rules engine
    print("Testing Rules Engine")
    print("=" * 60)

    # Create sample rules for testing
    manual_rule = CategorizationRule(
        rule_type=RuleType.CONTAINS,
        rule_source=RuleSource.MANUAL,
        pattern="netflix",
        category="Expenses.Bills.Streaming Services",
        confidence=1.0
    )

    history_rule = CategorizationRule(
        rule_type=RuleType.CONTAINS,
        rule_source=RuleSource.HISTORY_BASED,
        pattern="starbucks",
        category="Expenses.Dining Out",
        confidence=0.85
    )

    ai_rule = CategorizationRule(
        rule_type=RuleType.REGEX,
        rule_source=RuleSource.AI_GENERATED,
        pattern=r"chipotle.*",
        category="Expenses.Dining Out",
        confidence=0.92
    )

    # Create engine with sample rules
    engine = RulesEngine()
    engine.manual_rules = [manual_rule]
    engine.history_rules = [history_rule]
    engine.ai_rules = [ai_rule]

    # Test cases with Transaction objects
    from decimal import Decimal
    from datetime import date

    test_cases = [
        (Transaction(
            description="netflix.com",
            normalized_description="netflix.com",
            amount=Decimal("15.99"),
            date=date.today(),
            transaction_type=TransactionType.DEBIT
        ), "Should match manual rule"),
        (Transaction(
            description="starbucks #1234",
            normalized_description="starbucks #1234",
            amount=Decimal("5.75"),
            date=date.today(),
            transaction_type=TransactionType.DEBIT
        ), "Should match history rule"),
        (Transaction(
            description="chipotle 5678 san diego",
            normalized_description="chipotle 5678 san diego",
            amount=Decimal("12.50"),
            date=date.today(),
            transaction_type=TransactionType.DEBIT
        ), "Should match AI regex rule"),
        (Transaction(
            description="internet payment thank you",
            normalized_description="internet payment thank you",
            amount=Decimal("500.00"),
            date=date.today(),
            transaction_type=TransactionType.CREDIT
        ), "Should return Unspecified"),
        (Transaction(
            description="unknown merchant xyz",
            normalized_description="unknown merchant xyz",
            amount=Decimal("25.00"),
            date=date.today(),
            transaction_type=TransactionType.DEBIT
        ), "Should not match any rule"),
    ]

    for txn, expected in test_cases:
        engine.categorize_transaction(txn)
        print(f"\nDescription: {txn.description}")
        print(f"Type: {txn.transaction_type.value}")
        print(f"Expected: {expected}")
        print(f"Categorized: {txn.is_categorized()}")
        if txn.categorization:
            print(f"Category: {txn.categorization.category}")
            print(f"Confidence: {txn.categorization.confidence:.2%}")
            print(f"Reason: {txn.categorization.reasoning}")
        else:
            print(f"No match found")
        print("-" * 60)
