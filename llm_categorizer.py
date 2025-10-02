#!/usr/bin/env python3
"""
LLM-based Transaction Categorizer - Transaction-Based Architecture

Integrated workflow:
1. Rules Engine: Check manual/history/AI rules first (works with Transaction objects)
2. Credit Filter: Auto-return "Unspecified" for credit transactions
3. Phase 1 LLM: Try categorization using LLM knowledge (generates regex)
4. Phase 2 LLM: Fall back to internet search if uncertain
5. Updates Transaction.categorization field with CategorizationResult

Integrates with:
- rules_engine.py for priority-based rule matching (Transaction-based)
- core_models.py for Transaction and CategorizationResult dataclasses
- rules_db.py for AI rules caching
- category_extractor.py for valid categories
- description_normalizer.py for consistent normalization

Architecture:
- Works with Transaction objects (not primitive strings)
- Populates transaction.categorization field with CategorizationResult
- Maintains separation between transaction facts and categorization state
"""

import sys
import json
import argparse
import os
from typing import Dict, List, Optional, TypedDict
from datetime import datetime
from pathlib import Path

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

from rich.table import Table
from rich.console import Console
from rich.progress import Progress

from core_models import (
    CategorizationRule,
    CategorizationResult,
    RuleType,
    RuleSource,
    Transaction,
    TransactionType
)
from rules_db import save_history_rules
from description_normalizer import normalize_description
from rules_engine import RulesEngine, RuleMatchResult


class AgentState(TypedDict, total=False):
    """State for the categorization agent with static typing."""
    normalized_description: str
    original_description: str
    category: str
    merchant: str
    regex: str  # Generated regex pattern for matching similar transactions
    confidence: float
    needs_search: bool
    search_results: str
    reasoning: str
    phase: str


class LLMTransactionCategorizer:
    """
    LLM-based transaction categorizer with rules engine integration.

    Workflow:
    1. Check rules engine (manual/history/AI rules)
    2. If no match, run two-phase LLM categorization
    3. Cache results in ai_rules.yaml
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        tavily_api_key: Optional[str] = None,
        categories_file: Optional[str] = None,
        rules_engine: Optional[RulesEngine] = None,
        ai_rules_file: str = "ai_rules.yaml"
    ):
        """
        Initialize LLM categorizer with rules engine.

        Args:
            openai_api_key: OpenAI API key
            tavily_api_key: Tavily API key (optional, for Phase 2)
            categories_file: JSON file with valid categories
            rules_engine: Pre-configured rules engine (or creates default)
            ai_rules_file: YAML file for caching AI-generated rules
        """
        # Initialize API keys
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")

        if not self.openai_api_key:
            raise ValueError("OpenAI API key required.")

        if not self.tavily_api_key:
            print("Warning: Tavily API key not found. Phase 2 search will be disabled.")
            self.search_enabled = False
        else:
            self.search_enabled = True

        # Initialize LLM
        self.llm = ChatOpenAI(
            api_key=self.openai_api_key,
            model="gpt-4o-mini",
            temperature=0.1
        )

        # Initialize search tool
        if self.search_enabled:
            self.search_tool = TavilySearch(
                api_key=self.tavily_api_key,
                max_results=3,
                search_depth="basic"
            )
        else:
            self.search_tool = None

        # Load categories
        self.categories = self._load_categories(categories_file)

        # Initialize or use provided rules engine
        self.rules_engine = rules_engine or RulesEngine()

        # AI rules cache (for updating)
        self.ai_rules_file = ai_rules_file
        self.new_ai_rules: List[CategorizationRule] = []

        # Statistics
        self.stats = {
            'rules_engine_hits': 0,
            'phase1_success': 0,
            'phase2_search': 0,
            'total_processed': 0
        }

        # Create LangGraph agent
        self.agent = self._create_agent()

    def _load_categories(self, categories_file: Optional[str]) -> List[str]:
        """Load valid categories from JSON file."""
        if not categories_file or not Path(categories_file).exists():
            print("Warning: No categories file. Using defaults.")
            return self._get_default_categories()

        try:
            with open(categories_file, 'r') as f:
                data = json.load(f)
                categories = data.get('categories', [])
                print(f"Loaded {len(categories)} categories")
                return categories
        except Exception as e:
            print(f"Error loading categories: {e}")
            return self._get_default_categories()

    def _get_default_categories(self) -> List[str]:
        """Fallback default categories."""
        return [
            "Expenses.Dining Out",
            "Expenses.Groceries",
            "Expenses.Automobile.Gasoline",
            "Unspecified"
        ]

    def _create_agent(self) -> StateGraph:
        """Create LangGraph agent with two-phase categorization."""

        def phase1_categorize_node(state: AgentState) -> AgentState:
            """Phase 1: Categorize using LLM knowledge, generate regex."""
            description = state["normalized_description"]

            # Format all categories for display
            categories_list = "\n".join([f"- {cat}" for cat in self.categories])

            prompt = f"""You are an expert at categorizing financial transactions.

