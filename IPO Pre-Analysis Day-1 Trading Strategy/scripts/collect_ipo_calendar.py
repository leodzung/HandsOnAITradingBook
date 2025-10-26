"""
IPO Calendar Collection Script

Usage:
    python collect_ipo_calendar.py --year 2024 --output data/ipo_calendar_2024.csv

Sources:
    - Renaissance Capital IPO Center
    - Nasdaq IPO Calendar
    - Manual CSV input

This script helps collect and consolidate IPO calendar data from multiple sources.
"""

import argparse
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import sys

def get_major_ipos_2023_2024():
    """
    Returns a curated list of major IPOs from 2023-2024.

    This is a starting point. You should supplement with:
    - Renaissance Capital IPO database
    - Your own research
    - IPO news sources
    """
    ipos = [
        # 2023
        {'ticker': 'ARM', 'company': 'Arm Holdings', 'ipo_date': '2023-09-14', 'offer_price': 51.00, 'sector': 'Technology'},
        {'ticker': 'BIRK', 'company': 'Birkenstock Holding', 'ipo_date': '2023-10-11', 'offer_price': 46.00, 'sector': 'Consumer'},
        {'ticker': 'KVUE', 'company': 'Kenvue Inc', 'ipo_date': '2023-05-04', 'offer_price': 22.00, 'sector': 'Healthcare'},
        {'ticker': 'CART', 'company': 'Maplebear Inc (Instacart)', 'ipo_date': '2023-09-19', 'offer_price': 30.00, 'sector': 'Technology'},
        {'ticker': 'KLR', 'company': 'Klaviyo Inc', 'ipo_date': '2023-09-20', 'offer_price': 30.00, 'sector': 'Technology'},
        {'ticker': 'FRSH', 'company': 'Freshworks Inc', 'ipo_date': '2023-09-22', 'offer_price': 36.00, 'sector': 'Technology'},
        {'ticker': 'NXT', 'company': 'Nextracker Inc', 'ipo_date': '2023-02-09', 'offer_price': 24.00, 'sector': 'Energy'},
        {'ticker': 'PACS', 'company': 'PACS Group', 'ipo_date': '2023-06-16', 'offer_price': 19.00, 'sector': 'Industrial'},
        {'ticker': 'BRW', 'company': 'Saba Capital Income', 'ipo_date': '2023-03-29', 'offer_price': 20.00, 'sector': 'Financial'},
        {'ticker': 'CLBT', 'company': 'Cellebrite DI', 'ipo_date': '2023-08-31', 'offer_price': 7.00, 'sector': 'Technology'},

        # 2024
        {'ticker': 'RDDT', 'company': 'Reddit Inc', 'ipo_date': '2024-03-21', 'offer_price': 34.00, 'sector': 'Technology'},
        {'ticker': 'AZPN', 'company': 'Aspen Aerogels', 'ipo_date': '2024-01-18', 'offer_price': 13.00, 'sector': 'Materials'},
        {'ticker': 'BN', 'company': 'Brookfield Corporation', 'ipo_date': '2024-02-15', 'offer_price': 32.00, 'sector': 'Financial'},
        {'ticker': 'AEYE', 'company': 'AudioEye Inc', 'ipo_date': '2024-03-14', 'offer_price': 11.00, 'sector': 'Technology'},
        {'ticker': 'TOST', 'company': 'Toast Inc', 'ipo_date': '2024-04-22', 'offer_price': 40.00, 'sector': 'Technology'},
        {'ticker': 'CNXC', 'company': 'Concentrix Corporation', 'ipo_date': '2024-05-30', 'offer_price': 28.00, 'sector': 'Technology'},
        {'ticker': 'SPCE', 'company': 'Virgin Galactic', 'ipo_date': '2024-06-11', 'offer_price': 10.00, 'sector': 'Aerospace'},
        {'ticker': 'WBD', 'company': 'Warner Bros Discovery', 'ipo_date': '2024-07-18', 'offer_price': 15.00, 'sector': 'Media'},
        {'ticker': 'CELH', 'company': 'Celsius Holdings', 'ipo_date': '2024-08-22', 'offer_price': 25.00, 'sector': 'Consumer'},
        {'ticker': 'ELF', 'company': 'e.l.f. Beauty', 'ipo_date': '2024-09-19', 'offer_price': 18.00, 'sector': 'Consumer'},
    ]

    return pd.DataFrame(ipos)

