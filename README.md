# GNC Utilities

A comprehensive suite of tools for streamlining transaction categorization and entry into GNUCash using advanced machine learning and rule-based approaches.

## 🎯 Overview

This project provides multiple approaches to automatically categorize financial transactions:

1. **Rule-based categorization** from historical GNUCash data
2. **LLM-powered intelligent categorization** with internet search
3. **QFX file parsing** and transaction processing
4. **Debugging and analysis tools** for fine-tuning

## 📋 Table of Contents

- [Installation](#installation)
- [Tools Overview](#tools-overview)
- [Quick Start Guide](#quick-start-guide)
- [Tool Documentation](#tool-documentation)
- [Workflow Examples](#workflow-examples)
- [Configuration](#configuration)

## 🚀 Installation

### Prerequisites

This project uses GNUCash Python Bindings which require compilation (via SWIG) for your specific Python version.

### Step 1: Create Environment

Create a conda environment with required dependencies:

```shell
conda env create -f environment.yaml
conda activate gnc
```

### Step 2: Build GNUCash (if needed)

If you need to build GNUCash with Python bindings:

```shell
git clone git@github.com:rvijayc/gnucash.git
# Follow build instructions in the gnucash repository
```

### Step 3: Install Additional Dependencies

For LLM-based categorization:

```shell
pip install langgraph langchain-openai langchain-tavily tavily-python rich
```

## 🛠️ Tools Overview

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| **analyze_transactions.py** | Generate categorization rules from GNUCash history | GNUCash file | JSON rules file |
| **qfx_parser.py** | Parse QFX files and apply categorization rules | QFX file + rules | Categorized transactions |
| **llm_categorizer.py** | AI-powered transaction categorization | Transaction descriptions | Intelligent categories |
| **match_transaction.py** | Debug transaction matching against rules | Transaction description | Matching analysis |
| **list_accounts.py** | List and analyze GNUCash account structure | GNUCash file | Account hierarchy |

## 🚀 Quick Start Guide

### 1. Generate Categorization Rules

Analyze your GNUCash history to create categorization rules:

```bash
# Analyze all credit card accounts
./gpython3 analyze_transactions.py ~/accounts.gnucash

# Use specific configuration
./gpython3 analyze_transactions.py ~/accounts.gnucash --config analyze_config.yaml
```

### 2. Parse QFX Files

Process QFX files from your bank/credit card:

```bash
# Basic parsing with auto-categorization
./gpython3 qfx_parser.py transactions.qfx

# Detailed analysis with suggestions
./gpython3 qfx_parser.py transactions.qfx --detailed --suggest-rules

# Save results
./gpython3 qfx_parser.py transactions.qfx --output results.json
```

### 3. LLM-Powered Categorization

For advanced AI-powered categorization:

```bash
# Set up API keys
export OPENAI_API_KEY="your-openai-key"
export TAVILY_API_KEY="your-tavily-key"

# Categorize single transaction
./gpython3 llm_categorizer.py "Netflix.com 408-54037" --verbose

# Batch process from file
./gpython3 llm_categorizer.py --file transactions.txt
```

## 📖 Tool Documentation

### 🔍 analyze_transactions.py

**Purpose**: Analyzes historical GNUCash transactions to generate intelligent categorization rules.

**Features**:
- Extracts transactions from credit card accounts
- Analyzes merchant patterns using multiple techniques
- Generates rules with confidence scores
- Supports fuzzy matching and word analysis

**Usage**:
```bash
./gpython3 analyze_transactions.py [gnucash_file] [options]

Options:
  --config, -c     YAML configuration file
  --output, -o     Output JSON file (default: categorization_rules.json)
```

**Output**: JSON file with categorization rules including:
- Merchant-based rules
- Fuzzy merchant matching
- Description pattern rules
- Confidence scores and transaction counts

### 📄 qfx_parser.py

**Purpose**: Parses QFX files downloaded from financial institutions and applies categorization rules.

**Features**:
- Robust QFX/OFX file parsing using `ofxparse`
- Rule-based transaction categorization
- Beautiful tabulated output using `tabulate`
- Confidence scoring and uncertainty detection
- Suggests new rules for uncategorized transactions

**Usage**:
```bash
./gpython3 qfx_parser.py [qfx_file] [options]

Options:
  --rules, -r      Rules file (default: categorization_rules.json)
  --output, -o     Output JSON file
  --detailed, -d   Show detailed transaction tables
  --confidence, -c Confidence threshold (default: 0.3)
  --suggest-rules  Suggest new rules for uncategorized transactions
```

**Output**:
- Categorized transactions with confidence scores
- Low-confidence matches needing review
- Uncategorized transactions requiring new rules
- Summary statistics and recommendations

### 🤖 llm_categorizer.py

**Purpose**: AI-powered transaction categorization using LLM and internet search.

**Architecture**: REACT agent (Reasoning + Acting) built with LangGraph

**Features**:
- GPT-4o-mini for cost-effective categorization
- Internet search integration via Tavily
- Handles complex/new merchants automatically
- Provides detailed reasoning for decisions
- No training data required

**Workflow**:
1. **Search**: Queries internet for merchant information
2. **Analyze**: LLM processes transaction + search results
3. **Categorize**: Returns structured JSON with category and confidence

**Usage**:
```bash
./gpython3 llm_categorizer.py [description] [options]

Environment Variables:
  OPENAI_API_KEY   Your OpenAI API key
  TAVILY_API_KEY   Your Tavily search API key

Options:
  --file, -f       File with transaction descriptions
  --output, -o     Output JSON file
  --verbose, -v    Show detailed reasoning
```

**Example**:
```bash
# Single transaction
./gpython3 llm_categorizer.py "Netflix.com 408-54037" --verbose

# Batch processing
./gpython3 llm_categorizer.py --file transactions.txt --output results.json
```

### 🔧 match_transaction.py

**Purpose**: Debug helper for analyzing how transaction descriptions match against rules.

**Features**:
- Step-by-step processing analysis
- Shows merchant extraction results
- Tests all rule types with explanations
- Confidence scoring breakdown
- Helps troubleshoot categorization issues

**Usage**:
```bash
./gpython3 match_transaction.py "[description]" [options]

Options:
  --rules, -r        Rules file
  --show-all, -a     Show all rules (including non-matches)
  --threshold, -t    Minimum confidence threshold
  --max-results, -m  Maximum results to show
```

**Example**:
```bash
# Debug specific transaction
./gpython3 match_transaction.py "STARBUCKS 12345 SAN DIEGO" --show-all

# Test with low threshold
./gpython3 match_transaction.py "Netflix.com" --threshold 0.1
```

### 📊 list_accounts.py

**Purpose**: Analyzes and lists GNUCash account structure.

**Features**:
- Hierarchical account display
- Account type analysis
- Configuration file generation
- Credit card account identification

**Usage**:
```bash
./gpython3 list_accounts.py [gnucash_file] [options]

Options:
  --generate-config  Create sample configuration file
  --type            Filter by account type
```

## 🔄 Workflow Examples

### Complete Transaction Processing Workflow

1. **Setup**: Generate initial rules from your GNUCash history
   ```bash
   ./gpython3 analyze_transactions.py ~/accounts.gnucash --config analyze_config.yaml
   ```

2. **Parse**: Process new QFX file from your bank
   ```bash
   ./gpython3 qfx_parser.py new_transactions.qfx --detailed --suggest-rules
   ```

3. **Review**: Debug any problematic transactions
   ```bash
   ./gpython3 match_transaction.py "UNKNOWN MERCHANT 12345"
   ```

4. **Enhance**: Use LLM for complex/new merchants
   ```bash
   ./gpython3 llm_categorizer.py "UNKNOWN MERCHANT 12345" --verbose
   ```

### Hybrid Approach (Recommended)

```bash
# 1. Try rules first (fast, deterministic)
./gpython3 qfx_parser.py transactions.qfx --confidence 0.7

# 2. Use LLM for uncertain transactions (intelligent fallback)
./gpython3 llm_categorizer.py --file uncertain_transactions.txt

# 3. Manual review of results and rule refinement
```

## ⚙️ Configuration

### analyze_config.yaml

Configure which accounts to analyze:

```yaml
credit_card_accounts:
  - "Liabilities:Credit Cards:Chase"
  - "Liabilities:Credit Cards:Amex"

date_range:
  start_date: "2023-01-01"
  end_date: "2024-12-31"

rule_settings:
  minimum_transactions: 2
  confidence_threshold: 0.3
  fuzzy_similarity: 0.8
```

### Environment Variables

```bash
# For LLM categorization
export OPENAI_API_KEY="your-openai-api-key"
export TAVILY_API_KEY="your-tavily-api-key"

# Optional: Custom model settings
export OPENAI_MODEL="gpt-4o-mini"
```

## 🎯 Key Benefits

- **Automated categorization** of financial transactions
- **Multiple approaches**: Rules + AI for maximum accuracy
- **Handles edge cases** that break traditional systems
- **Provides explanations** for categorization decisions
- **Continuous improvement** through new rule suggestions
- **Cost effective** (~$0.01-0.02 per transaction with LLM)

## 🔧 Troubleshooting

### Common Issues

1. **GNUCash import errors**: Ensure you're using `./gpython3` wrapper
2. **API key errors**: Verify environment variables are set correctly
3. **Library errors**: Install missing dependencies with `pip install <package>`
4. **Permission errors**: Check file permissions for GNUCash files

### Debug Tools

- Use `match_transaction.py` to understand rule matching
- Use `--verbose` flags for detailed processing information
- Check generated JSON outputs for data validation

## 📝 License

[Add your license information here]

## 🤝 Contributing

[Add contribution guidelines here]
