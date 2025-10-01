# GNUCash Automatic Transaction Categorization System
## Functional Specification

### Overview

Personal finance management tools like GNUCash are invaluable for tracking expenses and generating insights about spending, savings, and investments. However, one significant barrier to adoption is the time-consuming process of manually categorizing transactions, particularly expense transactions which constitute the majority of financial activity.

This document outlines the functional specification for an automated transaction categorization system that leverages rule-based algorithms, machine learning, and generative AI to streamline this process. The initial version focuses specifically on categorizing expense transactions from credit cards, which represent the largest volume of transactions requiring categorization.

The system is built upon GNUCash Python bindings, which provide programmatic access to read and update GNUCash databases.

## System Architecture: A Layered Approach

The system employs a multi-layered approach with three distinct phases: pre-processing, categorization, and integration. Each layer builds upon the previous one to provide increasingly sophisticated transaction analysis and categorization capabilities.

### Pre-Processing Layer

#### Transaction Import and Parsing

Credit card transactions are typically downloaded as OFX/QFX files containing structured data including `id`, `date`, `description`, `type`, `memo`, `amount`, and other fields. For categorization purposes, the most critical fields are:

- **`type`**: Specifies whether a transaction is a *debit* (spending transaction) or *credit* (refund of a past expense or payment from a bank account). Credit transactions typically require special handling compared to debit transactions, which can be automatically categorized.

- **`description` and `raw_description`**: Contain the merchant name and other transaction details essential for categorization. The raw description represents the original data from the OFX file, while the description field contains the processed version.

#### Description Normalization

One of the first tasks after parsing an OFX/QFX file is to clean up (normalize) the description to reduce the total number of unique descriptions that all refer to the same merchant or expense type. This normalization process includes:

- Converting to lowercase
- Removing extra spaces
- Removing numbers such as zip codes and phone numbers
- Removing unwanted hyphens
- Additional standardization steps

**Example of Normalization Results:**

The following table shows an example parsed OFX file where the `raw_description` column refers to the description as specified in the OFX file, while the `description` column refers to the *normalized* description that is more unique and easier to categorize:

```
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ date       ┃ description                      ┃ amount   ┃ type   ┃ `raw_description`                ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 2025-03-14 │ linkedinpre *                    │ -39.99   │ debit  │ LinkedInPre *092382392 855-65536 │
│ 2025-03-14 │ netflix.com netflix.c            │ -17.99   │ debit  │ Netflix.com            netflix.c │
│ 2025-03-14 │ ucsd sbo mychart san diego       │ -1623.32 │ debit  │ UCSD SBO MYCHART       SAN DIEGO │
│ 2025-03-17 │ internet payment thank you       │ 6999.57  │ credit │ INTERNET PAYMENT THANK YOU       │ => credit card bill payment
│ 2025-03-17 │ ucsd parking flex la jolla       │ -6.0     │ debit  │ UCSD PARKING FLEX      LA JOLLA  │
│ 2025-03-17 │ ucsd parking mobile eb www.parkm │ -4.5     │ debit  │ UCSD PARKING MOBILE EB www.parkm │
│ 2025-04-07 │ thai sport bodyworks             │ -89.0    │ debit  │ Thai Sport Bodyworks   161-95147 │ 
│ 2025-04-07 │ icp*studio arthaus               │ -195.0   │ debit  │ ICP*STUDIO ARTHAUS     858-33351 │ 
│ 2025-04-08 │ thai sport bodyworks             │ 89.0     │ credit │ Thai Sport Bodyworks   161-95147 │ => refund of a previous expense.
```

### Categorization Layer

Once descriptions are normalized, the next step is to categorize them using a comprehensive set of rules described in the following sections.

#### Rules Database Structure

The rules database specifies how to categorize transactions read from OFX files. It contains the following fields:

- **`rule_type`**: Specifies the type of matching algorithm:
  - `exact_match`: The description must match the specified pattern exactly
  - `contains`: The description must contain the specified pattern string
  - `regex`: The description must match the specified regular expression pattern

- **`transaction_type`** *(optional)*: Restricts the rule to either `credit` or `debit` transactions. If omitted, the rule applies to both types.

- **`pattern`**: A string whose usage is determined by the `rule_type` above.

- **`category`**: Specifies the GNUCash account category to be applied to matching transactions.

- **`merchant_name`** *(optional)*: If applicable, specifies the merchant or business name associated with the transaction.

- **`description`** *(optional)*: Any description or comment associated with the rule.

The rules database must be stored in a human-readable and editable format; YAML is an excellent choice for this purpose.

