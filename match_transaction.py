#!/usr/bin/env python3
"""
Transaction Matching Debug Helper
Test how a transaction description matches against categorization rules
"""

import sys
import json
import argparse
import re
from pathlib import Path
from typing import List, Dict, Tuple
from difflib import SequenceMatcher

try:
    from tabulate import tabulate
except ImportError:
    print("Error: tabulate library not found.")
    print("Install with: pip install tabulate")
    sys.exit(1)


class TransactionMatcher:
    """Helper class to test transaction matching against rules."""
    
    def __init__(self, rules_file_path: str = 'categorization_rules.json'):
        self.rules_file_path = rules_file_path
        self.rules = []
    
    def load_rules(self) -> bool:
        """Load categorization rules from JSON file."""
        try:
            if not Path(self.rules_file_path).exists():
                print(f"Error: Rules file not found: {self.rules_file_path}")
                print("Run analyze_transactions.py first to generate categorization rules.")
                return False
                
            with open(self.rules_file_path, 'r') as f:
                rules_data = json.load(f)
            
            self.rules = rules_data.get('rules', [])
            print(f"Loaded {len(self.rules)} categorization rules from {self.rules_file_path}")
            return True
            
        except Exception as e:
            print(f"Error loading rules: {e}")
            return False
    
    def clean_description(self, description: str) -> str:
        """Clean and normalize transaction descriptions for pattern matching."""
        cleaned = description.lower()
        
        # Remove common transaction artifacts
        cleaned = re.sub(r'\d{2}/\d{2}(/\d{2,4})?', '', cleaned)  # Remove dates
        cleaned = re.sub(r'#\d+', '', cleaned)                    # Remove reference numbers
        cleaned = re.sub(r'\*+', '', cleaned)                     # Remove asterisks  
        cleaned = re.sub(r'\d{4,}', '', cleaned)                  # Remove long numbers (auth codes, etc.)
        cleaned = re.sub(r'\s+', ' ', cleaned)                    # Normalize whitespace
        cleaned = cleaned.strip()
        
        return cleaned
    
    def extract_merchant_name(self, description: str) -> str:
        """Extract and normalize merchant name from transaction description."""
        patterns = [
            r'PAYPAL \*([^0-9\s]+)',                    # PayPal transactions
            r'SQ \*([^0-9\s]+)',                       # Square transactions  
            r'TST\* ([^0-9\s]+)',                      # Toast/other POS
            r'AMZN MKTP ([^0-9\s]+)',                  # Amazon Marketplace
            r'UBER\s*([^0-9\s]*)',                     # Uber services
            r'LYFT\s*([^0-9\s]*)',                     # Lyft services
            r'SPOTIFY\s*([^0-9\s]*)',                  # Spotify
            r'NETFLIX\s*([^0-9\s]*)',                  # Netflix
            r'([A-Z][A-Z0-9\s&]+?)(?:\s+\d|\s*$)',     # General merchant pattern
        ]
        
        description_clean = description.upper().strip()
        
        for pattern in patterns:
            match = re.search(pattern, description_clean)
            if match:
                merchant = match.group(1).strip() if match.group(1) else match.group(0)
                # Clean up common artifacts
                merchant = re.sub(r'\s+', ' ', merchant)
                merchant = re.sub(r'[^A-Z0-9\s&]', '', merchant)
                merchant = merchant.strip()
                if len(merchant) > 2:
                    return merchant
        
        # Fallback: first few words as merchant name
        words = description_clean.split()
        merchant_words = []
        for word in words[:4]:  # Take up to 4 words
            if len(word) > 2 and not re.match(r'^\d+$', word):  # Skip short words and pure numbers
                merchant_words.append(word)
            if len(merchant_words) >= 2:  # Stop after getting 2 good words
                break
                
        return ' '.join(merchant_words) if merchant_words else description_clean[:20]
    
    def similarity_ratio(self, a: str, b: str) -> float:
        """Calculate similarity ratio between two strings."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def apply_rule(self, description: str, rule: Dict) -> Tuple[bool, float, str]:
        """Apply a single rule to a description and return (matched, confidence, explanation)."""
        rule_type = rule['type']
        pattern = rule['pattern']
        
        if rule_type == 'merchant_name':
            merchant = self.extract_merchant_name(description)
            if merchant.lower() == pattern.lower():
                return True, rule['confidence'], f"Extracted merchant '{merchant}' matches pattern '{pattern}'"
            else:
                return False, 0.0, f"Extracted merchant '{merchant}' does not match pattern '{pattern}'"
                
        elif rule_type == 'fuzzy_merchant':
            merchant = self.extract_merchant_name(description)
            # Check if merchant matches any variant
            variants = rule.get('variants', [pattern])
            best_similarity = 0.0
            best_variant = ''
            
            for variant in variants:
                similarity = self.similarity_ratio(merchant, variant)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_variant = variant
                    
            if best_similarity >= 0.8:
                return True, rule['confidence'], f"Extracted merchant '{merchant}' fuzzy matches variant '{best_variant}' (similarity: {best_similarity:.1%})"
            else:
                return False, 0.0, f"Extracted merchant '{merchant}' does not fuzzy match any variant (best: '{best_variant}', similarity: {best_similarity:.1%})"
                    
        elif rule_type == 'description_contains':
            cleaned_desc = self.clean_description(description)
            if pattern.lower() in cleaned_desc:
                return True, rule['confidence'], f"Cleaned description '{cleaned_desc}' contains pattern '{pattern}'"
            else:
                return False, 0.0, f"Cleaned description '{cleaned_desc}' does not contain pattern '{pattern}'"
                
        elif rule_type == 'description_exact':
            cleaned_desc = self.clean_description(description)
            if cleaned_desc == pattern.lower():
                return True, rule['confidence'], f"Cleaned description '{cleaned_desc}' exactly matches pattern '{pattern}'"
            else:
                return False, 0.0, f"Cleaned description '{cleaned_desc}' does not exactly match pattern '{pattern}'"
        
        return False, 0.0, f"Unknown rule type: {rule_type}"
    
    def find_matches(self, description: str, show_all: bool = False, confidence_threshold: float = 0.0) -> List[Dict]:
        """Find all matching rules for a transaction description."""
        matches = []
        
        for rule in self.rules:
            matched, confidence, explanation = self.apply_rule(description, rule)
            
            if matched or show_all:
                match_info = {
                    'rule': rule,
                    'matched': matched,
                    'confidence': confidence,
                    'explanation': explanation
                }
                
                if confidence >= confidence_threshold:
                    matches.append(match_info)
        
        # Sort by confidence (highest first)
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        return matches
    
    def debug_transaction(self, description: str, show_all: bool = False, 
                         confidence_threshold: float = 0.0, max_results: int = 10) -> None:
        """Debug a transaction description and show matching analysis."""
        print("=" * 80)
        print("TRANSACTION MATCHING DEBUG")
        print("=" * 80)
        print(f"Input Description: {description}")
        print(f"Rules File: {self.rules_file_path}")
        print(f"Total Rules: {len(self.rules)}")
        print()
        
        # Show processing steps
        print("Processing Steps:")
        print("-" * 40)
        merchant = self.extract_merchant_name(description)
        cleaned = self.clean_description(description)
        
        print(f"1. Original Description: '{description}'")
        print(f"2. Extracted Merchant:   '{merchant}'")
        print(f"3. Cleaned Description:  '{cleaned}'")
        print()
        
        # Find matches
        matches = self.find_matches(description, show_all, confidence_threshold)
        
        if not matches:
            print("❌ No matching rules found!")
            print()
            print("Suggestions:")
            print("- Try lowering the confidence threshold with --threshold")
            print("- Use --show-all to see all rules (including non-matches)")
            print("- Check if the merchant name extraction is working correctly")
            return
        
        # Show matching rules
        print(f"Matching Rules (showing top {min(max_results, len(matches))}):")
        print("-" * 60)
        
        table_data = []
        for i, match in enumerate(matches[:max_results]):
            rule = match['rule']
            status = "✅ MATCH" if match['matched'] else "❌ NO MATCH"
            
            # Truncate long category names for display
            category = rule['category']
            if len(category) > 40:
                category = category[:37] + "..."
            
            table_data.append([
                i + 1,
                status,
                f"{match['confidence']:.1%}",
                rule['type'],
                rule['pattern'][:30] + ("..." if len(rule['pattern']) > 30 else ""),
                category
            ])
        
        headers = ["#", "Status", "Confidence", "Rule Type", "Pattern", "Category"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        print()
        
        # Show best match details
        if matches and matches[0]['matched']:
            best_match = matches[0]
            print("🎯 BEST MATCH DETAILS:")
            print("-" * 30)
            rule = best_match['rule']
            print(f"Category: {rule['category']}")
            print(f"Rule Type: {rule['type']}")
            print(f"Pattern: {rule['pattern']}")
            print(f"Confidence: {best_match['confidence']:.1%}")
            print(f"Transaction Count: {rule.get('transaction_count', 'Unknown')}")
            print(f"Explanation: {best_match['explanation']}")
            
            if 'example_descriptions' in rule:
                print(f"Example Descriptions:")
                for desc in rule['example_descriptions'][:3]:
                    print(f"  - {desc}")
        
        # Show detailed explanations for top matches
        if show_all and matches:
            print()
            print("DETAILED EXPLANATIONS:")
            print("-" * 40)
            for i, match in enumerate(matches[:5]):  # Show top 5 explanations
                rule = match['rule']
                status = "✅" if match['matched'] else "❌"
                print(f"{i+1}. {status} {rule['type']} | {match['confidence']:.1%} | {match['explanation']}")


def main():
    parser = argparse.ArgumentParser(
        description="Debug transaction description matching against categorization rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test a simple transaction
  python match_transaction.py "STARBUCKS 12345 SAN DIEGO CA"
  
  # Show all rules (including non-matches)
  python match_transaction.py "Netflix.com" --show-all
  
  # Use custom rules file and lower threshold
  python match_transaction.py "UBER TRIP" --rules my_rules.json --threshold 0.1
  
  # Limit results and show explanations
  python match_transaction.py "PAYPAL *SPOTIFY" --max-results 5 --show-all
        """
    )
    
    parser.add_argument('description', help='Transaction description to test')
    parser.add_argument('--rules', '-r', default='categorization_rules.json',
                       help='Path to categorization rules JSON file (default: categorization_rules.json)')
    parser.add_argument('--show-all', '-a', action='store_true',
                       help='Show all rules, including non-matches')
    parser.add_argument('--threshold', '-t', type=float, default=0.0,
                       help='Minimum confidence threshold to show (default: 0.0)')
    parser.add_argument('--max-results', '-m', type=int, default=10,
                       help='Maximum number of results to show (default: 10)')
    
    args = parser.parse_args()
    
    # Initialize matcher
    matcher = TransactionMatcher(args.rules)
    
    # Load rules
    if not matcher.load_rules():
        sys.exit(1)
    
    # Debug the transaction
    matcher.debug_transaction(
        args.description, 
        args.show_all, 
        args.threshold, 
        args.max_results
    )


if __name__ == "__main__":
    main()
