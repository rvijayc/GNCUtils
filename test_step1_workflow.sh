#!/bin/bash
# Test Script for Step #1: Extract Unique Descriptions Workflow
# This demonstrates the refactored analyze_transactions.py

echo "==============================================="
echo "Step #1 Workflow Test: Extract Unique Descriptions"
echo "==============================================="
echo ""

# Activate conda environment
source /home/vijayr/miniconda3/etc/profile.d/conda.sh
conda activate gnc

# Set variables
GNUCASH_FILE="/home/vijayr/gnc/vijayr.gnucash"
CONFIG_FILE="analyze_config.yaml"
OUTPUT_RULES="test_history_rules.yaml"
OUTPUT_DESCRIPTIONS="test_unique_descriptions.txt"

echo "1. Running analyze_transactions.py with shared normalizer..."
echo "   - GNUCash file: $GNUCASH_FILE"
echo "   - Config: $CONFIG_FILE"
echo "   - Output rules: $OUTPUT_RULES"
echo "   - Output descriptions: $OUTPUT_DESCRIPTIONS"
echo ""

./gpython3 analyze_transactions.py "$GNUCASH_FILE" \
    --config "$CONFIG_FILE" \
    --output "$OUTPUT_RULES" \
    --unique-descriptions "$OUTPUT_DESCRIPTIONS"

echo ""
echo "==============================================="
echo "Step #1 Complete!"
echo "==============================================="
echo ""
echo "Generated files:"
echo "  1. $OUTPUT_RULES - History-based rules"
echo "  2. $OUTPUT_DESCRIPTIONS - Unique uncovered descriptions for LLM"
echo ""
echo "Next steps:"
echo "  - Review $OUTPUT_DESCRIPTIONS"
echo "  - Run LLM categorizer on selected descriptions"
echo ""
echo "Sample of unique descriptions:"
head -20 "$OUTPUT_DESCRIPTIONS"
echo ""
echo "Total unique uncovered descriptions:"
wc -l "$OUTPUT_DESCRIPTIONS"
