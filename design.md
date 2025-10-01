# GNUCash Expense Categorization System - Design Document

## Overview

This document outlines the complete design for an automated transaction categorization system that builds upon the existing prototyping tools to create a production-ready solution. The design leverages the multi-layered architecture specified in `functional-specs.md` while refactoring and extending the existing codebase.

## System Architecture

### Core Design Principles

1. **Layered Architecture**: Maintain the three-layer approach (pre-processing, categorization, integration)
2. **Type Safety**: Use Python's `typing` module extensively for static type checking
3. **Exception Propagation**: Minimal graceful error handling to aid debugging
4. **Modular Design**: Clear separation of concerns with well-defined interfaces
5. **Backward Compatibility**: Versioned data formats for future extensibility

## Data Models (Dataclasses)

### Core Transaction Types

```python
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import date
from enum import Enum
from decimal import Decimal

class TransactionType(Enum):
    DEBIT = "debit"
    CREDIT = "credit"

class RuleType(Enum):
    EXACT_MATCH = "exact_match"
    CONTAINS = "contains" 
    REGEX = "regex"

class RuleSource(Enum):
    MANUAL = "manual"
    HISTORY_BASED = "history_based"
    AI_GENERATED = "ai_generated"

@dataclass
class ParsedTransaction:
    """Represents a transaction parsed from QFX/OFX files"""
    id: str
    date: date
    description: str
    raw_description: str
    normalized_description: str  # After normalization
    amount: Decimal
    transaction_type: TransactionType
    account_id: str
    memo: Optional[str] = None
    fitid: Optional[str] = None

@dataclass
class HistoricalTransaction:
    """Represents a transaction read from GNUCash database for analysis"""
    id: str
    date: date
    description: str
    amount: Decimal
    credit_card_account: str
    category_account: str
    category_full_path: str
    memo: Optional[str] = None

@dataclass 
class CategorizationRule:
    """Represents a single categorization rule"""
    rule_type: RuleType
    rule_source: RuleSource
    pattern: str
    category: str
    transaction_type: Optional[TransactionType] = None
    merchant_name: Optional[str] = None
    description: Optional[str] = None
    confidence: float = 0.0
    
    # Metadata for rule evaluation (used by history-based rules)
    transaction_count: int = 0
    total_transactions: int = 0
    example_descriptions: List[str] = field(default_factory=list)

@dataclass
class CategoryMatch:
    """Result of applying a categorization rule to a transaction"""
    rule: CategorizationRule
    confidence: float
    matched: bool
    explanation: str
    extracted_merchant: Optional[str] = None

@dataclass
class CategorizedTransaction:
    """Transaction with categorization applied"""
    transaction: ParsedTransaction
    predicted_category: str
    best_match: CategoryMatch
    all_matches: List[CategoryMatch] = field(default_factory=list)
    final_confidence: float = 0.0
    needs_review: bool = False
    
@dataclass
class TransactionBatch:
    """Collection of categorized transactions with metadata"""
    transactions: List[CategorizedTransaction]
    total_count: int
    categorized_count: int
    uncategorized_count: int
    low_confidence_count: int
    processing_timestamp: str
    
    @property
    def categorization_rate(self) -> float:
        return self.categorized_count / self.total_count if self.total_count > 0 else 0.0
```

## Rules Database Format with Versioning

### Separate YAML Files for Different Rule Sources

Each rule source uses its own YAML file for independent management:

#### 1. Manual Rules File (`manual_rules.yaml`)
```yaml
version: "1.0"
description: "Manually specified rules (highest priority)"
rules:
  - rule_type: "exact_match"
    pattern: "internet payment thank you"
    category: "Unspecified"
    transaction_type: "credit"
    description: "Credit card bill payments"
    confidence: 1.0
    
  - rule_type: "contains" 
    pattern: "netflix"
    category: "Expenses:Bills:Streaming Services"
    merchant_name: "Netflix"
    confidence: 0.95
    
  - rule_type: "regex"
    pattern: "uber.*trip"
    category: "Expenses:Transportation:Rideshare"
    merchant_name: "Uber"
    confidence: 0.9
```

