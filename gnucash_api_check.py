#!/usr/bin/env python3
"""
GNUCash API Compatibility Checker
Helps identify available attributes and methods in your GNUCash Python bindings.
"""

import sys

def check_gnucash_api():
    """Check and display available GNUCash API elements."""
    
    try:
        import gnucash
        print("✓ GNUCash Python bindings imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import GNUCash bindings: {e}")
        print("Make sure to run this script with: ./gpython3 gnucash_api_check.py")
        return False
    
    print("\n" + "="*60)
    print("GNUCASH API COMPATIBILITY CHECK")
    print("="*60)
    
    # Check account types
    print("\n1. ACCOUNT TYPES:")
    print("   Available account type constants:")
    account_types = [x for x in dir(gnucash) if x.startswith('ACCT_TYPE_')]
    for acct_type in sorted(account_types):
        print(f"     - {acct_type}")
    
    # Check session modes  
    print("\n2. SESSION MODES:")
    session_modes = []
    
    # Look for top-level SESSION_ constants
    top_level_modes = [x for x in dir(gnucash) if 'SESSION_' in x]
    session_modes.extend([f"gnucash.{x}" for x in top_level_modes])
    
    # Look inside SessionOpenMode class if it exists
    if hasattr(gnucash, 'SessionOpenMode'):
        session_open_modes = [x for x in dir(gnucash.SessionOpenMode) if 'SESSION_' in x or not x.startswith('_')]
        session_modes.extend([f"gnucash.SessionOpenMode.{x}" for x in session_open_modes if not x.startswith('_')])
    
    if session_modes:
        print("   Available session mode constants:")
        for mode in sorted(session_modes):
            print(f"     - {mode}")
    else:
        print("   No SessionOpenMode constants found")
    
    # Check other common attributes
    print("\n3. OTHER COMMON ATTRIBUTES:")
    common_attrs = ['Session', 'Book', 'Account', 'Transaction', 'Split']
    for attr in common_attrs:
        if hasattr(gnucash, attr):
            print(f"     ✓ gnucash.{attr} - available")
        else:
            print(f"     ✗ gnucash.{attr} - not available")
    
    # Check version info
    print("\n4. VERSION INFORMATION:")
    version_attrs = [x for x in dir(gnucash) if 'version' in x.lower() or 'VERSION' in x]
    if version_attrs:
        for attr in version_attrs:
            try:
                value = getattr(gnucash, attr)
                print(f"     {attr}: {value}")
            except:
                print(f"     {attr}: <cannot access>")
    else:
        print("     No version information available")
    
    print("\n" + "="*60)
    print("RECOMMENDATIONS FOR COMPATIBILITY:")
    print("="*60)
    print("1. Always check if attributes exist before using them:")
    print("   if hasattr(gnucash, 'ACCT_TYPE_SAVINGS'):")
    print("       # Use the attribute")
    print()
    print("2. Use fallback patterns for missing constants:")
    print("   account_type_names = {}")
    print("   for attr_name in dir(gnucash):")
    print("       if attr_name.startswith('ACCT_TYPE_'):")
    print("           account_type_names[getattr(gnucash, attr_name)] = attr_name")
    print()
    print("3. Create compatibility layers:")
    print("   # Define missing constants if needed")
    print("   if not hasattr(gnucash, 'ACCT_TYPE_SAVINGS'):")
    print("       gnucash.ACCT_TYPE_SAVINGS = gnucash.ACCT_TYPE_BANK  # fallback")
    
    return True

def create_dynamic_account_type_mapping():
    """Create a dynamic mapping of account types available in this GNUCash installation."""
    
    try:
        import gnucash
    except ImportError:
        print("Cannot create mapping - GNUCash bindings not available")
        return None
    
    print("\n" + "="*60)
    print("DYNAMIC ACCOUNT TYPE MAPPING")
    print("="*60)
    print("Copy this code into your scripts for compatibility:")
    print()
    print("def get_account_type_name(account_type):")
    print('    """Convert account type enum to readable name (auto-generated)."""')
    print("    type_names = {")
    
    # Generate mapping dynamically
    account_types = [x for x in dir(gnucash) if x.startswith('ACCT_TYPE_')]
    for acct_type in sorted(account_types):
        attr_value = getattr(gnucash, acct_type)
        # Create readable name from constant name
        readable_name = acct_type.replace('ACCT_TYPE_', '').replace('_', ' ').title()
        print(f"        gnucash.{acct_type}: \"{readable_name}\",")
    
    print("    }")
    print("    return type_names.get(account_type, f\"Unknown({account_type})\")")
    
    return True

def main():
    print("GNUCash Python Bindings API Compatibility Checker")
    print("This tool helps identify what's available in your installation")
    
    if check_gnucash_api():
        create_dynamic_account_type_mapping()
        
        print(f"\n{'='*60}")
        print("DOCUMENTATION RESOURCES:")
        print("="*60)
        print("1. Official GNUCash Python docs:")
        print("   https://wiki.gnucash.org/wiki/Python_Bindings")
        print()
        print("2. GNUCash source code (for API reference):")
        print("   https://github.com/Gnucash/gnucash/tree/maint/bindings/python")
        print()
        print("3. Test your installation interactively:")
        print("   ./gpython3")
        print("   >>> import gnucash")
        print("   >>> help(gnucash)  # See available methods")
        print("   >>> dir(gnucash)   # See all attributes")
        print()
        print("4. Always test compatibility:")
        print("   ./gpython3 gnucash_api_check.py")

if __name__ == "__main__":
    main()
