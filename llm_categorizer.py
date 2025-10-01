#!/usr/bin/env python3
"""
LLM-based Transaction Categorizer with Internet Search
Uses LangGraph to create a REACT agent that categorizes transactions intelligently
"""

import sys
import json
import argparse
import os
from typing import Dict, List, Optional, TypedDict, Annotated
from datetime import datetime
from pathlib import Path
import re
import pdb

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

from rich.table import Table
from rich.console import Console

class AgentState(TypedDict):
    """State for the categorization agent"""
    transaction_description: str
    extracted_merchant: str
    search_results: str
    reasoning: str
    category: str
    confidence: float
    explanation: str
    messages: Annotated[List, "Messages in the conversation"]


class LLMTransactionCategorizer:
    """LLM-based transaction categorizer with internet search capability"""
    
    def __init__(self, openai_api_key: str = None, tavily_api_key: str = None):
        # Initialize API keys
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        
        if not self.openai_api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable or pass as parameter.")
        
        if not self.tavily_api_key:
            raise ValueError("Tavily API key required. Set TAVILY_API_KEY environment variable or pass as parameter.")
        
        # Initialize LLM and tools
        self.llm = ChatOpenAI(
                api_key=self.openai_api_key,  # pyright: ignore[reportArgumentType]
                model="gpt-4o-mini",  # Cost-effective model
                temperature=0.1  # Low temperature for consistent categorization
        )

        # Initialize
        self.search_tool = TavilySearch(
            api_key=self.tavily_api_key,
            max_results=3,
            search_depth="basic"
        )
        
        # Create the agent graph
        self.agent = self._create_agent()
        
        # Actual GNUCash categories from user's file
        self.common_categories = [
            "Expenses:Automobile",
            "Expenses:Automobile:Maintenance",
            "Expenses:Automobile:Rental",
            "Expenses:Automobile:Parking",
            "Expenses:Automobile:Gasoline",
            "Expenses:Automobile:Car Payment",
            "Expenses:Automobile:Taxes",
            "Expenses:Automobile:Upgrades",
            "Expenses:Automobile:Accessories",
            "Expenses:Bank Charges",
            "Expenses:Bank Charges:Interest Paid",
            "Expenses:Bank Charges:Fees",
            "Expenses:Bank Charges:Service Charge",
            "Expenses:Bills",
            "Expenses:Bills:Rent",
            "Expenses:Bills:Telephone",
            "Expenses:Bills:Cable-Satellite Television",
            "Expenses:Bills:Health Club",
            "Expenses:Bills:Electricity",
            "Expenses:Bills:Cellular",
            "Expenses:Bills:Water & Sewer",
            "Expenses:Bills:Other Loan Payment",
            "Expenses:Bills:Membership Fees",
            "Expenses:Bills:Common Fund",
            "Expenses:Bills:Online-Internet Service",
            "Expenses:Bills:Natural Gas-Oil",
            "Expenses:Bills:Homeowner's Dues",
            "Expenses:Bills:Commute",
            "Expenses:Bills:Garbage & Recycle",
            "Expenses:Bills:Home Security",
            "Expenses:Bills:Yard Maintenance",
            "Expenses:Bills:Streaming Services",
            "Expenses:Charitable Donations",
            "Expenses:Charitable Donations:Political Donations",
            "Expenses:Childcare",
            "Expenses:Cash Withdrawal",
            "Expenses:Cash Withdrawal:Miscellaneous Expenses",
            "Expenses:Cash Withdrawal:Cash Expeditures",
            "Expenses:Clothing",
            "Expenses:Clothing:Casual",
            "Expenses:Clothing:Formal",
            "Expenses:Clothing:Makeup",
            "Expenses:Clothing:Jewellery",
            "Expenses:Dining Out",
            "Expenses:Education",
            "Expenses:Education:Miscellaneous",
            "Expenses:Education:Fees",
            "Expenses:Education:Books",
            "Expenses:Education:Tuition",
            "Expenses:Education:Kids Classes",
            "Expenses:Electronics",
            "Expenses:Electronics:Gadgets",
            "Expenses:Electronics:Games",
            "Expenses:Electronics:Accesories",
            "Expenses:Electronics:Computers",
            "Expenses:Gifts",
            "Expenses:Gifts:General",
            "Expenses:Gifts:To India",
            "Expenses:Groceries",
            "Expenses:Groceries:Membership",
            "Expenses:Healthcare",
            "Expenses:Healthcare:Counter",
            "Expenses:Healthcare:Hospital",
            "Expenses:Healthcare:Physician",
            "Expenses:Healthcare:Athletic Club",
            "Expenses:Healthcare:Prescriptions",
            "Expenses:Healthcare:Home Gym",
            "Expenses:Healthcare:Eyecare (Before-Tax)",
            "Expenses:Healthcare:Dental",
            "Expenses:Healthcare:Eyecare",
            "Expenses:Healthcare:Miscellaneous",
            "Expenses:Household",
            "Expenses:Household:Baby Stuff",
            "Expenses:Household:Software",
            "Expenses:Household:Merchandise (Chicago)",
            "Expenses:Household:Merchandise",
            "Expenses:Household:House Cleaning",
            "Expenses:Insurance",
            "Expenses:Insurance:Life",
            "Expenses:Insurance:Umbrella",
            "Expenses:Insurance:Health (Before-Tax)",
            "Expenses:Insurance:Homeowner's-Renter's",
            "Expenses:Insurance:Health",
            "Expenses:Insurance:Automobile",
            "Expenses:Insurance:Renters",
            "Expenses:Insurance:Legal",
            "Expenses:Job Expense",
            "Expenses:Job Expense:Non-Reimbursed",
            "Expenses:Job Expense:Reimbursed",
            "Expenses:Leisure",
            "Expenses:Leisure:Musical Instruments",
            "Expenses:Leisure:Toys & Games",
            "Expenses:Leisure:Sporting Events",
            "Expenses:Leisure:Entertaining",
            "Expenses:Leisure:Tapes & CDs",
            "Expenses:Leisure:Books & Magazines",
            "Expenses:Leisure:Cultural Events",
            "Expenses:Leisure:Movies & Video Rentals",
            "Expenses:Leisure:Music Subscriptions",
            "Expenses:Leisure:Sporting Goods",
            "Expenses:Leisure:Phone Apps",
            "Expenses:Leisure:Music and Dance Classes",
            "Expenses:Leisure:Concerts",
            "Expenses:Leisure:Family Events-Parties",
            "Expenses:Leisure:Activities",
            "Expenses:Miscellaneous",
            "Expenses:Miscellaneous:Adjustment",
            "Expenses:Miscellaneous:Guest Expenses",
            "Expenses:Miscellaneous:Unclaimed",
            "Expenses:Miscellaneous:Depreciation",
            "Expenses:Miscellaneous:Fines",
            "Expenses:Miscellaneous:Unknown",
            "Expenses:Miscellaneous:Stationery",
            "Expenses:Miscellaneous:Tax Preparation",
            "Expenses:Miscellaneous:Finance Software",
            "Expenses:Miscellaneous:Family Events",
            "Expenses:Miscellaneous:Home-Transaction-Charges",
            "Expenses:Personal Care",
            "Expenses:Tax",
            "Expenses:Tax:Fed",
            "Expenses:Tax:Medicare",
            "Expenses:Tax:Property",
            "Expenses:Tax:SDI",
            "Expenses:Tax:State",
            "Expenses:Tax:Soc Sec",
            "Expenses:Tax:Fed-Previous Year",
            "Expenses:Tax:State-Previous Year",
            "Expenses:Taxes",
            "Expenses:Taxes:State-Provincial",
            "Expenses:Taxes:Medicare Tax",
            "Expenses:Taxes:Other Taxes",
            "Expenses:Taxes:Federal Income Tax",
            "Expenses:Taxes:Sales Tax",
            "Expenses:Taxes:Income Tax-Previous Year",
            "Expenses:Taxes:Social Security Tax",
            "Expenses:Taxes:State Income Tax",
            "Expenses:Taxes:Local Income Tax",
            "Expenses:Transportation",
            "Expenses:Transportation:Rideshare",
            "Expenses:Transportation:Airfare",
            "Expenses:Vacation",
            "Expenses:Vacation:Travel",
            "Expenses:Vacation:Purchases",
            "Expenses:Vacation:Lodging",
            "Expenses:Vacation:Activities",
            "Expenses:Vacation:Dining",
            "Expenses:Loan Payment",
            "Expenses:Loan Payment:Interest",
            "Expenses:Official",
            "Expenses:Official:Immigration",
            "Expenses:Official:Tax Preparation",
            "Expenses:Depreciation",
            "Expenses:Home Related",
            "Expenses:Home Related:Fees-Commisions",
            "Expenses:Home Related:Furnishings",
            "Expenses:Home Related:Moving Expenses",
            "Expenses:Home Related:Maintenance",
            "Expenses:Home Related:Remodel-Upgrades"
        ]
    
    
    def _create_agent(self) -> StateGraph:
        """Create the LangGraph agent for transaction categorization"""
        
        def search_transaction_info(transaction_description: str) -> str:
            """Search for information about a transaction/business"""
            # Create a smart search query from the transaction description
            query = f"{transaction_description} company industry type"
            output = self.search_tool.invoke(query)

            # validate outputs.
            if not output:
                return "No search results found."
            results = output['results']
            if len(results) == 0:
                return "No search results found."
            
            # Combine search results
            combined_results = []
            for result in results[:3]:  # Top 3 results
                if isinstance(result, dict):
                    content = result.get('content', '')
                    if content:
                        combined_results.append(content[:200])  # Limit length
        
            return " | ".join(combined_results) if combined_results else "No relevant information found"
                    
        def search_node(state: AgentState) -> AgentState:
            """Search for transaction information"""
            description = state["transaction_description"]
            search_result = search_transaction_info(transaction_description=description)           
            state["search_results"] = search_result
            state["messages"].append(ToolMessage(content=search_result, tool_call_id="search"))
            
            return state
        
        def categorize_node(state: AgentState) -> AgentState:
            """Use LLM to categorize the transaction"""
            
            # Create categorization prompt
            prompt = f"""
You are an expert financial transaction categorizer. Your task is to categorize a transaction into the most appropriate expense category.

Transaction Description: {state['transaction_description']}
Internet Search Results: {state['search_results']}

Common Categories:
{chr(10).join([f"- {cat}" for cat in self.common_categories])}

Please note that if the description contains the following, it may be related to Credit Card bill payments, so use the category "Unspecified" for these and leave the merchant name empty.

- INTERNET PAYMENT THANK YOU

Based on the transaction description and internet search results about the business, please:

1. Determine the most appropriate category from the list above (or suggest a new one if none fit).
2. Determine the official merchant or business name using the search results (if applicable).
2. Provide a confidence score from 0.0 to 1.0
3. Explain your reasoning

Please respond in the following raw JSON format:
{{
    "category": "Expenses:Category:Subcategory",
    "merchant": "Any official merchant name that you identified from searching (or) empty string if not applicable or none found"
    "description": "The input original description"
    "confidence": 0.95,
    "reasoning": "Detailed explanation of why this category was chosen"
}}
DO NOT include backticks or any Markdown formatting on top of raw JSON content.

Some categorization guidelines based on GNUCash structure:

- Netflix, Spotify, iTunes, streaming services → "Expenses:Bills:Streaming Services"
- Restaurants, coffee shops → "Expenses:Dining Out"
- Gas stations → "Expenses:Automobile:Gasoline"
- Uber, Lyft → "Expenses:Transportation:Rideshare"
- Parking fees → "Expenses:Automobile:Parking"
- LinkedIn, business software → "Expenses:Household:Software" 
- Starbucks, cafes → "Expenses:Dining Out"
- Target, Walmart → "Expenses:Household:Merchandise"
- Costco, Vons, Amazon Fresh, Ralphs, Grocery stores → "Expenses:Groceries"
- Health/fitness clubs → "Expenses:Bills:Health Club" 
- Phone bills (T-Mobile, Spectrum Mobile) → "Expenses:Bills:Cellular" or "Expenses:Bills:Telephone"
- Internet service (like Spectrum) → "Expenses:Bills:Online-Internet Service"
- Clothing stores → "Expenses:Clothing"
- Electronics stores → "Expenses:Electronics:Gadgets" or "Expenses:Electronics:Computers"

You may use the "Unspecified" category to tag transactions that you are unable to classify using the provided categories and rules.
"""
            
            # Get LLM response
            messages = [HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)
            
            try:
                # Parse JSON response
                import json
                result = json.loads(response.content)
                pdb.set_trace()
                
                state["category"] = result.get("category", "Unknown")
                state["confidence"] = float(result.get("confidence", 0.0))
                state["reasoning"] = result.get("reasoning", "No reasoning provided")
                state["explanation"] = f"LLM categorized based on merchant '{state['extracted_merchant']}' and search results"
                state["extracted_merchant"] = result.get("merchant")
                
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                state["category"] = "Unknown"
                state["confidence"] = 0.0
                state["reasoning"] = "Failed to parse LLM response"
                state["explanation"] = f"LLM response: {response.content}"
                state["extracted_merchant"] = "Unknown"
            
            state["messages"].append(AIMessage(content=f"Categorized as: {state['category']} (confidence: {state['confidence']})"))
            return state
        
        # Create the graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("search", search_node)
        workflow.add_node("categorize", categorize_node)
        
        # Add edges
        workflow.set_entry_point("search")
        workflow.add_edge("search", "categorize")
        workflow.add_edge("categorize", END)
        
        return workflow.compile()
    
    def categorize_transaction(self, description: str, verbose: bool = False) -> Dict:
        """Categorize a single transaction"""
        
        if verbose:
            print(f"🔍 Categorizing: {description}")
        
        # Initialize state
        initial_state: AgentState = {
            "transaction_description": description,
            "extracted_merchant": "",
            "search_results": "",
            "reasoning": "",
            "category": "",
            "confidence": 0.0,
            "explanation": "",
            "messages": []
        }
        
        # Run the agent
        result = self.agent.invoke(initial_state)
        
        if verbose:
            print(f"🎯 Result: {result['category']} (confidence: {result['confidence']:.1%})")
            print(f"💭 Reasoning: {result['reasoning']}")
        
        return {
            "transaction_description": description,
            "extracted_merchant": result["extracted_merchant"],
            "predicted_category": result["category"],
            "confidence": result["confidence"],
            "reasoning": result["reasoning"],
            "search_results": result["search_results"],
            "timestamp": datetime.now().isoformat()
        }
    
    def categorize_batch(self, descriptions: List[str], verbose: bool = False) -> List[Dict]:
        """Categorize multiple transactions"""
        results = []
        
        for i, description in enumerate(descriptions):
            if verbose:
                print(f"\n--- Transaction {i+1}/{len(descriptions)} ---")
            
            result = self.categorize_transaction(description, verbose)
            results.append(result)
        
        return results