#### 2. History-Based Rules File (`history_rules.yaml`)
```yaml
version: "1.0"
description: "Rules generated from historical GNUCash data"
generation_config:
  minimum_transactions: 2
  confidence_threshold: 0.3
  date_range:
    start_date: "2023-01-01"
    end_date: "2024-12-31"
rules:
  - rule_type: "contains"
    pattern: "starbucks"
    category: "Expenses:Dining Out"
    merchant_name: "Starbucks"
    confidence: 0.85
    transaction_count: 15
    total_transactions: 15
    example_descriptions: ["STARBUCKS 12345 SAN DIEGO", "STARBUCKS STORE #5678"]
    
  - rule_type: "contains"
    pattern: "costco"
    category: "Expenses:Groceries"
    merchant_name: "Costco"
    confidence: 0.92
    transaction_count: 8
    total_transactions: 8
    example_descriptions: ["COSTCO WHOLESALE #1234", "COSTCO GAS STATION"]
```

#### 3. AI-Generated Rules File (`ai_rules.yaml`)
```yaml
version: "1.0"
description: "AI-generated rules with internet search"
model_config:
  model: "gpt-4o-mini"
  temperature: 0.1
  search_provider: "tavily"
rules:
  - rule_type: "contains"
    pattern: "thai sport bodyworks"
    category: "Expenses:Healthcare:Athletic Club"
    merchant_name: "Thai Sport Bodyworks"
    confidence: 0.9
    reasoning: "Thai Sport Bodyworks appears to be a fitness/wellness facility offering massage and bodywork services."
    
  - rule_type: "contains"
    pattern: "linked premium"
    category: "Expenses:Household:Software"
    merchant_name: "LinkedIn"
    confidence: 0.88
    reasoning: "LinkedIn Premium is a professional networking subscription service."
```

### Rules Database Dataclass

```python
@dataclass
class RulesDatabase:
    """Container for categorization rules from multiple sources"""
    manual_rules: List[CategorizationRule] = field(default_factory=list)
    history_rules: List[CategorizationRule] = field(default_factory=list) 
    ai_rules: List[CategorizationRule] = field(default_factory=list)
    
    def get_all_rules(self) -> List[CategorizationRule]:
        """Return all rules sorted by source priority (manual > history > ai)"""
        all_rules = []
        
        # Add manual rules with priority 1-99
        for i, rule in enumerate(self.manual_rules):
            rule_copy = rule
            rule_copy.priority = i + 1
            all_rules.append(rule_copy)
            
        # Add history rules with priority 100-199  
        for i, rule in enumerate(self.history_rules):
            rule_copy = rule
            rule_copy.priority = i + 100
            all_rules.append(rule_copy)
            
        # Add AI rules with priority 200+
        for i, rule in enumerate(self.ai_rules):
            rule_copy = rule
            rule_copy.priority = i + 200
            all_rules.append(rule_copy)
            
        return sorted(all_rules, key=lambda r: r.priority)
    
    @classmethod
    def load_from_files(cls, 
                       manual_rules_file: Optional[str] = None,
                       history_rules_file: Optional[str] = None, 
                       ai_rules_file: Optional[str] = None) -> 'RulesDatabase':
        """Load rules database from separate YAML files"""
        database = cls()
        
        if manual_rules_file:
            database.manual_rules = cls._load_rules_from_file(manual_rules_file, RuleSource.MANUAL)
        if history_rules_file:
            database.history_rules = cls._load_rules_from_file(history_rules_file, RuleSource.HISTORY_BASED)  
        if ai_rules_file:
            database.ai_rules = cls._load_rules_from_file(ai_rules_file, RuleSource.AI_GENERATED)
            
        return database
    
    @classmethod
    def _load_rules_from_file(cls, filepath: str, source: RuleSource) -> List[CategorizationRule]:
        """Load rules from a single YAML file"""
        # Implementation to deserialize from YAML format
        pass
        
    def save_to_files(self, 
                     manual_rules_file: Optional[str] = None,
                     history_rules_file: Optional[str] = None,
                     ai_rules_file: Optional[str] = None) -> None:
        """Save rules to separate YAML files"""
        if manual_rules_file and self.manual_rules:
            self._save_rules_to_file(self.manual_rules, manual_rules_file)
        if history_rules_file and self.history_rules:
            self._save_rules_to_file(self.history_rules, history_rules_file)
        if ai_rules_file and self.ai_rules:
            self._save_rules_to_file(self.ai_rules, ai_rules_file)
    
    def _save_rules_to_file(self, rules: List[CategorizationRule], filepath: str) -> None:
        """Save rules to a single YAML file"""
        # Implementation to serialize to YAML format
        pass
```

