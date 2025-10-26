"""
SEC EDGAR S-1 Filing Downloader

Usage:
    python download_s1_filings.py --input data/ipo_calendar.csv --output data/s1_filings/

Downloads S-1 filings from SEC EDGAR for a list of tickers.

Requirements:
    - requests
    - beautifulsoup4
    - pandas

Important: SEC requires you to identify yourself in the User-Agent header.
Update the email address before running.
"""

import argparse
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import os
from pathlib import Path

# IMPORTANT: Replace with your information
USER_AGENT = "YourCompany your.email@example.com"

def get_cik_from_ticker(ticker):
    """
    Get CIK (Central Index Key) number from ticker symbol.

    SEC uses CIK instead of tickers internally.
    """
    url = f"https://www.sec.gov/cgi-bin/browse-edgar?company={ticker}&action=getcompany"

    headers = {'User-Agent': USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        time.sleep(0.1)  # Rate limiting

        soup = BeautifulSoup(response.content, 'html.parser')

        # Look for CIK in page
        cik_element = soup.find('span', {'class': 'companyName'})

        if cik_element:
            # Extract CIK from text like "COMPANY NAME CIK#: 0001234567"
            text = cik_element.get_text()
            if 'CIK' in text:
                cik = text.split('CIK#:')[1].split()[0]
                return cik.strip()

        return None

    except Exception as e:
        print(f"Error getting CIK for {ticker}: {e}")
        return None

def find_s1_filing_url(ticker, cik=None):
    """
    Find the URL for the S-1 filing document.

    Returns the URL of the HTML document, not the cover page.
    """
    # Get CIK if not provided
    if not cik:
        cik = get_cik_from_ticker(ticker)
        if not cik:
            return None

    # Search for S-1 filings
    search_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=S-1&dateb=&owner=exclude&count=10"

    headers = {'User-Agent': USER_AGENT}

    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        time.sleep(0.2)

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the documents table
        doc_table = soup.find('table', {'class': 'tableFile2'})

        if not doc_table:
            return None

        # Get first row (most recent S-1)
        rows = doc_table.find_all('tr')[1:]  # Skip header

        if not rows:
            return None

        # Find documents link
        first_row = rows[0]
        docs_button = first_row.find('a', {'id': 'documentsbutton'})

        if not docs_button:
            return None

        # Go to documents page
        docs_url = 'https://www.sec.gov' + docs_button['href']

        # Get document list
        response = requests.get(docs_url, headers=headers, timeout=10)
        time.sleep(0.2)

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find main S-1 document (usually first .htm file)
        doc_table = soup.find('table', {'class': 'tableFile'})

        if not doc_table:
            return None

        for row in doc_table.find_all('tr')[1:]:
            cols = row.find_all('td')

            if len(cols) >= 3:
                doc_type = cols[3].get_text().strip()

                # Look for main S-1 document
                if 'S-1' in doc_type or 'S-1/A' in doc_type:
                    doc_link = cols[2].find('a')

                    if doc_link:
                        return 'https://www.sec.gov' + doc_link['href']

        return None

    except Exception as e:
        print(f"Error finding S-1 for {ticker}: {e}")
        return None

def download_s1_filing(ticker, output_dir, cik=None):
    """
    Download S-1 filing and save as HTML file.

    Returns:
        Path to downloaded file or None if failed
    """
    # Find S-1 URL
    url = find_s1_filing_url(ticker, cik)

    if not url:
        return None

    headers = {'User-Agent': USER_AGENT}

    try:
        # Download file
        response = requests.get(url, headers=headers, timeout=30)
        time.sleep(0.3)  # Be polite

        # Save to file
        filepath = os.path.join(output_dir, f"{ticker}_s1.html")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(response.text)

        return filepath

    except Exception as e:
        print(f"Error downloading {ticker}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Download S-1 filings from SEC EDGAR')
    parser.add_argument('--input', type=str, required=True, help='Input CSV with ticker column')
    parser.add_argument('--output', type=str, default='data/s1_filings/', help='Output directory')
    parser.add_argument('--limit', type=int, help='Limit number to download (for testing)')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests (seconds)')

    args = parser.parse_args()

    # Check User-Agent
    if "your.email@example.com" in USER_AGENT:
        print("ERROR: Please update USER_AGENT with your email address!")
        print("SEC requires identification in User-Agent header.")
        print("Edit line 24 of this script.")
        return

    # Load IPO list
    print(f"Loading IPO list from {args.input}...")
    df = pd.read_csv(args.input)

    if 'ticker' not in df.columns:
        print("ERROR: Input CSV must have 'ticker' column")
        return

    tickers = df['ticker'].tolist()

    if args.limit:
        tickers = tickers[:args.limit]

    print(f"Found {len(tickers)} tickers to process")
    print()

    # Create output directory
    os.makedirs(args.output, exist_ok=True)

    # Download each filing
    results = []

    print("="*60)
    print("Starting downloads...")
    print("="*60)
    print()

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {ticker:6s} ... ", end='', flush=True)

        # Check if already downloaded
        existing = os.path.join(args.output, f"{ticker}_s1.html")
        if os.path.exists(existing):
            print("✓ Already exists (skipping)")
            results.append({'ticker': ticker, 'success': True, 'path': existing})
            continue

        # Download
        filepath = download_s1_filing(ticker, args.output)

        if filepath:
            print(f"✓ Downloaded")
            results.append({'ticker': ticker, 'success': True, 'path': filepath})
        else:
            print(f"✗ Failed")
            results.append({'ticker': ticker, 'success': False, 'path': None})

        # Rate limiting
        time.sleep(args.delay)

    # Summary
    df_results = pd.DataFrame(results)
    success_rate = df_results['success'].mean()

    print()
    print("="*60)
    print("Download Complete!")
    print("="*60)
    print(f"Success rate: {success_rate:.1%}")
    print(f"Downloaded: {df_results['success'].sum()}/{len(df_results)}")
    print(f"Failed: {(~df_results['success']).sum()}/{len(df_results)}")
    print()
    print(f"Files saved to: {args.output}")

    # Save results log
    results_file = os.path.join(args.output, '_download_log.csv')
    df_results.to_csv(results_file, index=False)
    print(f"Download log: {results_file}")

    # Show failed tickers
    failed = df_results[~df_results['success']]['ticker'].tolist()
    if failed:
        print()
        print("Failed tickers (check manually):")
        for ticker in failed:
            print(f"  - {ticker}: https://www.sec.gov/cgi-bin/browse-edgar?company={ticker}&type=S-1")

if __name__ == "__main__":
    main()