def display_results(results):
    """
    Display categorization results in a nicely formatted Rich table.
    
    Args:
        results (list[dict]): Each dict should have keys:
            - extracted_merchant
            - predicted_category
            - confidence (float)
            - transaction_description
    """
    console = Console()
    table = Table(show_header=True, header_style="bold magenta")

    # overflow="fold" ensures long text wraps instead of truncating
    table.add_column("Description", style="white", overflow="fold")
    table.add_column("Merchant", style="cyan", no_wrap=True)
    table.add_column("Category", style="green")
    table.add_column("Confidence", style="yellow")
    table.add_column("Reasoning", style="white", overflow="fold")

    for result in results:
        merchant = result.get("extracted_merchant", "")[:20]
        category = result.get("predicted_category", "")[:40]
        confidence = f"{result.get('confidence', 0.0):.1%}"
        description = result.get("transaction_description", "")
        reasoning = result.get('reasoning', "")
        table.add_row(description, merchant, category, confidence, reasoning)

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="LLM-based transaction categorizer with internet search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Categorize a single transaction
  python llm_categorizer.py "Netflix.com 408-54037"
  
  # Categorize multiple transactions from a file
  python llm_categorizer.py --file transactions.txt
  
  # Use verbose mode to see detailed reasoning
  python llm_categorizer.py "STARBUCKS 12345 SAN DIEGO" --verbose
  
  # Save results to JSON file
  python llm_categorizer.py "UBER TRIP" --output results.json

