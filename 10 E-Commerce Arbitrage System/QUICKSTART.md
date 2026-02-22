# Quick Start Guide

Get your E-Commerce Arbitrage System up and running in minutes.

## Prerequisites

- Python 3.8 or higher
- Amazon Seller account (for SP-API access)
- Keepa API subscription (recommended)

## Installation

### 1. Clone and Navigate

```bash
cd "10 E-Commerce Arbitrage System"
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Credentials

Copy the example configuration:

```bash
cp config/config.example.yaml config/config.yaml
cp .env.example .env
```

Edit `config/config.yaml` and `.env` with your credentials:

**Minimum Required:**
- Amazon SP-API credentials (from Amazon Seller Central)
- Keepa API key (from keepa.com)
- Email SMTP credentials (for alerts)

**Optional but Recommended:**
- Amazon Product Advertising API
- Retail API keys (Walmart, Best Buy)
- Telegram bot (for mobile alerts)

### 4. Set Up API Credentials

#### Amazon SP-API

1. Go to Amazon Seller Central > Apps & Services
2. Register a new application
3. Copy the credentials to your config file

#### Keepa API

1. Sign up at https://keepa.com
2. Subscribe to API access ($19-149/month)
3. Get your API key from account settings

#### Email (Gmail Example)

1. Enable 2-factor authentication on your Google account
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Use the app password in your config

## Quick Test

### Test Configuration

```bash
python main.py --show-deals
```

This should initialize the system and show any existing deals in the database.

### Run Your First Scan

```bash
python main.py --scanner amazon
```

This will scan Amazon for deals using your configured settings.

## Basic Usage

### Scan All Sources

```bash
python main.py --scan-all
```

### Scan Specific Source

```bash
python main.py --scanner amazon
python main.py --scanner retail
```

### View Top Deals

```bash
python main.py --show-deals --min-roi 40
```

### Send Daily Report

```bash
python main.py --report
```

## Configuration Tips

### 1. Adjust ROI Threshold

In `config/config.yaml`:

```yaml
profit:
  min_roi: 30.0  # Increase for more selective deals
```

### 2. Configure Watchlist

Add ASINs you want to monitor:

```yaml
amazon:
  watchlist_asins:
    - "B08N5WRWNW"
    - "B07XJ8C8F5"
```

### 3. Set Up Automated Scans

Use cron (Linux/Mac) or Task Scheduler (Windows):

```bash
# Run scan every 2 hours
0 */2 * * * cd /path/to/system && python main.py --scan-all

# Daily report at 8 AM
0 8 * * * cd /path/to/system && python main.py --report
```

## Analysis

Open the Jupyter notebook for detailed analysis:

```bash
jupyter notebook notebooks/analysis.ipynb
```

## Common Issues

### "No module named 'keepa'"

Install the keepa package:
```bash
pip install keepa
```

### "Database file not found"

Create the data directory:
```bash
mkdir -p data
```

### "Invalid API credentials"

Double-check your credentials in `config/config.yaml` and ensure:
- No extra spaces
- Quotes are correct
- All required fields are filled

### "No deals found"

This is normal on first run. The system needs time to discover deals. Try:
1. Add some ASINs to your watchlist
2. Lower the min_roi threshold temporarily
3. Check that your Keepa API is working

## Next Steps

1. **Optimize filters**: Adjust sales rank, category, and price filters
2. **Add watchlists**: Monitor specific products or categories
3. **Analyze performance**: Use the Jupyter notebook to identify best categories
4. **Automate**: Set up scheduled scans with cron
5. **Scale up**: Add more retail sources and wholesale sites

## Getting Help

- Check the main README.md for detailed documentation
- Review the configuration file comments
- Examine example notebooks
- Check API documentation for:
  - Amazon SP-API: https://developer-docs.amazon.com/sp-api/
  - Keepa API: https://keepa.com/#!api

## Important Notes

### Legal & Ethical

- **Respect Terms of Service**: Only use official APIs when available
- **Rate Limiting**: Don't exceed API rate limits
- **Authenticity**: Never sell counterfeit products
- **Gating**: Respect Amazon's brand restrictions
- **Taxes**: Track and report all income properly

### Risk Management

- Start small with low-cost items
- Verify product condition and authenticity
- Account for returns (typically 2-5%)
- Monitor price changes daily
- Don't invest more than you can afford to lose

### Best Practices

- **Diversify**: Don't rely on a single source
- **Track Performance**: Use the database to learn what works
- **Stay Updated**: Amazon fees and policies change
- **Test First**: Buy one item before scaling up
- **Quality Control**: Inspect all products before sending to FBA

## Sample Workflow

1. **Morning**: Check email digest of overnight deals
2. **Research**: Investigate top 5-10 opportunities
3. **Verify**: Check Amazon for current pricing and competition
4. **Purchase**: Buy 1-3 best deals
5. **Evening**: Run manual scan for time-sensitive deals
6. **Weekly**: Review performance in Jupyter notebook
7. **Monthly**: Optimize filters based on actual results

Good luck with your arbitrage business!
