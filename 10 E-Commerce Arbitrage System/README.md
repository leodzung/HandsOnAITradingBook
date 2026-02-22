# E-Commerce Arbitrage System

An automated system for discovering profitable resale opportunities across multiple e-commerce platforms.

## Overview

This system scans multiple sources (retail websites, wholesale platforms, Amazon) to identify products that can be purchased at a low price and resold on Amazon or other marketplaces for profit.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator (main.py)                    │
│                    Schedules & Coordinates                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┼────────────┬─────────────┐
          ▼            ▼            ▼             ▼
    ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
    │ Amazon  │  │ Retail  │  │Wholesale│  │  Deal   │
    │ Scanner │  │ Scanner │  │ Scanner │  │   API   │
    │         │  │         │  │         │  │ Scanner │
    └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘
         │            │            │             │
         └────────────┴────────────┴─────────────┘
                       │
                       ▼
              ┌────────────────┐
              │ Deal Aggregator│
              │  & Normalizer  │
              └────────┬───────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │  Profit  │ │  Filter  │ │  Risk    │
    │Calculator│ │  Engine  │ │ Analyzer │
    └────┬─────┘ └────┬─────┘ └────┬─────┘
         │            │            │
         └────────────┴────────────┘
                      │
                      ▼
              ┌────────────────┐
              │    Database    │
              │   (SQLite)     │
              └────────┬───────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │  Email   │ │ Telegram │ │Dashboard │
    │  Alerts  │ │   Bot    │ │   Web    │
    └──────────┘ └──────────┘ └──────────┘
```

## Components

### 1. Scanners (`src/scanners/`)
- **amazon_scanner.py** - Scans Amazon for deals using Product Advertising API
- **retail_scanner.py** - Monitors retail sites (Walmart, Target, Best Buy)
- **wholesale_scanner.py** - Checks liquidation/wholesale platforms
- **deal_api_scanner.py** - Integrates with deal aggregator APIs

### 2. Analyzers (`src/analyzers/`)
- **profit_calculator.py** - Calculates true profit after all fees
- **price_tracker.py** - Tracks historical prices and trends
- **competition_analyzer.py** - Analyzes seller competition
- **sales_rank_analyzer.py** - Estimates sales velocity

### 3. Integrations (`src/integrations/`)
- **amazon_api.py** - Amazon SP-API & Product Advertising API wrapper
- **keepa_api.py** - Keepa API for price history and tracking
- **rainforest_api.py** - Alternative Amazon data API
- **retail_apis.py** - Walmart, Target API integrations

### 4. Utils (`src/utils/`)
- **database.py** - SQLite database operations
- **notifications.py** - Email, SMS, Telegram alerts
- **config.py** - Configuration management
- **logger.py** - Logging utilities

## Key Features

### Profit Calculation
Accounts for all costs:
- Purchase price
- Amazon referral fees (8-15% depending on category)
- FBA fees (storage + fulfillment)
- Shipping costs (to Amazon warehouse)
- Sales tax
- Return rate estimates
- Monthly storage fees

### Multi-Source Scanning
- **Amazon**: Find Amazon deals to resell in different marketplaces
- **Retail Sites**: Monitor clearance sections via APIs/scraping
- **Wholesale**: Check liquidation platforms (via APIs)
- **Deal APIs**: Integrate commercial deal-finding services

### Smart Filtering
- Minimum ROI threshold (e.g., 30%+)
- Maximum competition (number of sellers)
- Sales rank requirements
- Category restrictions (avoid restricted categories)
- Brand gating checks

### Risk Analysis
- Price volatility score
- Sales rank stability
- Number of competing sellers
- Review quality/quantity
- Historical price trends

## Installation

```bash
cd "10 E-Commerce Arbitrage System"
pip install -r requirements.txt
```

## Configuration

1. Copy `config/config.example.yaml` to `config/config.yaml`
2. Add your API credentials:
   - Amazon SP-API credentials
   - Keepa API key
   - Email/Telegram credentials
3. Configure scanning parameters (ROI thresholds, categories, etc.)

## Usage

### Run Full Scan
```bash
python main.py --scan-all
```

### Run Specific Scanner
```bash
python main.py --scanner amazon
python main.py --scanner retail
python main.py --scanner wholesale
```

### View Top Opportunities
```bash
python main.py --show-deals --min-roi 40
```

### Generate Report
```bash
python main.py --report --days 7
```

## Data Flow

1. **Scanning Phase**: Each scanner runs on schedule (e.g., every 2 hours)
2. **Data Normalization**: Raw deal data normalized to common format
3. **Enrichment**: Add Amazon pricing, sales rank, competition data
4. **Profit Calculation**: Calculate true profit after all fees
5. **Filtering**: Apply ROI, competition, and risk filters
6. **Storage**: Save qualified deals to database
7. **Alerting**: Send notifications for high-value opportunities
8. **Dashboard**: View and analyze deals in web interface

## Database Schema

### deals table
- product_asin
- product_title
- source (amazon/walmart/wholesale/etc.)
- source_price
- amazon_price
- estimated_profit
- roi_percentage
- sales_rank
- num_sellers
- first_seen
- last_updated
- status (new/purchased/rejected)

### price_history table
- asin
- timestamp
- price
- source

## API Requirements

### Required APIs:
- **Amazon SP-API** (free, requires seller account)
  - Product data, pricing, sales rank

### Recommended APIs:
- **Keepa API** ($19-149/month)
  - Historical price tracking
  - Sales rank history
  - Best deals finder

### Optional APIs:
- **Rainforest API** (pay-per-request)
  - Alternative to Amazon API
- **Walmart API** (free with approval)
- **Target API** (available via RedCircle API)

## Cost Considerations

### Amazon FBA Fees
- Referral fee: 8-15% of sale price
- Fulfillment fee: $3-8 per item (size/weight dependent)
- Monthly storage: $0.75-$2.40 per cubic foot
- Long-term storage: Additional fees after 365 days

### ROI Calculation Formula
```
ROI = ((Selling Price - All Costs) / All Costs) * 100

Where All Costs = Purchase Price + Shipping + Amazon Fees + Storage
```

## Scheduled Automation

Use cron or Task Scheduler to run scans automatically:

```bash
# Run every 2 hours
0 */2 * * * cd /path/to/system && python main.py --scan-all

# Daily report at 8 AM
0 8 * * * cd /path/to/system && python main.py --report --email
```

## Notebooks

- **analysis.ipynb** - Analyze historical deal performance
- **category_analysis.ipynb** - Identify best categories
- **profit_optimization.ipynb** - Optimize ROI thresholds

## Legal & Ethical Considerations

- Respect robots.txt and terms of service
- Use official APIs when available
- Implement rate limiting
- Don't resell restricted/gated brands without approval
- Verify product authenticity
- Follow Amazon's resale policies

## Future Enhancements

- ML model to predict profitable products
- Image recognition for product matching
- Chrome extension for manual searching
- Mobile app for notifications
- Integration with inventory management
- Automated purchasing (with approval workflow)