## Component Architecture

### 1. Transaction Analyzer (Refactored)

```python
class TransactionAnalyzer:
    """Analyzes historical GNUCash data and generates categorization rules"""
    
    def __init__(self, gnucash_file: str, config: Optional[Dict] = None):
        self.gnucash_file = gnucash_file
        self.config = config or {}
        self.extracted_transactions: List[ParsedTransaction] = []
        
    def extract_historical_transactions(self, 
                                      accounts: List[str], 
                                      date_range: Optional[Dict] = None) -> List[ParsedTransaction]:
        """Extract and normalize historical transactions"""
        pass
        
    def analyze_categorization_patterns(self) -> List[CategorizationRule]:
        """Generate rules using multiple analysis techniques"""
        pass
        
    def generate_history_based_rules(self) -> RulesDatabase:
        """Create a rules database from historical analysis"""
        pass
```

### 2. QFX Parser Library (Refactored)

```python
class QFXTransactionParser:
    """Parses QFX files and normalizes transaction descriptions"""
    
    def parse_qfx_file(self, qfx_filepath: str) -> List[ParsedTransaction]:
        """Parse QFX file and return normalized transactions"""
        pass
        
    def normalize_description(self, description: str) -> str:
        """Normalize description (no merchant extraction here)"""
        pass
```

### 3. Rule Engine

```python
class RuleEngine:
    """Applies categorization rules to transactions"""
    
    def __init__(self, rules_database: RulesDatabase):
        self.rules_database = rules_database
        
    def apply_rules(self, transaction: ParsedTransaction, 
                   confidence_threshold: float = 0.3) -> CategoryMatch:
        """Apply all applicable rules and return best match"""
        pass
        
    def categorize_batch(self, transactions: List[ParsedTransaction]) -> TransactionBatch:
        """Categorize multiple transactions efficiently"""
        pass
```

### 4. AI Categorization Agent (Refactored)

```python
class AICategorizeationAgent:
    """LLM-powered categorization with search capabilities"""
    
    def __init__(self, openai_key: str, tavily_key: str, rules_database: RulesDatabase):
        self.rules_database = rules_database
        self.llm_client = ChatOpenAI(api_key=openai_key, model="gpt-4o-mini")
        self.search_client = TavilySearch(api_key=tavily_key)
        
    def categorize_transaction(self, transaction: ParsedTransaction) -> CategoryMatch:
        """Use AI to categorize a single transaction"""
        pass
        
    def batch_categorize(self, transactions: List[ParsedTransaction]) -> List[CategoryMatch]:
        """Efficiently categorize multiple transactions with caching"""
        pass
        
    def update_rules_cache(self, new_matches: List[CategoryMatch]) -> None:
        """Add successful AI categorizations to rules database for reuse"""
        pass
```

### 5. Transaction Categorization Engine (New Top-Level Component)

