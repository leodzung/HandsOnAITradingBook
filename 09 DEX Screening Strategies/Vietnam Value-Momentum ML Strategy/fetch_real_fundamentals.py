"""
Fetch Real Fundamental Data from Vietnamese Stock Sources (Q3/Q4 2025)

Data sources:
1. VietStock API (primary)
2. SSI API (backup)
3. Fallback to web scraping if APIs fail
"""

import requests
import json
import pandas as pd
import time
from datetime import datetime

def fetch_vietstock_data(symbol):
    """Fetch fundamental data from VietStock."""
    try:
        # VietStock API endpoint
        url = f"https://finance.vietstock.vn/data/financeinfo"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': f'https://finance.vietstock.vn/{symbol}/tai-chinh.htm'
        }
        
        params = {
            'code': symbol,
            'type': 'BCTT'  # Balance sheet
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return None
            
    except Exception as e:
        print(f"VietStock error for {symbol}: {str(e)[:50]}")
        return None


def fetch_ssi_data(symbol):
    """Fetch fundamental data from SSI."""
    try:
        # SSI iBoard API  
        url = f"https://iboard.ssi.com.vn/dchart/api/1.1/Stock/{symbol}/Overview"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Origin': 'https://iboard.ssi.com.vn',
            'Referer': f'https://iboard.ssi.com.vn/bang-gia/vn30/{symbol}'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return None
            
    except Exception as e:
        print(f"SSI error for {symbol}: {str(e)[:50]}")
        return None


def extract_fundamentals(symbol):
    """
    Extract P/E, P/B, ROE from various sources.
    Returns dict with fundamental metrics.
    """
    
    # Try VietStock first
    data = fetch_vietstock_data(symbol)
    if data:
        try:
            # Parse VietStock response
            # (Structure varies, adapt as needed)
            return parse_vietstock_response(symbol, data)
        except:
            pass
    
    # Try SSI as backup
    data = fetch_ssi_data(symbol)
    if data:
        try:
            return parse_ssi_response(symbol, data)
        except:
            pass
    
    return None


def parse_vietstock_response(symbol, data):
    """Parse VietStock JSON response."""
    # This is placeholder - actual structure depends on API response
    fundamentals = {
        'symbol': symbol,
        'pe_ratio': None,
        'pb_ratio': None,
        'roe': None,
        'roa': None,
        'source': 'VietStock'
    }
    
    # Add parsing logic when we see actual response structure
    return fundamentals


def parse_ssi_response(symbol, data):
    """Parse SSI JSON response."""
    fundamentals = {
        'symbol': symbol,
        'pe_ratio': data.get('pe'),
        'pb_ratio': data.get('pb'),
        'roe': data.get('roe'),
        'roa': data.get('roa'),
        'source': 'SSI'
    }
    
    return fundamentals


def fetch_all_stocks(symbols):
    """Fetch fundamental data for all stocks."""
    
    print("=" * 70)
    print("FETCHING REAL FUNDAMENTAL DATA (Q3/Q4 2025)")
    print("=" * 70)
    print(f"\nFetching data for {len(symbols)} stocks...")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = []
    failed = []
    
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] Fetching {symbol}...", end=" ", flush=True)
        
        data = extract_fundamentals(symbol)
        
        if data and (data['pe_ratio'] or data['pb_ratio'] or data['roe']):
            results.append(data)
            print(f"✅ (P/E: {data.get('pe_ratio', 'N/A')})")
        else:
            failed.append(symbol)
            print("❌")
        
        # Rate limiting
        time.sleep(0.5)
    
    print(f"\n✅ Successfully fetched: {len(results)}/{len(symbols)} stocks")
    print(f"❌ Failed: {len(failed)} stocks")
    
    if failed:
        print(f"   Failed symbols: {', '.join(failed[:10])}{('...' if len(failed) > 10 else '')}")
    
    return pd.DataFrame(results) if results else None


if __name__ == '__main__':
    """Test fetching data for a few stocks."""
    
    # Test with a small sample first
    test_symbols = ['VCB', 'BID', 'VNM', 'HPG', 'FPT']
    
    print("\n🧪 Testing with sample stocks first...")
    df = fetch_all_stocks(test_symbols)
    
    if df is not None and len(df) > 0:
        print("\n" + "=" * 70)
        print("SAMPLE RESULTS")
        print("=" * 70)
        print(df.to_string(index=False))
        
        print("\n✅ API working! Ready to fetch full universe.")
        print("\nTo fetch all 78 stocks, update the symbols list and re-run.")
    else:
        print("\n❌ APIs not accessible. You may need to:")
        print("   1. Check if websites require login/API key")
        print("   2. Use browser developer tools to find actual API endpoints")
        print("   3. Manually download data from SSI iBoard or VietStock website")
        print("\n📌 Manual alternative:")
        print("   - Go to https://iboard.ssi.com.vn/")
        print("   - Search each stock and note P/E, P/B, ROE")
        print("   - Update fundamental_screener.py manual_data section")
