#!/usr/bin/env python3
"""
GNUCash Transaction Analyzer - Step 1
Analyzes credit card transactions and generates categorization rules.
"""

import sys
import json
import re
import argparse
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

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


class GnuCashSession:
    """Context manager for GNUCash sessions to ensure proper cleanup."""
    
    def __init__(self, book_path):
        self.book_path = book_path
        self.session = None
        self.book = None
    
    def __enter__(self):
        try:
            self.session = gnucash.Session(self.book_path, mode=gnucash.SessionOpenMode.SESSION_READ_ONLY)
            self.book = self.session.book
            print(f"Successfully loaded GNUCash book: {self.book_path}")
            return self.book
        except Exception as e:
            print(f"Error loading GNUCash book: {e}")
            if self.session:
                try:
                    self.session.end()
                except:
                    pass
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            try:
                self.session.end()
                self.session.destroy()
                print("GNUCash session closed and destroyed successfully")
            except Exception as e:
                print(f"Warning: Error closing GNUCash session: {e}")


class TransactionAnalyzer:
    """Analyzes GNUCash transactions to generate categorization rules."""
    
    def __init__(self, book_path, config=None):
        self.book_path = book_path
        self.book = None
        self.transactions = []
        self.rules = []
        self.config = config or {}
        
    def load_config(self, config_path):
        """Load YAML configuration file."""
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            print(f"Configuration loaded from: {config_path}")
        except Exception as e:
            print(f"Error loading configuration: {e}")
            sys.exit(1)
    
    def get_account_by_path(self, account_path):
        """Find account by its hierarchical path (e.g., 'Liabilities: Credit Cards: Chase')."""
        root_account = self.book.get_root_account()
        path_parts = [part.strip() for part in account_path.split(':')]
        
        def find_account_recursive(account, remaining_path):
            if not remaining_path:
                return account
            
            target_name = remaining_path[0]
            for child in account.get_children():
                if child.GetName() == target_name:
                    return find_account_recursive(child, remaining_path[1:])
            return None
        
        # Skip "Root Account" if it's the first part
        if path_parts and path_parts[0] == "Root Account":
            path_parts = path_parts[1:]
        
        return find_account_recursive(root_account, path_parts)
    
    def get_credit_card_accounts(self):
        """Find credit card accounts based on configuration or all if no config."""
        if self.config and 'credit_card_accounts' in self.config:
            # Use specified accounts from config
            specified_accounts = self.config['credit_card_accounts']
            cc_accounts = []
            
            print(f"Using {len(specified_accounts)} accounts from configuration:")
            
            for account_path in specified_accounts:
                account = self.get_account_by_path(account_path)
                if account:
                    if account.GetType() == gnucash.ACCT_TYPE_CREDIT:
                        cc_accounts.append(account)
                        print(f"  ✓ Found: {account_path}")
                    else:
                        print(f"  ✗ Warning: {account_path} is not a credit card account")
                else:
                    print(f"  ✗ Error: Account not found: {account_path}")
            
            return cc_accounts
        else:
            # Default behavior: find all credit card accounts
            cc_accounts = []
            root_account = self.book.get_root_account()
            
            def find_cc_accounts(account):
                if account.GetType() == gnucash.ACCT_TYPE_CREDIT:
                    cc_accounts.append(account)
                for child in account.get_children():
                    find_cc_accounts(child)
            
            find_cc_accounts(root_account)
            return cc_accounts
    
    def extract_transactions(self):
        """Extract all transactions from credit card accounts."""
        cc_accounts = self.get_credit_card_accounts()
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
                if any(t['guid'] == transaction.GetGUID().to_string() for t in transactions):
                    continue
                
                # Apply date filtering if configured
                transaction_date = transaction.GetDate().date()
                if start_date and transaction_date < start_date:
                    continue
                if end_date and transaction_date > end_date:
                    continue
                
                # Find the opposing split (the expense/income account)
                opposing_split = None
                for s in transaction.GetSplitList():
                    if s.GetAccount() != account:
                        opposing_split = s
                        break
                
                if opposing_split:
                    transaction_data = {
                        'guid': transaction.GetGUID().to_string(),
                        'date': transaction_date.strftime('%Y-%m-%d'),
                        'description': transaction.GetDescription(),
                        'amount': float(split.GetValue()),
                        'credit_card_account': account_name,
                        'credit_card_account_path': account_path,
                        'category_account': opposing_split.GetAccount().GetName(),
                        'category_full_path': opposing_split.GetAccount().get_full_name(),
                        'memo': split.GetMemo() or '',
                    }
                    transactions.append(transaction_data)
        
        self.transactions = transactions
        print(f"Extracted {len(transactions)} transactions")
        return transactions
    
    def extract_merchant_name(self, description):
        """Extract and normalize merchant name from transaction description."""
        # Common patterns in transaction descriptions
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

    def clean_description(self, description):
        """Clean and normalize transaction descriptions for pattern matching."""
        # Convert to lowercase
        cleaned = description.lower()
        
        # Remove common transaction artifacts
        cleaned = re.sub(r'\d{2}/\d{2}(/\d{2,4})?', '', cleaned)  # Remove dates
        cleaned = re.sub(r'#\d+', '', cleaned)                    # Remove reference numbers
        cleaned = re.sub(r'\*+', '', cleaned)                     # Remove asterisks  
        cleaned = re.sub(r'\d{4,}', '', cleaned)                  # Remove long numbers (auth codes, etc.)
        cleaned = re.sub(r'\s+', ' ', cleaned)                    # Normalize whitespace
        cleaned = cleaned.strip()
        
        return cleaned
    
    def similarity_ratio(self, a, b):
        """Calculate similarity ratio between two strings."""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def group_similar_merchants(self, merchants, threshold=0.8):
        """Group similar merchant names using fuzzy matching."""
        groups = []
        used = set()
        
        merchant_list = list(merchants.keys())
        
        for i, merchant1 in enumerate(merchant_list):
            if i in used:
                continue
                
            group = [(merchant1, merchants[merchant1])]
            used.add(i)
            
            for j, merchant2 in enumerate(merchant_list[i+1:], i+1):
                if j not in used:
                    similarity = self.similarity_ratio(merchant1, merchant2)
                    if similarity >= threshold:
                        group.append((merchant2, merchants[merchant2]))
                        used.add(j)
            
            if len(group) > 1:  # Only return groups with multiple merchants
                groups.append(group)
        
        return groups
    
    def generate_rules(self):
        """Generate enhanced categorization rules using multiple techniques."""
        # Get rule settings from config
        rule_settings = self.config.get('rule_settings', {})
        min_transactions = rule_settings.get('minimum_transactions', 2)
        confidence_threshold = rule_settings.get('confidence_threshold', 0.3)
        fuzzy_similarity = rule_settings.get('fuzzy_similarity', 0.8)
        
        print(f"Rule generation settings:")
        print(f"  Minimum transactions: {min_transactions}")
        print(f"  Confidence threshold: {confidence_threshold}")
        print(f"  Fuzzy similarity: {fuzzy_similarity}")
        
        # Group transactions by category
        category_transactions = defaultdict(list)
        
        for txn in self.transactions:
            category = txn['category_full_path']
            category_transactions[category].append(txn)
        
        rules = []
        
        for category, txns in category_transactions.items():
            if len(txns) < min_transactions:  # Skip categories with too few transactions
                continue
            
            # Method 1: Merchant-based rules (enhanced)
            merchant_counts = Counter()
            merchant_examples = defaultdict(list)
            
            for txn in txns:
                merchant = self.extract_merchant_name(txn['description'])
                if merchant and len(merchant) > 2:
                    merchant_counts[merchant] += 1
                    merchant_examples[merchant].append(txn['description'])
            
            # Generate merchant rules
            for merchant, count in merchant_counts.items():
                if count >= 2:  # At least 2 transactions
                    confidence = count / len(txns)
                    
                    rule = {
                        'type': 'merchant_name',
                        'pattern': merchant,
                        'category': category,
                        'confidence': confidence,
                        'transaction_count': count,
                        'total_transactions': len(txns),
                        'example_descriptions': merchant_examples[merchant][:3]
                    }
                    rules.append(rule)
            
            # Method 2: Fuzzy merchant grouping
            if len(merchant_counts) > 1:
                similar_groups = self.group_similar_merchants(merchant_counts, threshold=fuzzy_similarity)
                
                for group in similar_groups:
                    total_count = sum(count for _, count in group)
                    if total_count >= 2:
                        # Use the most frequent merchant as the canonical name
                        canonical_merchant = max(group, key=lambda x: x[1])[0]
                        confidence = total_count / len(txns)
                        
                        rule = {
                            'type': 'fuzzy_merchant',
                            'pattern': canonical_merchant,
                            'variants': [merchant for merchant, _ in group],
                            'category': category,
                            'confidence': confidence,
                            'transaction_count': total_count,
                            'total_transactions': len(txns),
                            'example_descriptions': merchant_examples[canonical_merchant][:2]
                        }
                        rules.append(rule)
            
            # Method 3: Enhanced word analysis (skip common words)
            descriptions = [self.clean_description(txn['description']) for txn in txns]
            
            # Common words to ignore
            skip_words = {'payment', 'purchase', 'debit', 'credit', 'card', 'auto', 'recurring', 
                         'online', 'mobile', 'pos', 'terminal', 'transaction', 'transfer'}
            
            word_counts = Counter()
            for desc in descriptions:
                words = desc.split()
                for word in words:
                    if len(word) > 3 and word not in skip_words:  # Skip very short words and common terms
                        word_counts[word] += 1
            
            # Generate word-based rules with higher threshold
            for word, count in word_counts.most_common(3):  # Top 3 words only
                if count >= max(2, len(txns) * 0.4):  # Higher threshold: 40%
                    confidence = count / len(txns)
                    
                    rule = {
                        'type': 'description_contains',
                        'pattern': word,
                        'category': category,
                        'confidence': confidence,
                        'transaction_count': count,
                        'total_transactions': len(txns),
                        'example_descriptions': [txn['description'] for txn in txns if word in self.clean_description(txn['description'])][:3]
                    }
                    rules.append(rule)
            
            # Method 4: Exact description patterns (with better threshold)
            exact_matches = Counter(descriptions)
            for desc, count in exact_matches.items():
                if count >= 3 and len(desc) > 5:  # At least 3 times and meaningful length
                    confidence = count / len(txns)
                    
                    rule = {
                        'type': 'description_exact',
                        'pattern': desc,
                        'category': category,
                        'confidence': confidence,
                        'transaction_count': count,
                        'total_transactions': len(txns),
                        'example_descriptions': [txn['description'] for txn in txns if self.clean_description(txn['description']) == desc][:3]
                    }
                    rules.append(rule)
        
        # Sort rules by confidence, then by transaction count
        rules.sort(key=lambda x: (x['confidence'], x['transaction_count']), reverse=True)
        
        self.rules = rules
        return rules
    
    def save_rules(self, filename='categorization_rules.json'):
        """Save the generated rules to a JSON file."""
        output_data = {
            'generated_at': datetime.now().isoformat(),
            'book_path': self.book_path,
            'total_transactions': len(self.transactions),
            'total_rules': len(self.rules),
            'rules': self.rules
        }
        
        with open(filename, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        print(f"Rules saved to {filename}")
    
    def print_summary(self):
        """Print a summary of the analysis."""
        print("\n" + "="*60)
        print("TRANSACTION ANALYSIS SUMMARY")
        print("="*60)
        print(f"Total transactions analyzed: {len(self.transactions)}")
        print(f"Total rules generated: {len(self.rules)}")
        
        # Show top categories
        category_counts = Counter(txn['category_full_path'] for txn in self.transactions)
        print(f"\nTop 10 transaction categories:")
        for category, count in category_counts.most_common(10):
            print(f"  {category}: {count} transactions")
        
        # Show top rules
        print(f"\nTop 10 categorization rules:")
        for i, rule in enumerate(self.rules[:10], 1):
            print(f"  {i}. '{rule['pattern']}' → {rule['category']}")
            print(f"     Confidence: {rule['confidence']:.2%} ({rule['transaction_count']}/{rule['total_transactions']} transactions)")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze GNUCash credit card transactions and generate categorization rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all credit card accounts
  ./gpython3 analyze_transactions.py ~/gnc/accounts.gnucash
  
  # Use configuration file to specify which accounts to analyze
  ./gpython3 analyze_transactions.py ~/gnc/accounts.gnucash --config analyze_config.yaml
  
  # Generate a sample configuration file first
  ./gpython3 list_accounts.py ~/gnc/accounts.gnucash --generate-config
        """
    )
    
    parser.add_argument('book_path', help='Path to GNUCash file')
    parser.add_argument('--config', '-c', help='Path to YAML configuration file')
    parser.add_argument('--output', '-o', default='categorization_rules.json', 
                       help='Output file for rules (default: categorization_rules.json)')
    
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
        
        # Print summary
        analyzer.print_summary()
    
    print(f"\nAnalysis complete! Rules have been saved to '{args.output}'")
    print("You can now proceed to Step #2 - importing OFX transactions.")
    
    if not args.config:
        print(f"\nTip: To analyze specific accounts only, run:")
        print(f"  ./gpython3 list_accounts.py {args.book_path} --generate-config")
        print(f"  # Edit the generated analyze_config.yaml file")
        print(f"  ./gpython3 analyze_transactions.py {args.book_path} --config analyze_config.yaml")
        
if __name__ == "__main__":
    main()
