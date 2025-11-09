"""
AI-Powered Tag Mapper
=====================
Uses AI (Claude) to intelligently map company-specific XBRL tags
to standardized financial concepts for comparability across companies.

Author: Faliang & Claude
Date: November 2025
"""

import json
import anthropic
import os
from pathlib import Path
from typing import Dict, List, Optional
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AITagMapper:
    """
    Intelligent tag mapping using Claude AI
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize AI Tag Mapper

        Args:
            api_key: Anthropic API key (if None, reads from environment)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found. Set environment variable or pass api_key parameter.")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        logger.info("AI Tag Mapper initialized")

        # Standard financial concepts taxonomy
        self.standard_concepts = self._load_standard_concepts()

    def _load_standard_concepts(self) -> Dict:
        """
        Define standard financial concepts for mapping
        These are the normalized concepts we want to map to
        """
        return {
            # Income Statement
            "Revenue": {
                "category": "Income Statement",
                "description": "Total revenue from all sources",
                "variations": ["Revenues", "SalesRevenue", "TotalRevenue", "RevenueFromContractWithCustomer"]
            },
            "CostOfRevenue": {
                "category": "Income Statement",
                "description": "Cost of goods sold or cost of services",
                "variations": ["CostOfGoodsSold", "CostOfSales", "CostOfServices"]
            },
            "GrossProfit": {
                "category": "Income Statement",
                "description": "Revenue minus cost of revenue",
                "variations": []
            },
            "OperatingExpenses": {
                "category": "Income Statement",
                "description": "Total operating expenses",
                "variations": ["OperatingExpensesTotal"]
            },
            "OperatingIncome": {
                "category": "Income Statement",
                "description": "Income from operations",
                "variations": ["OperatingIncomeLoss", "IncomeLossFromOperations"]
            },
            "NetIncome": {
                "category": "Income Statement",
                "description": "Bottom line net income",
                "variations": ["NetIncomeLoss", "ProfitLoss", "NetEarnings"]
            },
            "EPS_Basic": {
                "category": "Income Statement",
                "description": "Basic earnings per share",
                "variations": ["EarningsPerShareBasic"]
            },
            "EPS_Diluted": {
                "category": "Income Statement",
                "description": "Diluted earnings per share",
                "variations": ["EarningsPerShareDiluted"]
            },

            # Balance Sheet - Assets
            "TotalAssets": {
                "category": "Balance Sheet - Assets",
                "description": "Total assets",
                "variations": ["Assets", "AssetTotal"]
            },
            "CurrentAssets": {
                "category": "Balance Sheet - Assets",
                "description": "Current assets",
                "variations": ["AssetsCurrent"]
            },
            "Cash": {
                "category": "Balance Sheet - Assets",
                "description": "Cash and cash equivalents",
                "variations": ["CashAndCashEquivalents", "CashCashEquivalentsRestrictedCash"]
            },
            "ShortTermInvestments": {
                "category": "Balance Sheet - Assets",
                "description": "Short-term investments",
                "variations": ["MarketableSecuritiesCurrent"]
            },
            "AccountsReceivable": {
                "category": "Balance Sheet - Assets",
                "description": "Accounts receivable net",
                "variations": ["AccountsReceivableNet", "ReceivablesNet"]
            },
            "Inventory": {
                "category": "Balance Sheet - Assets",
                "description": "Inventory",
                "variations": ["InventoryNet"]
            },
            "PropertyPlantEquipment": {
                "category": "Balance Sheet - Assets",
                "description": "Property, plant and equipment, net",
                "variations": ["PropertyPlantAndEquipmentNet", "PPENet"]
            },
            "Goodwill": {
                "category": "Balance Sheet - Assets",
                "description": "Goodwill",
                "variations": []
            },
            "IntangibleAssets": {
                "category": "Balance Sheet - Assets",
                "description": "Intangible assets, net",
                "variations": ["IntangibleAssetsNet"]
            },

            # Balance Sheet - Liabilities
            "TotalLiabilities": {
                "category": "Balance Sheet - Liabilities",
                "description": "Total liabilities",
                "variations": ["Liabilities", "LiabilitiesTotal"]
            },
            "CurrentLiabilities": {
                "category": "Balance Sheet - Liabilities",
                "description": "Current liabilities",
                "variations": ["LiabilitiesCurrent"]
            },
            "AccountsPayable": {
                "category": "Balance Sheet - Liabilities",
                "description": "Accounts payable",
                "variations": []
            },
            "ShortTermDebt": {
                "category": "Balance Sheet - Liabilities",
                "description": "Short-term debt",
                "variations": ["DebtCurrent", "ShortTermBorrowings"]
            },
            "LongTermDebt": {
                "category": "Balance Sheet - Liabilities",
                "description": "Long-term debt",
                "variations": ["LongTermDebtNoncurrent", "DebtNoncurrent"]
            },

            # Balance Sheet - Equity
            "StockholdersEquity": {
                "category": "Balance Sheet - Equity",
                "description": "Total stockholders equity",
                "variations": ["Equity", "ShareholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
            },
            "CommonStock": {
                "category": "Balance Sheet - Equity",
                "description": "Common stock value",
                "variations": ["CommonStockValue"]
            },
            "RetainedEarnings": {
                "category": "Balance Sheet - Equity",
                "description": "Retained earnings",
                "variations": ["RetainedEarningsAccumulatedDeficit"]
            },

            # Cash Flow Statement
            "OperatingCashFlow": {
                "category": "Cash Flow Statement",
                "description": "Net cash from operating activities",
                "variations": ["NetCashProvidedByUsedInOperatingActivities", "CashFlowFromOperations"]
            },
            "InvestingCashFlow": {
                "category": "Cash Flow Statement",
                "description": "Net cash from investing activities",
                "variations": ["NetCashProvidedByUsedInInvestingActivities"]
            },
            "FinancingCashFlow": {
                "category": "Cash Flow Statement",
                "description": "Net cash from financing activities",
                "variations": ["NetCashProvidedByUsedInFinancingActivities"]
            },
            "CapitalExpenditures": {
                "category": "Cash Flow Statement",
                "description": "Capital expenditures",
                "variations": ["PaymentsToAcquirePropertyPlantAndEquipment", "CapEx"]
            },

            # Investment Company Specific
            "InvestmentAtFairValue": {
                "category": "Investment Company",
                "description": "Investments at fair value",
                "variations": ["InvestmentOwnedAtFairValue", "InvestmentsAtFairValue"]
            },
            "InvestmentAtCost": {
                "category": "Investment Company",
                "description": "Investments at cost",
                "variations": ["InvestmentOwnedAtCost"]
            },
            "InvestmentIncome": {
                "category": "Investment Company",
                "description": "Investment income",
                "variations": ["InterestAndDividendIncome", "InvestmentIncomeInterest"]
            },

            # Share Information
            "SharesOutstanding": {
                "category": "Share Information",
                "description": "Common shares outstanding",
                "variations": ["CommonStockSharesOutstanding", "CommonStockSharesIssued"]
            },
            "WeightedAverageShares_Basic": {
                "category": "Share Information",
                "description": "Weighted average shares - basic",
                "variations": ["WeightedAverageNumberOfSharesOutstandingBasic"]
            },
            "WeightedAverageShares_Diluted": {
                "category": "Share Information",
                "description": "Weighted average shares - diluted",
                "variations": ["WeightedAverageNumberOfDilutedSharesOutstanding"]
            },
        }

    def map_company_tags(self, company_profile: Dict, sample_size: int = 30) -> Dict:
        """
        Use AI to map a company's tags to standard concepts

        Args:
            company_profile: Company tag profile from extractor
            sample_size: Number of top tags to map initially (for POC)

        Returns:
            Mapping dictionary with confidence scores
        """
        cik = company_profile['cik']
        company_name = company_profile['company_name']
        industry = company_profile['industry']

        logger.info(f"Mapping tags for {company_name} (CIK: {cik})")
        logger.info(f"Total tags: {company_profile['total_unique_tags']}")

        # Take top N most frequently used tags
        tag_details = company_profile['tag_details'][:sample_size]

        logger.info(f"Mapping top {len(tag_details)} tags using AI...")

        # Prepare prompt
        prompt = self._create_mapping_prompt(company_name, industry, tag_details)

        # Call Claude API
        try:
            mapping_result = self._call_claude_api(prompt)
            logger.info("AI mapping completed successfully")

            # Parse and validate result
            mapping = self._parse_mapping_result(mapping_result, tag_details)

            # Add metadata
            mapping_with_metadata = {
                'cik': cik,
                'company_name': company_name,
                'industry': industry,
                'mapping_date': datetime.now().isoformat(),
                'tags_mapped': len(mapping),
                'model': 'claude-sonnet-4-5',
                'mappings': mapping
            }

            return mapping_with_metadata

        except Exception as e:
            logger.error(f"Error during AI mapping: {e}")
            raise

    def _create_mapping_prompt(self, company_name: str, industry: str, tag_details: List[Dict]) -> str:
        """Create prompt for Claude API"""

        # Build tag list with metadata
        tag_list = []
        for tag in tag_details:
            tag_info = f"""
