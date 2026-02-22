"""
Test DexScreener Volume Data
Shows what volume information is available
"""

import requests
import json

# Fetch a sample pool
url = "https://api.dexscreener.com/latest/dex/search?q=pancakeswap"
response = requests.get(url, timeout=10)

if response.status_code == 200:
    data = response.json()
    
    if 'pairs' in data and len(data['pairs']) > 0:
        # Get first BSC pool
        bsc_pools = [p for p in data['pairs'] if p.get('chainId') == 'bsc']
        
        if bsc_pools:
            pool = bsc_pools[0]
            
            print("="*80)
            print("DEXSCREENER VOLUME DATA STRUCTURE")
            print("="*80)
            
            print(f"\nToken Pair: {pool.get('baseToken', {}).get('symbol')}/{pool.get('quoteToken', {}).get('symbol')}")
            print(f"DEX: {pool.get('dexId')}")
            print(f"Chain: {pool.get('chainId')}")
            
            print("\n" + "="*80)
            print("VOLUME FIELDS")
            print("="*80)
            
            volume = pool.get('volume', {})
            print(f"\nRaw volume object:")
            print(json.dumps(volume, indent=2))
            
            print("\n" + "-"*80)
            print("VOLUME BREAKDOWN:")
            print("-"*80)
            
            # Different timeframes
            if 'm5' in volume:
                print(f"  5-minute volume:  ${float(volume['m5']):,.2f}")
            if 'h1' in volume:
                print(f"  1-hour volume:    ${float(volume['h1']):,.2f}")
            if 'h6' in volume:
                print(f"  6-hour volume:    ${float(volume['h6']):,.2f}")
            if 'h24' in volume:
                print(f"  24-hour volume:   ${float(volume['h24']):,.2f}")
            
            print("\n" + "="*80)
            print("LIQUIDITY DATA")
            print("="*80)
            
            liquidity = pool.get('liquidity', {})
            print(f"\nRaw liquidity object:")
            print(json.dumps(liquidity, indent=2))
            
            if 'usd' in liquidity:
                liq_usd = float(liquidity['usd'])
                vol_24h = float(volume.get('h24', 0))
                
                print("\n" + "-"*80)
                print("VOLUME RATIOS (Important for analysis):")
                print("-"*80)
                
                if liq_usd > 0:
                    vol_liq_ratio = (vol_24h / liq_usd) * 100
                    print(f"  Volume/Liquidity Ratio: {vol_liq_ratio:.2f}%")
                    print(f"  (24h volume as % of total liquidity)")
                    
                    if vol_liq_ratio > 100:
                        print(f"  → 🔥 HIGH ACTIVITY (volume > liquidity)")
                    elif vol_liq_ratio > 50:
                        print(f"  → ✅ GOOD ACTIVITY (healthy turnover)")
                    elif vol_liq_ratio > 10:
                        print(f"  → ⚠️  MODERATE (some activity)")
                    else:
                        print(f"  → ❌ LOW (illiquid/inactive)")
            
            print("\n" + "="*80)
            print("TRANSACTION COUNTS")
            print("="*80)
            
            txns = pool.get('txns', {})
            print(f"\nRaw txns object:")
            print(json.dumps(txns, indent=2))
            
            if 'h24' in txns:
                h24 = txns['h24']
                buys = h24.get('buys', 0)
                sells = h24.get('sells', 0)
                total = buys + sells
                
                print("\n24-hour Transaction Breakdown:")
                print(f"  Buys:  {buys}")
                print(f"  Sells: {sells}")
                print(f"  Total: {total}")
                
                if total > 0:
                    buy_pressure = (buys / total) * 100
                    print(f"  Buy Pressure: {buy_pressure:.1f}%")
                    
                    if buy_pressure > 60:
                        print(f"  → 🚀 BULLISH (more buyers)")
                    elif buy_pressure < 40:
                        print(f"  → 📉 BEARISH (more sellers)")
                    else:
                        print(f"  → ⚖️  NEUTRAL (balanced)")
            
            print("\n" + "="*80)
            print("WHAT VOLUME TELLS US")
            print("="*80)
            
            print("""
Volume is the total USD value traded in a time period.

Key Insights:

1. ABSOLUTE VOLUME
   • High volume (>$100k/24h) = active trading
   • Low volume (<$10k/24h) = illiquid, risky
   
2. VOLUME/LIQUIDITY RATIO
   • >100% = Very active (volume exceeds pool size)
   • 50-100% = Healthy activity
   • <10% = Dead/illiquid
   
3. VOLUME CONSISTENCY
   • m5, h1, h6, h24 tell you if volume is:
     - Spiking (high m5, low h24) = pump happening NOW
     - Sustained (high across all timeframes) = genuine interest
     - Declining (low recent, high h24) = losing momentum
     
4. TRANSACTION COUNT
   • Many txns + high volume = real activity
   • Few txns + high volume = whale movements/wash trading
   
5. BUY/SELL RATIO
   • More buys = bullish sentiment
   • More sells = bearish/distribution
            """)
            
            print("\n" + "="*80)
            
        else:
            print("No BSC pools found")
    else:
        print("No pairs found")
else:
    print(f"API error: {response.status_code}")

