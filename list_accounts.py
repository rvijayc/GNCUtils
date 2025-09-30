#!/usr/bin/env python3
"""
GNUCash Account Lister
Lists all accounts in a GNUCash book in hierarchical format for easy copy-paste into config files.
"""

from typing import Optional
import sys
from pathlib import Path

try:
    import gnucash
    from gnucash import gnucash_core_c
except ImportError:
    print("Error: GNUCash Python bindings not found.")
    print("Make sure to run this script with: ./gpython3 list_accounts.py")
    sys.exit(1)

class GnuCashSession:
    """Context manager for GNUCash sessions to ensure proper cleanup."""
    
    def __init__(self, book_path, log_conf: Optional[str]=None):
        """

        Args:
            book_path: Path of the GNUCash book to load.
            log_conf: Path of the logging configuration file.
        """
        self.book_path = book_path
        self.session = None
        self.book = None
        self.log_conf = log_conf
    
    def __enter__(self):
        try:
            self.session = gnucash.Session( 
                            self.book_path,
                            mode=gnucash.SessionOpenMode.SESSION_READ_ONLY
            )
            if self.log_conf:
                gnucash_core_c.qof_log_init()
                gnucash_core_c.qof_log_parse_log_config(self.log_conf)
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


class AccountLister:
    """Lists all accounts in a GNUCash book."""
    
    def __init__(self, book_path):
        self.book_path = book_path
        self.book = None
        
    def get_account_type_name(self, account_type):
        """Convert account type enum to readable name."""
        type_names = {
            gnucash.ACCT_TYPE_ASSET: "Asset",
            gnucash.ACCT_TYPE_LIABILITY: "Liability", 
            gnucash.ACCT_TYPE_EQUITY: "Equity",
            gnucash.ACCT_TYPE_INCOME: "Income",
            gnucash.ACCT_TYPE_EXPENSE: "Expense",
            gnucash.ACCT_TYPE_BANK: "Bank",
            gnucash.ACCT_TYPE_CASH: "Cash",
            gnucash.ACCT_TYPE_CREDIT: "Credit",
            gnucash.ACCT_TYPE_STOCK: "Stock",
            gnucash.ACCT_TYPE_MUTUAL: "Mutual Fund",
            gnucash.ACCT_TYPE_CHECKING: "Checking",
            gnucash.ACCT_TYPE_RECEIVABLE: "Accounts Receivable",
            gnucash.ACCT_TYPE_PAYABLE: "Accounts Payable",
            gnucash.ACCT_TYPE_ROOT: "Root",
            gnucash.ACCT_TYPE_TRADING: "Trading",
        }
        return type_names.get(account_type, f"Unknown({account_type})")
    
    def list_all_accounts(self, show_types=True, credit_cards_only=False):
        """List all accounts in hierarchical format."""
        root_account = self.book.get_root_account()
        accounts = []
        
        def collect_accounts(account, path=""):
            account_name = account.GetName()
            account_type = account.GetType()
            
            # Skip the root account itself
            if account_name == "Root Account":
                current_path = ""
            else:
                current_path = f"{path}: {account_name}" if path else account_name
            
            # Only add non-root accounts
            if current_path:
                if credit_cards_only:
                    if account_type == gnucash.ACCT_TYPE_CREDIT:
                        accounts.append({
                            'path': current_path,
                            'type': self.get_account_type_name(account_type),
                            'full_name': account.get_full_name()
                        })
                else:
                    accounts.append({
                        'path': current_path,
                        'type': self.get_account_type_name(account_type),
                        'full_name': account.get_full_name()
                    })
            
            # Recursively process children
            for child in account.get_children():
                collect_accounts(child, current_path)
        
        collect_accounts(root_account)
        return accounts
    
    def print_accounts(self, show_types=True, credit_cards_only=False):
        """Print accounts in a formatted way."""
        accounts = self.list_all_accounts(show_types, credit_cards_only)
        
        if credit_cards_only:
            print(f"\n{'='*60}")
            print("CREDIT CARD ACCOUNTS ONLY")
            print(f"{'='*60}")
        else:
            print(f"\n{'='*60}")
            print("ALL ACCOUNTS")
            print(f"{'='*60}")
        
        print("Format: Account Path (Account Type)")
        print("Copy the account paths below for your YAML configuration:")
        print()
        
        for account in accounts:
            if show_types:
                print(f"  - \"{account['path']}\"  # {account['type']}")
            else:
                print(f"  - \"{account['path']}\"")
        
        print(f"\nTotal accounts listed: {len(accounts)}")
        
        if not credit_cards_only:
            # Show credit cards separately for convenience
            credit_cards = [acc for acc in accounts if "Credit" in acc['type']]
            if credit_cards:
                print(f"\n{'='*60}")
                print("CREDIT CARD ACCOUNTS FOR EASY COPY-PASTE")
                print(f"{'='*60}")
                print("# Add these to your analyze_config.yaml file:")
                print("credit_card_accounts:")
                for cc in credit_cards:
                    print(f"  - \"{cc['path']}\"")
    
    def generate_sample_config(self):
        """Generate a sample YAML configuration file."""
        accounts = self.list_all_accounts(credit_cards_only=True)
        
        config_content = f"""# GNUCash Transaction Analyzer Configuration
# Generated on {Path().resolve()}

# Specify which credit card accounts to analyze
# Use the exact account paths as shown by list_accounts.py
credit_card_accounts:
"""
        
        if accounts:
            config_content += "  # Uncomment and modify the accounts you want to analyze:\n"
            for account in accounts:
                config_content += f"  # - \"{account['path']}\"\n"
        else:
            config_content += """  # Example format:
  # - "Liabilities: Credit Cards: Chase Freedom"
  # - "Liabilities: Credit Cards: American Express"
  # - "Liabilities: Credit Cards: Discover"
"""
        
        config_content += """
# Optional: Specify date range for analysis
date_range:
  # start_date: "2023-01-01"  # YYYY-MM-DD format
  # end_date: "2024-12-31"    # YYYY-MM-DD format

# Optional: Rule generation settings
rule_settings:
  minimum_transactions: 2      # Minimum transactions needed to create a rule
  confidence_threshold: 0.3    # Minimum confidence score for rules
  fuzzy_similarity: 0.8       # Similarity threshold for fuzzy merchant matching
"""
        
        return config_content