#### Rules Generation Strategies

Categorization rules can be generated through multiple complementary approaches, each corresponding to a different database file:

##### 1. Manual Specification (Highest Priority)

To accommodate rules specific to personal circumstances, the system allows users to manually specify rules using the defined rules format. These manually-defined rules take precedence over all other options.

**Key Considerations:**
- Transactions requiring more than two splits are typically specified manually
- While the current rules database format doesn't support multi-split transactions, the format should be designed for backward compatibility when this capability is added in future versions

##### 2. History-Based Determination (Medium Priority)

This approach analyzes past categorizations in the user's existing GNUCash file to generate a comprehensive set of rules.

**Implementation Details:**
- Employs a one-shot approach that processes the entire GNUCash database to generate rules
- Requires high confidence thresholds (e.g., minimum pattern length to avoid trivial matches like "COM")
- Generated rules must be reviewed and tested before deployment
- Rules determined through this method are stored in the standard rules database format

##### 3. Generative AI-Based Determination (Lowest Priority)

For transactions that cannot be categorized through existing rules, the system employs a generative AI agent with search capabilities to determine appropriate categorization and merchant identification.

**Operational Strategy:**
- Description normalization reduces the number of AI queries required
- The system caches AI results on-the-fly: when a new description requires querying, it first consults the database and returns cached results if available; otherwise, it runs the agent and updates the database
- This approach is the most time-consuming and therefore receives the lowest priority

**Scope Limitations:**
For approaches #2 and #3, consideration should be restricted to *debit* transactions only. Credit transactions require special handling, for which either manual specification (#1) or manual intervention is appropriate. For credit transactions that may be potential refunds, the system should search for matching transactions in the recent past on the same account and provide options for manual handling. Automatic handling of such transactions using a "Holding" account for potential refunds represents a potential improvement for future versions.

**Alternative Approaches:**
While it's possible to apply machine learning to past transactions to train a transformer-based classifier, this represents a more complex approach compared to using generative AI, which is likely to be more accurate due to its ability to leverage world knowledge.

#### Rules Application Priority

Rules must be applied in the following order after reading and normalizing OFX transactions:

1. Manual Specification
2. History-Based Determination  
3. Generative AI-Based Determination

### Integration Layer: System Components

The complete system comprises the following integrated components:

#### Transaction Analyzer
- Analyzes the existing GNUCash database based on user configuration specified in a YAML configuration file
- Supports configurable account filtering and date range selection
- Generates a rules database following the specified format
- **Note**: The existing `analyze_transactions.py` provides a strong foundation but requires adaptation to follow the specified rules database format

#### QFX Parser Library
- Loads QFX/OFX files and performs description normalization
- Provides normalized descriptions for subsequent category determination
- Designed as a general-purpose QFX library for use by other tools
- **Note**: `qfx_parser.py` serves as an excellent starting point for this component

#### Generative AI Agent
- Manages its own rules database for efficient operation
- Takes transaction descriptions as input and performs the following operations:
  - Checks existing rules database for matches and returns cached results when found
  - Determines merchant name and category with detailed reasoning for the selection
  - Updates the rules database with new entries for future use
- **Note**: `llm_categorization.py` provides a solid foundation for this component

#### Transaction Categorization Engine (Top-Level Component)
- Orchestrates the complete workflow by taking a GNUCash file and QFX file as inputs
- Performs the following operations:
  - Parses QFX transactions
  - Processes each *debit* transaction by applying rules in the specified priority order
  - Categorizes transactions, placing uncategorizable items in an "Unspecified" category for later manual handling
  - Generates a comprehensive categorization summary for user review and approval using the `rich` library for enhanced table formatting
  - Upon user approval, applies the categorization changes to the GNUCash database by creating new transactions

### User Interface and Workflow

The system provides a streamlined user experience through:
- **Rich-formatted output**: Clear, visually appealing tables showing categorization results
- **Summary reporting**: Comprehensive statistics on categorization success and areas requiring attention
- **Review and approval workflow**: Users can examine results before database modifications
- **Detailed feedback**: Clear indication of uncategorizable transactions requiring manual intervention

## Implementation Notes

This specification builds upon the existing prototype tools developed in the project, specifically leveraging:
- `analyze_transactions.py` for historical pattern analysis capabilities
- `qfx_parser.py` for transaction parsing and normalization functionality  
- `llm_categorizer.py` for AI-powered categorization features
- Established GNUCash Python bindings integration

The modular design ensures that each component can be developed, tested, and enhanced independently while maintaining clear interfaces and data flow between system layers.
