#!/usr/bin/env python3
"""
Rules database management with YAML serialization.
Handles loading and saving categorization rules from/to YAML files.
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from core_models import CategorizationRule, RuleSource


def save_history_rules(
    rules: list[CategorizationRule],
    filepath: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Save history-based rules to a YAML file.

    Args:
        rules: List of categorization rules to save
        filepath: Path to output YAML file
        metadata: Optional metadata about rule generation (config, stats, etc.)
    """
    # Prepare YAML structure
    yaml_data = {
        'version': '1.0',
        'description': 'Rules generated from historical GNUCash data',
        'generated_at': datetime.now().isoformat(),
    }

    # Add metadata if provided
    if metadata:
        yaml_data['metadata'] = metadata

    # Convert rules to dictionaries
    yaml_data['rules'] = [rule.to_dict() for rule in rules]

    # Write to file with nice formatting
    with open(filepath, 'w') as f:
        yaml.dump(
            yaml_data,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            indent=2
        )

    print(f"Saved {len(rules)} rules to: {filepath}")


def load_history_rules(filepath: str) -> list[CategorizationRule]:
    """
    Load history-based rules from a YAML file.

    Args:
        filepath: Path to YAML file containing rules

    Returns:
        List of CategorizationRule objects
    """
    if not Path(filepath).exists():
        raise FileNotFoundError(f"Rules file not found: {filepath}")

    with open(filepath, 'r') as f:
        yaml_data = yaml.safe_load(f)

    # Validate version
    version = yaml_data.get('version', '1.0')
    if version != '1.0':
        print(f"Warning: Rules file version {version} may not be compatible")

    # Load rules
    rules = []
    for rule_data in yaml_data.get('rules', []):
        rule = CategorizationRule.from_dict(rule_data, RuleSource.HISTORY_BASED)
        rules.append(rule)

    print(f"Loaded {len(rules)} rules from: {filepath}")
    return rules


def load_manual_rules(filepath: str) -> list[CategorizationRule]:
    """
    Load manually-specified rules from a YAML file.

    Args:
        filepath: Path to YAML file containing manual rules

    Returns:
        List of CategorizationRule objects
    """
    if not Path(filepath).exists():
        print(f"Manual rules file not found: {filepath}")
        return []

    with open(filepath, 'r') as f:
        yaml_data = yaml.safe_load(f)

    rules = []
    for rule_data in yaml_data.get('rules', []):
        rule = CategorizationRule.from_dict(rule_data, RuleSource.MANUAL)
        rules.append(rule)

    print(f"Loaded {len(rules)} manual rules from: {filepath}")
    return rules


def load_ai_rules(filepath: str) -> list[CategorizationRule]:
    """
    Load AI-generated rules from a YAML file.

    Args:
        filepath: Path to YAML file containing AI-generated rules

    Returns:
        List of CategorizationRule objects
    """
    if not Path(filepath).exists():
        print(f"AI rules file not found: {filepath}")
        return []

    with open(filepath, 'r') as f:
        yaml_data = yaml.safe_load(f)

    rules = []
    for rule_data in yaml_data.get('rules', []):
        rule = CategorizationRule.from_dict(rule_data, RuleSource.AI_GENERATED)
        rules.append(rule)

    print(f"Loaded {len(rules)} AI-generated rules from: {filepath}")
    return rules


def create_sample_manual_rules_file(filepath: str = "manual_rules.yaml") -> None:
    """
    Create a sample manual rules file with examples.

    Args:
        filepath: Path where the sample file should be created
    """
    sample_data = {
        'version': '1.0',
        'description': 'Manually specified rules (highest priority)',
        'rules': [
            {
                'rule_type': 'exact_match',
                'pattern': 'internet payment thank you',
                'category': 'Unspecified',
                'transaction_type': 'credit',
                'description': 'Credit card bill payments',
                'confidence': 1.0,
            },
            {
                'rule_type': 'contains',
                'pattern': 'netflix',
                'category': 'Expenses:Bills:Streaming Services',
                'merchant_name': 'Netflix',
                'confidence': 0.95,
            },
        ]
    }

    with open(filepath, 'w') as f:
        yaml.dump(sample_data, f, default_flow_style=False, sort_keys=False, indent=2)

    print(f"Sample manual rules file created: {filepath}")
