#!/usr/bin/env python3
"""
Common GNUCash utilities and session management.
Shared module for all GNUCash Python scripts.
"""

import sys
from pathlib import Path
from typing import Optional

try:
    import gnucash
    from gnucash import gnucash_core_c
except ImportError:
    print("Error: GNUCash Python bindings not found.")
    print("Make sure to run scripts with: ./gpython3 <script>")
    sys.exit(1)


class GnuCashSession:
    """Context manager for GNUCash sessions with proper logging and cleanup."""
    
    def __init__(self, book_path: str, log_conf: Optional[str] = None, read_only: bool = True):
        """
        Initialize GNUCash session manager.
        
        Args:
            book_path: Path to the GNUCash book file
            log_conf: Path to logging configuration file (optional)
            read_only: Whether to open in read-only mode (default: True)
        """
        self.book_path = book_path
        self.session = None
        self.book = None
        self.log_conf = log_conf
        self.read_only = read_only
    
    def __enter__(self):
        """Enter the session context - opens the book and initializes logging."""
        try:
            # Initialize logging first if config provided
            if self.log_conf:
                gnucash_core_c.qof_log_init()
                gnucash_core_c.qof_log_parse_log_config(self.log_conf)
                print(f"GNUCash logging initialized from: {self.log_conf}")
            
            # Open session in appropriate mode
            mode = (gnucash.SessionOpenMode.SESSION_READ_ONLY if self.read_only 
                   else gnucash.SessionOpenMode.SESSION_NORMAL)
            
            self.session = gnucash.Session(self.book_path, mode=mode)
            self.book = self.session.book
            
            mode_str = "read-only" if self.read_only else "read-write"
            print(f"Successfully loaded GNUCash book ({mode_str}): {self.book_path}")
            
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
        """Exit the session context - properly closes and destroys the session."""
        if self.session:
            try:
                self.session.end()
                self.session.destroy()
                print("GNUCash session closed and destroyed successfully")
            except Exception as e:
                print(f"Warning: Error closing GNUCash session: {e}")


def get_account_type_name(account_type):
    """Convert account type enum to readable name (compatible with all GNUCash versions)."""
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


def find_account_by_path(book, account_path: str):
    """
    Find account by its hierarchical path (e.g., 'Liabilities: Credit Cards: Chase').
    
    Args:
        book: GNUCash book object
        account_path: Colon-separated account path
        
    Returns:
        Account object if found, None otherwise
    """
    root_account = book.get_root_account()
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


def get_credit_card_accounts(book, specified_accounts=None):
    """
    Get credit card accounts from the book.
    
    Args:
        book: GNUCash book object
        specified_accounts: List of account paths to filter by (optional)
        
    Returns:
        List of credit card account objects
    """
    if specified_accounts:
        # Use specified accounts from config
        cc_accounts = []
        print(f"Using {len(specified_accounts)} accounts from configuration:")
        
        for account_path in specified_accounts:
            account = find_account_by_path(book, account_path)
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
        root_account = book.get_root_account()
        
        def find_cc_accounts(account):
            if account.GetType() == gnucash.ACCT_TYPE_CREDIT:
                cc_accounts.append(account)
            for child in account.get_children():
                find_cc_accounts(child)
        
        find_cc_accounts(root_account)
        return cc_accounts


def create_default_log_config(filename: str = "log.conf"):
    """
    Create a default GNUCash logging configuration file.
    
    Args:
        filename: Name of the log configuration file to create
    """
    config_content = """# GNUCash Logging Configuration
# Based on: https://wiki.gnucash.org/wiki/Logging
# Log Levels: CRIT, ERR, WARN, INFO, DEBUG

# Session and backend logging (most useful for Python bindings)
gnc.session=INFO
gnc.backend=INFO
gnc.backend.dbi=WARN
gnc.backend.sql=WARN

# Python binding specific logging  
python=INFO
swig=WARN

# Core engine logging
gnc.engine=WARN
gnc.account=WARN
gnc.transaction=WARN
gnc.split=WARN

# GUI logging (usually not needed for Python scripts)
gnc.gui=WARN
gnc.import=WARN

# QOF (Query Object Framework) logging
qof=WARN
qof.session=INFO

# Default log level for unlisted modules
*=WARN
"""
    
    with open(filename, 'w') as f:
        f.write(config_content)
    
    print(f"Default logging configuration created: {filename}")
    return filename


# Convenience function for setting up logging
def setup_logging(log_level: str = "INFO", create_config: bool = True):
    """
    Set up GNUCash logging with reasonable defaults.
    
    Args:
        log_level: Default log level (DEBUG, INFO, WARN, ERR, CRIT)
        create_config: Whether to create a default config if none exists
        
    Returns:
        Path to the log configuration file
    """
    log_conf_path = Path("log.conf")
    
    if create_config and not log_conf_path.exists():
        create_default_log_config(str(log_conf_path))
    
    if log_conf_path.exists():
        return str(log_conf_path)
    else:
        print(f"Warning: No log configuration file found at {log_conf_path}")
        return None