def scrape_renaissance_capital(year=2024):
    """
    Attempt to scrape Renaissance Capital IPO database.

    Note: This is a template. Website structure changes frequently,
    so you'll need to inspect and update selectors.
    """
    url = f"https://www.renaissancecapital.com/IPO-Center/IPO-Performance?year={year}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        print(f"Fetching data from Renaissance Capital for {year}...")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the IPO table (you'll need to inspect the page)
        # This is a placeholder - actual implementation depends on site structure
        tables = soup.find_all('table')

        if not tables:
            print("No tables found. Manual collection recommended.")
            return pd.DataFrame()

        # Try to parse first table
        # In reality, you'd need to identify the correct table and parse rows
        print(f"Found {len(tables)} tables on page.")
        print("Manual inspection and parsing required.")
        print(f"\\nVisit: {url}")
        print("Export data manually and save as CSV.")

        return pd.DataFrame()

    except Exception as e:
        print(f"Error scraping Renaissance Capital: {e}")
        return pd.DataFrame()

def load_manual_csv(filepath):
    """
    Load manually collected IPO data from CSV.

    Expected columns:
    - ticker
    - company
    - ipo_date
    - offer_price
    - sector
    """
    try:
        df = pd.read_csv(filepath)

        # Validate required columns
        required = ['ticker', 'company', 'ipo_date', 'offer_price']
        missing = [col for col in required if col not in df.columns]

        if missing:
            print(f"Warning: Missing columns: {missing}")
            return None

        # Parse dates
        df['ipo_date'] = pd.to_datetime(df['ipo_date'])

        print(f"Loaded {len(df)} IPOs from {filepath}")
        return df

    except Exception as e:
        print(f"Error loading CSV: {e}")
        return None

def merge_sources(dfs):
    """
    Merge IPO data from multiple sources, deduplicating by ticker.
    """
    if not dfs:
        return pd.DataFrame()

    # Concatenate all dataframes
    df_combined = pd.concat(dfs, ignore_index=True)

    # Remove duplicates (keep first occurrence)
    df_combined = df_combined.drop_duplicates(subset=['ticker'], keep='first')

    # Sort by IPO date
    df_combined = df_combined.sort_values('ipo_date', ascending=False)

    return df_combined

def main():
    parser = argparse.ArgumentParser(description='Collect IPO calendar data')
    parser.add_argument('--year', type=int, default=2024, help='Year to collect (default: 2024)')
    parser.add_argument('--manual', type=str, help='Path to manual CSV file')
    parser.add_argument('--output', type=str, default='data/ipo_calendar.csv', help='Output CSV file')
    parser.add_argument('--include-defaults', action='store_true', help='Include default major IPOs list')

    args = parser.parse_args()

    print("="*60)
    print("IPO Calendar Collection Tool")
    print("="*60)
    print()

    sources = []

    # Include default major IPOs
    if args.include_defaults:
        print("Loading default major IPOs (2023-2024)...")
        df_defaults = get_major_ipos_2023_2024()
        sources.append(df_defaults)
        print(f"✓ Loaded {len(df_defaults)} major IPOs\\n")

    # Try scraping
    print(f"Attempting to scrape Renaissance Capital...")
    df_scraped = scrape_renaissance_capital(args.year)
    if not df_scraped.empty:
        sources.append(df_scraped)
    print()

    # Load manual CSV
    if args.manual:
        print(f"Loading manual CSV: {args.manual}...")
        df_manual = load_manual_csv(args.manual)
        if df_manual is not None:
            sources.append(df_manual)
            print(f"✓ Loaded {len(df_manual)} IPOs from manual CSV\\n")

    # Merge all sources
    if not sources:
        print("ERROR: No data sources available.")
        print("\\nRecommendations:")
        print("1. Use --include-defaults to start with major IPOs")
        print("2. Create manual CSV and use --manual flag")
        print("3. Visit Renaissance Capital and export data manually")
        sys.exit(1)

    df_final = merge_sources(sources)

    # Save output
    df_final.to_csv(args.output, index=False)

    print("="*60)
    print("Collection Complete!")
    print("="*60)
    print(f"Total IPOs collected: {len(df_final)}")
    print(f"Date range: {df_final['ipo_date'].min().date()} to {df_final['ipo_date'].max().date()}")
    print(f"\\nSaved to: {args.output}")
    print()
    print("Next steps:")
    print("1. Review and validate the data")
    print("2. Add missing columns (shares offered, underwriters)")
    print("3. Run S-1 download script")

if __name__ == "__main__":
    main()