Transaction Description: {description}

AVAILABLE CATEGORIES (you MUST use exactly one of these):
{categories_list}

CRITICAL RULES:
1. You MUST choose a category from the list above - DO NOT invent new categories
2. Use the EXACT category name as shown (including dots and capitalization)
3. For well-known merchants, categorize confidently
4. Generate a regex pattern to match similar transactions (e.g., "chipotle.*" for all Chipotles)
5. Credit card payments ("INTERNET PAYMENT") → "Unspecified"
6. If uncertain about the merchant (< 0.7 confidence), set needs_search=true

MERCHANT-SPECIFIC GUIDELINES:
- Pharmacies (CVS, Walgreens, Rite Aid): Default to "Expenses.Healthcare.Counter" (most purchases are OTC, not prescriptions)
- Gas stations with convenience stores (7-Eleven, Circle K): If the name mentions "gas" use "Expenses.Automobile.Gasoline", otherwise use the store category
- Multi-department stores (Costco, Target, Walmart): Cannot determine specific category - use the broadest applicable category
- Costco Gas: Use "Expenses.Automobile.Gasoline" (not Groceries)
- Airport transactions: Most likely parking unless explicitly airfare

Respond in JSON format (NO markdown, raw JSON only):
{{
    "category": "Expenses.Category.Subcategory",
    "merchant": "Merchant name if identifiable",
    "regex": "regex pattern to match similar transactions",
    "confidence": 0.95,
    "needs_search": false,
    "reasoning": "Brief explanation"
}}"""

            messages = [HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)

            try:
                result = json.loads(response.content)

                # Validate category exists in our list
                proposed_category = result.get("category", "Unspecified")
                if proposed_category not in self.categories:
                    print(f"Warning: LLM proposed invalid category '{proposed_category}', using 'Unspecified'")
                    state["category"] = "Unspecified"
                    state["confidence"] = 0.0
                    state["needs_search"] = True
                else:
                    state["category"] = proposed_category
                    state["confidence"] = float(result.get("confidence", 0.0))
                    state["needs_search"] = result.get("needs_search", False)

                state["merchant"] = result.get("merchant", "")
                state["regex"] = result.get("regex", "")
                state["reasoning"] = result.get("reasoning", "")
                state["phase"] = "phase1"

                if state["confidence"] >= 0.7 and not state["needs_search"]:
                    self.stats['phase1_success'] += 1
                    state["search_results"] = "Not needed"

            except json.JSONDecodeError as e:
                print(f"JSON parse error in phase1: {e}")
                state["category"] = "Unspecified"
                state["confidence"] = 0.0
                state["needs_search"] = True
                state["regex"] = ""

            return state

        def search_node(state: AgentState) -> AgentState:
            """Search for transaction information."""
            if not self.search_enabled:
                state["search_results"] = "Search disabled"
                return state

            description = state["original_description"]

            try:
                query = f"{description} company business type"
                output = self.search_tool.invoke(query)

                if not output or not output.get('results'):
                    state["search_results"] = "No results"
                    return state

                results = output['results']
                combined = []
                for r in results[:3]:
                    if isinstance(r, dict) and r.get('content'):
                        combined.append(r['content'][:200])

                state["search_results"] = " | ".join(combined) if combined else "No info"
                self.stats['phase2_search'] += 1

            except Exception as e:
                state["search_results"] = f"Search error: {e}"

            return state

        def phase2_categorize_node(state: AgentState) -> AgentState:
            """Phase 2: Categorize with search results."""
            description = state["normalized_description"]
            search_results = state.get("search_results", "")

            # Format all categories for display
            categories_list = "\n".join([f"- {cat}" for cat in self.categories])

            prompt = f"""Categorize this transaction using search results.

