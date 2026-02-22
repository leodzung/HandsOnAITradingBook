#!/usr/bin/env python3
"""
Check why PRDT is not appearing in scan results
"""

import requests
import time
from datetime import datetime

# Search for PRDT on DexScreener
print('Searching DexScreener for PRDT...')
print('='*60)

try:
    # Search by token symbol
    url = 'https://api.dexscreener.com/latest/dex/search/?q=PRDT'
    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        data = response.json()
        pairs = data.get('pairs', [])

        if not pairs:
            print('❌ No PRDT pairs found on DexScreener')
        else:
            print(f'✅ Found {len(pairs)} PRDT pair(s):')
            print()

            for i, pair in enumerate(pairs[:5], 1):
                base = pair.get('baseToken', {})
                quote = pair.get('quoteToken', {})

                print(f'{i}. {base.get("symbol")}/{quote.get("symbol")}')
                print(f'   Chain: {pair.get("chainId")}')
                print(f'   DEX: {pair.get("dexId")}')

                liquidity = float(pair.get('liquidity', {}).get('usd', 0))
                volume = float(pair.get('volume', {}).get('h24', 0))

                print(f'   Liquidity: ${liquidity:,.0f}')
                print(f'   Volume 24h: ${volume:,.0f}')

                # Check age
                created_at = pair.get('pairCreatedAt', 0)
                if created_at:
                    created_time = created_at / 1000
                    age_hours = (time.time() - created_time) / 3600
                    age_days = age_hours / 24
                    print(f'   Age: {age_hours:.1f} hours ({age_days:.1f} days)')
                else:
                    age_hours = 999
                    print(f'   Age: Unknown')

                # Check our filter criteria
                print(f'\n   Filter Check:')
                print(f'     Age < 168h (7 days): {"✅ PASS" if age_hours < 168 else "❌ FAIL"}')
                print(f'     Liquidity > $30,000: {"✅ PASS" if liquidity > 30000 else "❌ FAIL"} (${liquidity:,.0f})')
                print(f'     Volume > $5,000: {"✅ PASS" if volume > 5000 else "❌ FAIL"} (${volume:,.0f})')

                if liquidity > 0:
                    vol_liq_ratio = (volume / liquidity) * 100
                    print(f'     Vol/Liq 20-1000%: {"✅ PASS" if 20 <= vol_liq_ratio <= 1000 else "❌ FAIL"} ({vol_liq_ratio:.1f}%)')
                else:
                    print(f'     Vol/Liq 20-1000%: ❌ FAIL (no liquidity)')

                print()

                # Overall verdict
                passes = (
                    age_hours < 168 and
                    liquidity > 30000 and
                    volume > 5000 and
                    liquidity > 0 and
                    20 <= (volume / liquidity) * 100 <= 1000
                )

                if passes:
                    print(f'   ✅ Would PASS initial filters')
                else:
                    print(f'   ❌ BLOCKED by initial filters')
                print()

    else:
        print(f'❌ API Error: {response.status_code}')

except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