```python
class TransactionCategorizationEngine:
    """Orchestrates the complete categorization workflow"""
    
    def __init__(self, 
                 gnucash_file: str,
                 rules_database: RulesDatabase,
                 ai_agent: Optional[AICategorizeationAgent] = None):
        self.gnucash_file = gnucash_file
        self.rules_database = rules_database
        self.ai_agent = ai_agent
        self.parser = QFXTransactionParser()
        self.rule_engine = RuleEngine(rules_database)
        
    def process_qfx_file(self, qfx_file: str, 
                        confidence_threshold: float = 0.3,
                        use_ai_fallback: bool = True) -> ProcessingResult:
        """Complete end-to-end processing pipeline"""
        
        # 1. Parse QFX transactions
        transactions = self.parser.parse_qfx_file(qfx_file)
        
        # 2. Apply rule-based categorization
        categorized_batch = self.rule_engine.categorize_batch(transactions)
        
        # 3. Use AI for uncategorized transactions (if enabled)
        if use_ai_fallback and self.ai_agent:
            uncategorized = [t for t in categorized_batch.transactions 
                           if not t.best_match.matched]
            ai_results = self.ai_agent.batch_categorize([t.transaction for t in uncategorized])
            
            # Update results with AI categorizations
            for transaction, ai_match in zip(uncategorized, ai_results):
                if ai_match.confidence >= confidence_threshold:
                    transaction.best_match = ai_match
                    transaction.predicted_category = ai_match.rule.category
        
        # 4. Generate summary and prepare for review
        return ProcessingResult(
            categorized_batch=categorized_batch,
            summary=self._generate_summary(categorized_batch),
            requires_approval=True
        )
    
    def apply_categorizations_to_gnucash(self, 
                                       processing_result: ProcessingResult) -> None:
        """Apply approved categorizations to GNUCash database"""
        pass
        
    def _generate_summary(self, batch: TransactionBatch) -> Dict:
        """Generate rich summary for user review"""
        pass

@dataclass
class ProcessingResult:
    """Result of complete processing pipeline"""
    categorized_batch: TransactionBatch
    summary: Dict[str, Any]
    requires_approval: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
```

## UML Class Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    TransactionCategorizationEngine              │
├─────────────────────────────────────────────────────────────────┤
│ - gnucash_file: str                                             │
│ - rules_database: RulesDatabase                                 │
│ - ai_agent: AICategorizeationAgent                             │
│ - parser: QFXTransactionParser                                  │
│ - rule_engine: RuleEngine                                       │
├─────────────────────────────────────────────────────────────────┤
│ + process_qfx_file(qfx_file: str): ProcessingResult            │
│ + apply_categorizations_to_gnucash(result: ProcessingResult)    │
└─────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
    ┌───────────────────────┐ ┌─────────────────┐ ┌──────────────────────┐
    │ QFXTransactionParser  │ │   RuleEngine    │ │ AICategorizeation    │
    ├───────────────────────┤ ├─────────────────┤ │      Agent           │
    │ + parse_qfx_file()    │ │ - rules_database│ ├──────────────────────┤
    │ + normalize_desc()    │ │ + apply_rules() │ │ - llm_client         │
    │ + extract_merchant()  │ │ + categorize_   │ │ - search_client      │
    └───────────────────────┘ │   batch()       │ │ + categorize_trans() │
                              └─────────────────┘ │ + update_rules_cache()│
                                       │          └──────────────────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │ RulesDatabase   │
                              ├─────────────────┤
                              │ + version: str  │
                              │ + manual_rules  │
                              │ + history_rules │
                              │ + ai_rules      │
                              ├─────────────────┤
                              │ + get_all_rules()│
                              │ + add_rule()    │
                              │ + save_to_yaml()│
                              └─────────────────┘
                                       │
                                       │ contains
                                       ▼
                              ┌─────────────────┐
                              │Categorization   │
                              │     Rule        │
                              ├─────────────────┤
                              │ + rule_id: str  │
                              │ + rule_type     │
                              │ + pattern: str  │
                              │ + category: str │
                              │ + confidence    │
                              └─────────────────┘