Description: {description}
Search Results: {search_results}

AVAILABLE CATEGORIES (you MUST use exactly one of these):
{categories_list}

CRITICAL RULES:
1. You MUST choose a category from the list above - DO NOT invent new categories
2. Use the EXACT category name as shown (including dots and capitalization)
3. Use search results to determine the correct business type
4. Generate a regex pattern to match similar transactions

MERCHANT-SPECIFIC GUIDELINES:
- Pharmacies (CVS, Walgreens, Rite Aid): Default to "Expenses.Healthcare.Counter" (most purchases are OTC, not prescriptions)
- Gas stations with convenience stores (7-Eleven, Circle K): If the name mentions "gas" use "Expenses.Automobile.Gasoline", otherwise use the store category
- Multi-department stores (Costco, Target, Walmart): Cannot determine specific category - use the broadest applicable category
- Costco Gas: Use "Expenses.Automobile.Gasoline" (not Groceries)
- Airport transactions: Most likely parking unless explicitly airfare

Respond in JSON format (NO markdown, raw JSON only):
{{
    "category": "Expenses.Category.Subcategory",
    "merchant": "Official merchant name from search",
    "regex": "regex pattern for similar transactions",
    "confidence": 0.95,
    "reasoning": "Detailed explanation"
}}"""

            messages = [HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)

            try:
                result = json.loads(response.content)

                # Validate category exists in our list
                proposed_category = result.get("category", "Unspecified")
                if proposed_category not in self.categories:
                    print(f"Warning: LLM proposed invalid category '{proposed_category}' in phase2, using 'Unspecified'")
                    state["category"] = "Unspecified"
                    state["confidence"] = 0.0
                else:
                    state["category"] = proposed_category
                    state["confidence"] = float(result.get("confidence", 0.0))

                state["merchant"] = result.get("merchant", state.get("merchant", ""))
                state["regex"] = result.get("regex", state.get("regex", ""))
                state["reasoning"] = result.get("reasoning", "")
                state["phase"] = "phase2"

            except json.JSONDecodeError as e:
                print(f"JSON parse error in phase2: {e}")
                # Keep phase1 results

            return state

        def should_search(state: AgentState) -> str:
            """Decide whether to search."""
            needs_search = state.get("needs_search", False)
            confidence = state.get("confidence", 0.0)

            if needs_search or confidence < 0.7:
                return "search"
            return "end"

        # Build graph
        workflow = StateGraph(AgentState)

        workflow.add_node("phase1_categorize", phase1_categorize_node)
        workflow.add_node("search", search_node)
        workflow.add_node("phase2_categorize", phase2_categorize_node)

        workflow.set_entry_point("phase1_categorize")

        workflow.add_conditional_edges(
            "phase1_categorize",
            should_search,
            {"search": "search", "end": END}
        )

        workflow.add_edge("search", "phase2_categorize")
        workflow.add_edge("phase2_categorize", END)

        return workflow.compile()

    def categorize_transaction(
        self,
        transaction: Transaction,
        verbose: bool = False
    ) -> Transaction:
        """
        Categorize a transaction using rules engine + LLM.

        Args:
            transaction: Transaction object to categorize
            verbose: Print details

        Returns:
            Same transaction object with categorization field populated
        """
        # Step 1: Try rules engine first
        match_result = self.rules_engine.match_transaction(transaction)

        if match_result.matched:
            self.stats['rules_engine_hits'] += 1
            if verbose:
                print(f"✓ Rules engine match: {transaction.normalized_description}")
                print(f"  Category: {match_result.rule.category}")
                print(f"  Reason: {match_result.reason}")

            transaction.categorization = CategorizationResult(
                category=match_result.rule.category,
                confidence=match_result.rule.confidence,
                matched_rule=match_result.rule,
                source=match_result.rule.rule_source,
                reasoning=match_result.reason
            )
            return transaction

        # Step 2: Run LLM agent
        if verbose:
            print(f"🔍 LLM Processing: {transaction.normalized_description}")

        initial_state: AgentState = {
            "normalized_description": transaction.normalized_description,
            "original_description": transaction.description,
            "category": "",
            "merchant": "",
            "regex": "",
            "confidence": 0.0,
            "needs_search": False,
            "search_results": "",
            "reasoning": "",
            "phase": ""
        }

        result = self.agent.invoke(initial_state)
        self.stats['total_processed'] += 1

        if verbose:
            phase_label = f"PHASE {result.get('phase', '?')[-1]}"
            print(f"  [{phase_label}] {result['category']} (conf: {result['confidence']:.1%})")
            print(f"  Merchant: {result.get('merchant', 'N/A')}")
            print(f"  Regex: {result.get('regex', 'N/A')}")

        # Cache result if confident
        if result['confidence'] >= 0.7 and result.get('regex'):
            rule = CategorizationRule(
                rule_type=RuleType.REGEX,
                rule_source=RuleSource.AI_GENERATED,
                pattern=result['regex'],
                category=result['category'],
                merchant_name=result.get('merchant', ''),
                description=result.get('reasoning', ''),
                confidence=result['confidence']
            )
            self.new_ai_rules.append(rule)

        # Create categorization result
        transaction.categorization = CategorizationResult(
            category=result['category'],
            confidence=result['confidence'],
            matched_rule=None,  # No specific rule matched (LLM-generated)
            source=RuleSource.AI_GENERATED,
            reasoning=result.get('reasoning', '')
        )

        return transaction

    def categorize_batch(
        self,
        transactions: List[Transaction],
        verbose: bool = False
    ) -> List[Transaction]:
        """Categorize multiple transactions."""
        if verbose:
            with Progress() as progress:
                task = progress.add_task("[cyan]Categorizing...", total=len(transactions))
                for txn in transactions:
                    self.categorize_transaction(txn, verbose=False)
                    progress.update(task, advance=1)
        else:
            for txn in transactions:
                self.categorize_transaction(txn, verbose=False)

        return transactions

    def save_ai_rules(self) -> None:
        """Save newly generated AI rules to file."""
        if not self.new_ai_rules:
            print("No new AI rules to save")
            return

        # Merge with existing AI rules from rules engine
        all_ai_rules = self.rules_engine.ai_rules + self.new_ai_rules

        # Remove duplicates by pattern
        unique_rules = {}
        for rule in all_ai_rules:
            unique_rules[rule.pattern] = rule

        metadata = {
            'total_rules': len(unique_rules),
            'last_updated': datetime.now().isoformat(),
            'stats': self.stats
        }

        save_history_rules(list(unique_rules.values()), self.ai_rules_file, metadata)
        print(f"Saved {len(unique_rules)} AI rules to {self.ai_rules_file}")

    def print_stats(self) -> None:
        """Print categorization statistics."""
        print("\n" + "="*60)
        print("CATEGORIZATION STATISTICS")
        print("="*60)
        print(f"Total processed: {self.stats['total_processed']}")
        print(f"Rules engine hits: {self.stats['rules_engine_hits']}")
        print(f"Phase 1 success (no search): {self.stats['phase1_success']}")
        print(f"Phase 2 (with search): {self.stats['phase2_search']}")

        total = self.stats['total_processed'] + self.stats['rules_engine_hits']
        if total > 0:
            rules_rate = self.stats['rules_engine_hits'] / total * 100
            search_rate = self.stats['phase2_search'] / self.stats['total_processed'] * 100 if self.stats['total_processed'] > 0 else 0

            print(f"\nRules engine hit rate: {rules_rate:.1f}%")
            print(f"Search rate: {search_rate:.1f}%")


def display_results(transactions: List[Transaction]) -> None:
    """Display categorization results."""
    console = Console()
    table = Table(show_header=True, header_style="bold magenta")

    table.add_column("Description", style="white", max_width=25)
    table.add_column("Category", style="green", max_width=25)
    table.add_column("Conf", style="yellow")
    table.add_column("Source", style="blue")

    for txn in transactions:
        desc = txn.normalized_description[:25]

        if txn.categorization:
            category = txn.categorization.category[:25]
            confidence = f"{txn.categorization.confidence:.0%}"
            source = txn.categorization.source.value if txn.categorization.source else "?"
        else:
            category = "Uncategorized"
            confidence = "0%"
            source = "N/A"

        table.add_row(desc, category, confidence, source)

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="LLM categorizer with rules engine",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--description', '-d', help='Single description')
    parser.add_argument('--file', '-f', help='File with descriptions (one per line)')
    parser.add_argument('--categories', '-c', help='JSON file with categories')
    parser.add_argument('--manual-rules', help='Manual rules YAML')
    parser.add_argument('--history-rules', help='History rules YAML')
    parser.add_argument('--ai-rules', '-a', default='ai_rules.yaml', help='AI rules YAML')
    parser.add_argument('--no-history', action='store_true', help='Skip history rules')
    parser.add_argument('--no-ai', action='store_true', help='Skip AI rules')
    parser.add_argument('--output', '-o', help='Output JSON file')
    parser.add_argument('--verbose', '-v', action='store_true')

    args = parser.parse_args()

    if not args.description and not args.file:
        parser.error("Must provide --description or --file")

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        sys.exit(1)

    # Initialize rules engine
    rules_engine = RulesEngine(
        manual_rules_file=args.manual_rules,
        history_rules_file=args.history_rules,
        ai_rules_file=args.ai_rules,
        use_history=not args.no_history,
        use_ai=not args.no_ai
    )

    # Initialize categorizer
    try:
        categorizer = LLMTransactionCategorizer(
            categories_file=args.categories,
            rules_engine=rules_engine,
            ai_rules_file=args.ai_rules
        )
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Process
    if args.description:
        from datetime import date
        from decimal import Decimal

        normalized = normalize_description(args.description)

        # Create Transaction object
        txn = Transaction(
            description=args.description,
            normalized_description=normalized,
            amount=Decimal("0.00"),  # Unknown amount for manual testing
            date=date.today(),
            transaction_type=TransactionType.DEBIT
        )

        categorizer.categorize_transaction(txn, verbose=args.verbose)

        if not args.verbose:
            display_results([txn])

        if args.output:
            output_data = {
                "description": txn.description,
                "normalized_description": txn.normalized_description,
                "category": txn.categorization.category if txn.categorization else None,
                "confidence": txn.categorization.confidence if txn.categorization else 0.0,
                "source": txn.categorization.source.value if txn.categorization and txn.categorization.source else None,
                "reasoning": txn.categorization.reasoning if txn.categorization else ""
            }
            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2)

    elif args.file:
        from datetime import date
        from decimal import Decimal

        if not Path(args.file).exists():
            print(f"Error: File not found: {args.file}")
            sys.exit(1)

        with open(args.file, 'r') as f:
            descriptions = [line.strip() for line in f if line.strip()]

        # Create Transaction objects
        transactions = []
        for desc in descriptions:
            normalized = normalize_description(desc)
            txn = Transaction(
                description=desc,
                normalized_description=normalized,
                amount=Decimal("0.00"),
                date=date.today(),
                transaction_type=TransactionType.DEBIT
            )
            transactions.append(txn)

        print(f"Processing {len(transactions)} transactions...")
        categorizer.categorize_batch(transactions, verbose=args.verbose)

        if not args.verbose:
            display_results(transactions[:20])
            if len(transactions) > 20:
                print(f"\n... and {len(transactions) - 20} more")

        if args.output:
            output_data = []
            for txn in transactions:
                output_data.append({
                    "description": txn.description,
                    "normalized_description": txn.normalized_description,
                    "category": txn.categorization.category if txn.categorization else None,
                    "confidence": txn.categorization.confidence if txn.categorization else 0.0,
                    "source": txn.categorization.source.value if txn.categorization and txn.categorization.source else None,
                    "reasoning": txn.categorization.reasoning if txn.categorization else ""
                })
            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"\nResults saved to {args.output}")

        # Save AI rules
        categorizer.save_ai_rules()

        # Print stats
        categorizer.print_stats()


if __name__ == "__main__":
    main()