def main():
    if len(sys.argv) < 2:
        print("Usage: ./gpython3 list_accounts.py <path_to_gnucash_file> [options]")
        print("Options:")
        print("  --credit-cards-only    Show only credit card accounts")
        print("  --generate-config      Generate sample YAML configuration file")
        print("  --no-types            Don't show account types")
        print()
        print("Examples:")
        print("  ./gpython3 list_accounts.py ~/gnc/vijayr.gnucash")
        print("  ./gpython3 list_accounts.py ~/gnc/vijayr.gnucash --credit-cards-only")
        print("  ./gpython3 list_accounts.py ~/gnc/vijayr.gnucash --generate-config")
        sys.exit(1)
    
    book_path = sys.argv[1]
    
    if not Path(book_path).exists():
        print(f"Error: GNUCash file not found: {book_path}")
        sys.exit(1)
    
    # Parse command line options
    credit_cards_only = "--credit-cards-only" in sys.argv
    generate_config = "--generate-config" in sys.argv
    show_types = "--no-types" not in sys.argv
    
    lister = AccountLister(book_path)
    
    try:
        with GnuCashSession(book_path) as book:
            lister.book = book
            
            if generate_config:
                config_content = lister.generate_sample_config()
                config_filename = "analyze_config.yaml"
                
                with open(config_filename, 'w') as f:
                    f.write(config_content)
                
                print(f"Sample configuration file generated: {config_filename}")
                print("\nEdit this file to specify which accounts to analyze, then run:")
                print("./gpython3 analyze_transactions.py ~/gnc/vijayr.gnucash --config analyze_config.yaml")
            else:
                lister.print_accounts(show_types, credit_cards_only)
                
                if not credit_cards_only:
                    print(f"\n{'='*60}")
                    print("NEXT STEPS:")
                    print("1. Copy the credit card account paths you want to analyze")
                    print("2. Run: ./gpython3 list_accounts.py ~/gnc/vijayr.gnucash --generate-config")
                    print("3. Edit the generated analyze_config.yaml file")
                    print("4. Run the analyzer with: ./gpython3 analyze_transactions.py ~/gnc/vijayr.gnucash --config analyze_config.yaml")
    
    except Exception as e:
        print(f"Error during account listing: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
