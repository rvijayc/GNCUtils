#!/bin/bash
# debug_gnucash.sh - Run GNUCash Python scripts with debug logging
#
# Usage:
#   ./debug_gnucash.sh [level] [domains] <command>
#
# Examples:
#   ./debug_gnucash.sh 4 "gnc.session,python" ./gpython3 list_accounts.py ~/gnc/vijayr.gnucash
#   ./debug_gnucash.sh 5 "*" ./gpython3 analyze_transactions.py ~/gnc/vijayr.gnucash
#   ./debug_gnucash.sh  # Use defaults: level 4, common domains

# Set debug level (1-5, 5 is most verbose)
DEBUG_LEVEL=${1:-4}

# Set domains to debug (default: all important ones)
DEBUG_DOMAINS=${2:-"gnc.engine,gnc.session,gnc.backend,python"}

# If no additional arguments provided, show usage
if [ $# -eq 0 ]; then
    echo "GNUCash Debug Logging Wrapper"
    echo "Usage: $0 [level] [domains] <command>"
    echo ""
    echo "Parameters:"
    echo "  level   : Log level 1-5 (default: 4)"
    echo "            1=ERROR, 2=WARN, 3=MESSAGE, 4=INFO, 5=DEBUG"
    echo "  domains : Comma-separated log domains (default: common domains)"
    echo "            Use '*' for all domains"
    echo "  command : Command to run with debug logging"
    echo ""
    echo "Examples:"
    echo "  $0 4 'gnc.session,python' ./gpython3 list_accounts.py ~/gnc/vijayr.gnucash"
    echo "  $0 5 '*' ./gpython3 analyze_transactions.py ~/gnc/vijayr.gnucash"
    echo ""
    echo "Common domains:"
    echo "  gnc.engine, gnc.session, gnc.backend, python, gnc.account,"
    echo "  gnc.transaction, gnc.split, gnc.backend.dbi, gnc.backend.sql"
    exit 1
fi

# If only level provided, shift once; if level and domains provided, shift twice
if [ $# -eq 1 ]; then
    shift 1
elif [ $# -ge 2 ] && [[ "$3" != "" ]]; then
    shift 2
else
    echo "Error: No command provided"
    exit 1
fi

echo "================================="
echo "GNUCash Debug Logging Session"
echo "================================="
echo "Debug Level: $DEBUG_LEVEL"
echo "Debug Domains: $DEBUG_DOMAINS"
echo "Command: $*"
echo "================================="
echo ""

# Set environment variables
export GNC_LOG_LEVEL=$DEBUG_LEVEL
export GNC_LOG_DOMAIN="$DEBUG_DOMAINS"

# Run the command
exec "$@"