┌─────────────────┐    processes    ┌─────────────────┐    creates    ┌─────────────────┐
│ ParsedTransaction│◄───────────────│                │──────────────►│ CategorizedTrans│
├─────────────────┤                 │   RuleEngine   │               ├─────────────────┤
│ + id: str       │                 │                │               │ + transaction   │
│ + description   │                 └─────────────────┘               │ + predicted_cat │
│ + amount        │                                                   │ + best_match    │
│ + normalized    │                                                   │ + confidence    │
└─────────────────┘                                                   └─────────────────┘
```

## Implementation Strategy

### Phase 1: Core Infrastructure
1. Implement dataclasses and type definitions
2. Create RulesDatabase with YAML serialization
3. Refactor existing common utilities in `gnc_common.py`

### Phase 2: Component Refactoring  
1. Refactor `TransactionAnalyzer` to use new data models
2. Refactor `QFXParser` into `QFXTransactionParser` library
3. Refactor `LLMCategorizer` into `AICategorizeationAgent`

### Phase 3: Integration Layer
1. Implement `RuleEngine` for rule application
2. Create `TransactionCategorizationEngine` orchestrator
3. Add GNUCash integration for applying categorizations

### Phase 4: Enhancement & Testing
1. Add comprehensive logging and debugging support
2. Create test suite with sample data
3. Performance optimization for large transaction volumes

## File Organization

```
gnc_utils/
├── design.md                     # This document
├── functional-specs.md           # Existing functional specs
├── core/                         # Core data models and types
│   ├── __init__.py
│   ├── models.py                # Dataclasses and enums
│   └── exceptions.py            # Custom exceptions
├── parsers/                      # Transaction parsing components  
│   ├── __init__.py
│   ├── qfx_parser.py            # Refactored QFX parser
│   └── description_normalizer.py
├── analysis/                     # Historical analysis components
│   ├── __init__.py
│   ├── transaction_analyzer.py   # Refactored analyzer
│   └── pattern_detector.py
├── rules/                        # Rule management
│   ├── __init__.py
│   ├── database.py              # RulesDatabase implementation
│   ├── engine.py                # RuleEngine implementation
│   └── serialization.py         # YAML handling
├── ai/                          # AI-powered components
│   ├── __init__.py
│   ├── categorization_agent.py  # Refactored LLM categorizer
│   └── search_client.py         # Search functionality
├── integration/                 # GNUCash integration
│   ├── __init__.py
│   ├── gnucash_session.py       # Session management
│   └── transaction_writer.py    # Write categorized transactions
├── engine.py                    # Main TransactionCategorizationEngine
├── cli/                         # Command-line interfaces
│   ├── __init__.py
│   ├── main.py                  # Main CLI entry point
│   ├── analyze.py               # Analysis CLI
│   ├── categorize.py            # Categorization CLI
│   └── debug.py                 # Debug tools CLI
└── utils/                       # Utilities
    ├── __init__.py
    ├── logging.py               # Logging configuration
    └── config.py                # Configuration management
```

## Backward Compatibility

The rules database versioning system ensures that:
1. Version 1.0 supports current functionality
2. Future versions (1.1+) can add multi-split transaction support
3. Version compatibility matrix guides migration strategies
4. Existing JSON rules can be migrated to YAML format

## Error Handling Philosophy

Following the requirement to avoid excessive graceful error handling:
- Use type hints extensively to catch errors at development time
- Let exceptions propagate with clear, descriptive messages
- Add logging for debugging without swallowing exceptions
- Use assertions for development-time constraint checking

This design provides a solid foundation for implementing the complete expense categorization system while leveraging and refactoring the existing prototyping work.