Tag: {tag['tag']}
  - Label: {tag['tlabel']}
  - Documentation: {tag['doc'][:200] if tag['doc'] else 'N/A'}
  - Type: {tag['datatype']}
  - Balance: {tag['crdr'] if tag['crdr'] else 'N/A'}
  - Period: {'Instant' if tag['iord'] == 'I' else 'Duration' if tag['iord'] == 'D' else 'N/A'}
  - Usage count: {tag['occurrence_count']}
  - Unit: {tag['common_unit']}
"""
            tag_list.append(tag_info.strip())

        # Build standard concepts list
        concepts_list = []
        for concept, info in self.standard_concepts.items():
            concepts_list.append(f"{concept} ({info['category']}): {info['description']}")

        prompt = f"""You are an expert financial data analyst specializing in XBRL taxonomy mapping.

TASK: Map company-specific XBRL tags to standardized financial concepts.

COMPANY INFORMATION:
- Name: {company_name}
- Industry: {industry}

STANDARD CONCEPTS TAXONOMY:
{chr(10).join(concepts_list)}

COMPANY TAGS TO MAP:
{chr(10).join(tag_list)}

INSTRUCTIONS:
1. For each tag, identify the most appropriate standard concept
2. Assign a confidence score (0.0-1.0):
   - 1.0 = Perfect match (e.g., "NetIncomeLoss" → "NetIncome")
   - 0.9 = Very close match with minor variation
   - 0.8 = Good match, semantically equivalent
   - 0.7 = Reasonable match but some ambiguity
   - 0.5 = Uncertain/partial match
   - 0.0 = No good match (unmappable)

