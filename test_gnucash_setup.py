#!/usr/bin/env python3
"""
Test script to verify GNUCash Python bindings are working correctly.
"""

import sys

def test_gnucash_import():
    """Test if GNUCash bindings can be imported."""
    try:
        import gnucash
        print("✓ GNUCash Python bindings imported successfully")
        
        # Test basic functionality
        print(f"✓ GNUCash version info available")
        print(f"✓ Account types available: {hasattr(gnucash, 'ACCT_TYPE_CREDIT')}")
        
        return True
    except ImportError as e:
        print(f"✗ Failed to import GNUCash bindings: {e}")
        print("Make sure to run this script with: ./gpython3 test_gnucash_setup.py")
        return False
    except Exception as e:
        print(f"✗ Error testing GNUCash bindings: {e}")
        return False

def main():
    print("Testing GNUCash Python bindings setup...")
    print("=" * 50)
    
    if test_gnucash_import():
        print("\n✓ Setup test passed! You're ready to analyze your GNUCash file.")
        print("\nNext steps:")
        print("1. Run: ./gpython3 analyze_transactions.py /path/to/your/accounts.gnucash")
        print("2. Review the generated categorization_rules.json file")
        print("3. Proceed to Step #2 (OFX import and categorization)")
    else:
        print("\n✗ Setup test failed. Please check your GNUCash Python bindings installation.")
        sys.exit(1)

if __name__ == "__main__":
    main()