Environment Variables Required:
  OPENAI_API_KEY: Your OpenAI API key
  TAVILY_API_KEY: Your Tavily search API key
        """
    )
    
    parser.add_argument('description', nargs='?', help='Transaction description to categorize')
    parser.add_argument('--file', '-f', help='File containing transaction descriptions (one per line)')
    parser.add_argument('--output', '-o', help='Output file for results (JSON format)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed reasoning')
    
    args = parser.parse_args()
    
    if not args.description and not args.file:
        parser.error("Must provide either a transaction description or a file with --file")
    
    # Check environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    if not os.getenv("TAVILY_API_KEY"):
        print("Error: TAVILY_API_KEY environment variable not set")
        print("Get a free API key at: https://tavily.com/")
        sys.exit(1)
    
    # Initialize categorizer
    try:
        categorizer = LLMTransactionCategorizer()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Process transactions
    if args.description:
        # Single transaction
        result = categorizer.categorize_transaction(args.description, args.verbose)
        
        if not args.verbose:
            display_results([result])
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Results saved to {args.output}")
    
    elif args.file:
        # Multiple transactions from file
        if not Path(args.file).exists():
            print(f"Error: File not found: {args.file}")
            sys.exit(1)
        
        with open(args.file, 'r') as f:
            descriptions = [line.strip() for line in f if line.strip()]
        
        if not descriptions:
            print("Error: No transaction descriptions found in file")
            sys.exit(1)
        
        print(f"Processing {len(descriptions)} transactions...")
        results = categorizer.categorize_batch(descriptions, args.verbose)
        
        # Show summary table
        if not args.verbose:
            display_results(results)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