3. If confidence < 0.7, provide explanation
4. For tags with no good match, suggest "CUSTOM" and note why
5. Consider the tag's metadata (label, documentation, type, usage) in your assessment

RESPONSE FORMAT (JSON):
{{
  "mappings": [
    {{
      "tag": "TagName",
      "standard_concept": "StandardConcept",
      "confidence": 0.95,
      "reasoning": "Brief explanation of why this mapping makes sense"
    }}
  ]
}}

Provide mappings for all {len(tag_details)} tags."""

        return prompt

    def _call_claude_api(self, prompt: str) -> str:
        """Call Claude API for tag mapping"""
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=8000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = message.content[0].text
            return response_text

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    def _parse_mapping_result(self, api_response: str, original_tags: List[Dict]) -> List[Dict]:
        """Parse and validate API response"""
        try:
            # Extract JSON from response
            # Claude might wrap JSON in markdown code blocks
            if "```json" in api_response:
                json_start = api_response.find("```json") + 7
                json_end = api_response.find("```", json_start)
                json_text = api_response[json_start:json_end].strip()
            elif "```" in api_response:
                json_start = api_response.find("```") + 3
                json_end = api_response.find("```", json_start)
                json_text = api_response[json_start:json_end].strip()
            else:
                json_text = api_response.strip()

            # Parse JSON
            result = json.loads(json_text)
            mappings = result.get('mappings', [])

            # Validate mappings
            validated_mappings = []
            for mapping in mappings:
                if all(key in mapping for key in ['tag', 'standard_concept', 'confidence']):
                    validated_mappings.append(mapping)
                else:
                    logger.warning(f"Skipping invalid mapping: {mapping}")

            logger.info(f"Parsed {len(validated_mappings)} valid mappings")
            return validated_mappings

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {api_response}")
            raise

    def save_mapping(self, mapping: Dict, output_dir: Path):
        """Save mapping to JSON file"""
        output_dir.mkdir(parents=True, exist_ok=True)

        cik = mapping['cik']
        company_name = mapping['company_name'].replace('/', '_').replace('\\', '_')[:50]

        filename = f"mapping_{cik}_{company_name}.json"
        filepath = output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved mapping to {filepath}")
        return filepath


def main():
    """Test AI mapping on sample companies"""
    import sys
    from pathlib import Path

    # Get company tag profile directory
    if len(sys.argv) > 1:
        profiles_dir = Path(sys.argv[1])
    else:
        profiles_dir = Path('data/sec_data/extracted/2024q3/company_tag_profiles')

    output_dir = profiles_dir / 'ai_mappings'
    output_dir.mkdir(exist_ok=True)

    # Initialize mapper
    mapper = AITagMapper()

    # Load company profiles
    profile_files = list(profiles_dir.glob('company_*_tags.json'))

    if not profile_files:
        logger.error(f"No company profiles found in {profiles_dir}")
        return

    logger.info(f"Found {len(profile_files)} company profiles")

    # Map first 3 companies as POC
    n_companies = min(3, len(profile_files))
    logger.info(f"Mapping tags for {n_companies} companies...")

    results = []
    for i, profile_file in enumerate(profile_files[:n_companies]):
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {i+1}/{n_companies}: {profile_file.name}")
        logger.info(f"{'='*60}")

        # Load profile
        with open(profile_file, 'r', encoding='utf-8') as f:
            profile = json.load(f)

        # Map tags
        try:
            mapping = mapper.map_company_tags(profile, sample_size=30)

            # Save mapping
            mapper.save_mapping(mapping, output_dir)

            results.append({
                'cik': profile['cik'],
                'company_name': profile['company_name'],
                'tags_mapped': len(mapping['mappings']),
                'high_confidence': len([m for m in mapping['mappings'] if m['confidence'] >= 0.8]),
                'medium_confidence': len([m for m in mapping['mappings'] if 0.5 <= m['confidence'] < 0.8]),
                'low_confidence': len([m for m in mapping['mappings'] if m['confidence'] < 0.5]),
            })

        except Exception as e:
            logger.error(f"Failed to map {profile['company_name']}: {e}")
            continue

    # Print summary
    print(f"\n{'='*60}")
    print("AI MAPPING SUMMARY")
    print(f"{'='*60}")
    for result in results:
        print(f"\n{result['company_name']} (CIK: {result['cik']})")
        print(f"  Total tags mapped: {result['tags_mapped']}")
        print(f"  High confidence (≥0.8): {result['high_confidence']}")
        print(f"  Medium confidence (0.5-0.8): {result['medium_confidence']}")
        print(f"  Low confidence (<0.5): {result['low_confidence']}")

    print(f"\nMappings saved to: {output_dir}")


if __name__ == "__main__":
    main()
