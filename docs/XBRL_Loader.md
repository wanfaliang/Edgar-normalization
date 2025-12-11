# Full relationships for a company (with fallback for Inline XBRL)
  python src/xbrl_loader.py --ticker MSFT --year 2024 --quarter 2 --show-children

  # Or for Amazon (uses filing-specific calc linkbase)
  python src/xbrl_loader.py --ticker AMZN --year 2024 --quarter 2 --show-children

  # Export to JSON for programmatic use
  python src/xbrl_loader.py --ticker MSFT --year 2024 --quarter 2 --export-json msft_calc.json

  Other useful options:

  # Show tree for a specific tag (recursive breakdown)
  python src/xbrl_loader.py --ticker AMZN --year 2024 --quarter 2 --tree Assets

  # List all parent (sum) tags
  python src/xbrl_loader.py --ticker AMZN --year 2024 --quarter 2 --list-parents

  # Use CIK instead of ticker
  python src/xbrl_loader.py --cik 1000209 --year 2024 --quarter 2 --show-children