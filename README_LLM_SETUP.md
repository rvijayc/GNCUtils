# LLM Transaction Categorizer Setup Guide

## Overview
The LLM categorizer uses a REACT agent built with LangGraph that:
1. **Extracts merchant names** with improved logic (fixes "Netflix.com" → "COM" issue)
2. **Searches the internet** for merchant information using Tavily
3. **Categorizes intelligently** using GPT-4o-mini with world knowledge

## Prerequisites

### 1. Install Required Libraries
```bash
pip install langgraph langchain-openai langchain-community tavily-python tabulate
```

### 2. Get API Keys

**OpenAI API Key:**
- Go to https://platform.openai.com/api-keys
- Create a new API key
- Cost: ~$0.01-0.02 per transaction (very cheap with gpt-4o-mini)

**Tavily API Key (for web search):**
- Go to https://tavily.com/
- Sign up for free account
- Get API key from dashboard
- Free tier: 1000 searches/month

### 3. Set Environment Variables
```bash
export OPENAI_API_KEY="your-openai-api-key-here"
export TAVILY_API_KEY="your-tavily-api-key-here"
```

Or add to your `.bashrc`/`.zshrc`:
```bash
echo 'export OPENAI_API_KEY="your-key"' >> ~/.bashrc
echo 'export TAVILY_API_KEY="your-key"' >> ~/.bashrc
source ~/.bashrc
```

## Testing the LLM Categorizer

### Test Single Transactions
```bash
# Test the Netflix issue that was failing
./gpython3 llm_categorizer.py "Netflix.com            408-54037"

# Test other merchants
./gpython3 llm_categorizer.py "STARBUCKS 12345 SAN DIEGO CA"
./gpython3 llm_categorizer.py "UBER TRIP 12345"
./gpython3 llm_categorizer.py "TARGET 00028555 SAN DIEGO"

# Verbose mode to see detailed reasoning
./gpython3 llm_categorizer.py "Netflix.com 408-54037" --verbose
```

### Test Multiple Transactions
Create a test file `test_transactions.txt`:
```
Netflix.com            408-54037
STARBUCKS 800-782-7282 800-782-7
LinkedInPre *28136056  855-65356
UCSD PARKING MOBILE EB www.parkm
PAYPAL *SPOTIFY        402935773
```

Then run:
```bash
./gpython3 llm_categorizer.py --file test_transactions.txt --verbose
```

### Expected Output
The LLM categorizer should correctly identify:
- **Netflix** → `Expenses:Entertainment:Streaming Services`
- **Starbucks** → `Expenses:Food:Dining Out` 
- **LinkedIn** → `Expenses:Business:Software` or `Expenses:Subscriptions:Software`
- **Spotify** → `Expenses:Entertainment:Streaming Services`

## Key Features

### 1. Improved Merchant Extraction
```python
# Old system: "Netflix.com" → "COM" (wrong!)
# New system: "Netflix.com" → "Netflix" (correct!)
```

### 2. Internet Search Integration
- Searches for "[merchant] business type category what is"
- Gets real-world information about the business
- Uses this context for intelligent categorization

### 3. LLM Reasoning
- Provides detailed explanations for categorization decisions
- High confidence scores for well-known merchants
- Fallback handling for unknown businesses

### 4. Cost Effective
- Uses GPT-4o-mini (~$0.15 per 1M tokens)
- Typical transaction costs ~$0.01-0.02
- Much cheaper than GPT-4

## Architecture

```
Transaction Description
        ↓
1. Extract Merchant (improved regex)
        ↓ 
2. Search Internet (Tavily API)
        ↓
3. LLM Categorization (GPT-4o-mini)
        ↓
Category + Confidence + Reasoning
```

## Integration with QFX Parser

Once this works well, we can integrate it into the main QFX parser as a fallback:

```python
# Pseudo-code for hybrid approach:
if high_confidence_rule_match:
    return rule_category
elif medium_confidence_rule_match:
    return rule_category  # but flag for review
else:
    return llm_categorize(description)  # Use LLM for unknown transactions
```

## Troubleshooting

**Import Errors:**
- Make sure you're using `./gpython3` to run in the correct conda environment
- Install missing packages with `pip install <package>`

**API Key Errors:**
- Verify environment variables are set: `echo $OPENAI_API_KEY`
- Make sure keys don't have extra spaces or quotes

**Network Errors:**
- Tavily search requires internet connection
- Check if your network blocks API calls

## Next Steps

1. **Test thoroughly** with your actual QFX transactions
2. **Tune categories** to match your GNUCash account structure  
3. **Integrate** with the main QFX parser
4. **Create enhanced rules** system with manual YAML rules
