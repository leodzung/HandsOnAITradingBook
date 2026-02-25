# Polymarket Markets - Manual Review

**Generated**: 2026-02-13
**Total Active Markets**: 54
**All have CLOB orderbooks**: ✅

## Summary Statistics

- **Average orderbook depth**: 20 bids, 41 asks
- **Average estimated slippage**: ~5,907 bps (59%)
- **Slippage range**: 1,000 - 10,000 bps (10% - 100%)

### By Asset
- **BTC**: 26 markets, avg ~5,731 bps (57%)
- **ETH**: 14 markets, avg ~5,857 bps (59%)
- **GOLD**: 14 markets, avg ~6,286 bps (63%)

---

## Markets by Estimated Slippage

### 🟢 Low Slippage (~1,000 bps / 10%)
*These have deep orderbooks (30+ levels on each side)*

1. **BTC $100k** - [Link](https://polymarket.com/event/will-bitcoin-reach-100000-by-december-31-2026-571?tid=0xdaa4866bae18be58c5a79d2aeeffd035ec78f1bb49dbd88f72993997778a990f)
   YES=$0.395, Volume=$639k, Liquidity=$100k, 35 bids / 59 asks

2. **BTC $15k** - [Link](https://polymarket.com/event/will-bitcoin-dip-to-15000-by-december-31-2026-416-954-417-853-885-363-335-458-585-275-615-269-479-379-516-218-918?tid=0xa885bfe10688056a9d0f4e9a1523bfa18f66fda065f0400d714ba54776083713)
   YES=$0.070, Volume=$3.2M, Liquidity=$64k, 57 bids / 59 asks

3. **BTC $10k** - [Link](https://polymarket.com/event/will-bitcoin-dip-to-10000-by-december-31-2026-888-644-567-258?tid=0xd8a5843555ba95455a28d895660c07c59b615184bf4ae64893992f3504797d29)
   YES=$0.052, Volume=$32k, Liquidity=$24k, 33 bids / 43 asks

4. **BTC $250k** - [Link](https://polymarket.com/event/will-bitcoin-reach-250000-by-december-31-2026?tid=0x6fefc0438c7598b23531457c8c60541990d0786bd4bd9dfc3eabc8d95c291092)
   YES=$0.049, Volume=$2.1M, Liquidity=$59k, 42 bids / 44 asks

5. **ETH $1k dip** - [Link](https://polymarket.com/event/will-ethereum-dip-to-1000-by-december-31-2026?tid=0xacb33346b59a2a3770e2391b7d1b0e77d8dcdcf840a66f5fa01d28db43c4e369)
   YES=$0.355, Volume=$158k, Liquidity=$27k, 33 bids / 33 asks

6. **ETH $10k** - [Link](https://polymarket.com/event/will-ethereum-reach-10000-by-december-31-2026?tid=0x201f51d2d892c41c5bfa6568a0a2f93ab2ea426e87dddfd5fb0191f7ec34a441)
   YES=$0.039, Volume=$205k, Liquidity=$115k, 34 bids / 51 asks

7. **GOLD $4,600** - [Link](https://polymarket.com/event/will-gold-gc-hit-low-4600-by-end-of-february-292-259-212-256-398-758-656-625?tid=0x98b461ee7a734c81f23cc00ac927071addd20ea324897dc7becf5cb6183ec8b9)
   YES=$0.206, Volume=$209k, Liquidity=$9k, 48 bids / 45 asks

8. **GOLD $5,500** - [Link](https://polymarket.com/event/will-gold-gc-hit-high-5500-by-end-of-february-743-796-985-593-523-417-437?tid=0xd7e6e54bf46892aec7f865e84d7695e3b1d7686302bf28ccc0be5847e85a65ee)
   YES=$0.134, Volume=$726k, Liquidity=$65k, 45 bids / 72 asks

9. **GOLD $5,800** - [Link](https://polymarket.com/event/will-gold-gc-hit-high-5800-by-end-of-february-759-378-429-713-662-579?tid=0x9bd1851cfe883d474d125e12ce69eca3eecb700f4ce3f942880fe61047ec154d)
   YES=$0.047, Volume=$300k, Liquidity=$23k, 34 bids / 52 asks

---

### 🟡 Moderate Slippage (~5,000 bps / 50%)
*Orderbooks with 10-30 levels, moderate liquidity*

**BTC Markets (17)**
- $75k, $55k dip, $80k, $50k dip, $90k, $45k dip, $40k dip
- $110k, $120k, $35k dip, $30k dip, $130k, $140k, $25k dip, $5k dip

**ETH Markets (9)**
- $1.5k dip, $3.5k, $800 dip, $4k, $4.5k, $5k, $5.5k, $6k, $7.5k

**GOLD Markets (9)**
- $4,450, $4,200, $6,000, $4,000, $6,200

---

### 🔴 High Slippage (~10,000 bps / 100%)
*Thin orderbooks (<10 levels), highest slippage*

**BTC Markets (6)**
- $160k, $150k, $20k dip, $170k, $180k, $190k, $200k

**ETH Markets (4)**
- $6.5k, $7k, $8k

**GOLD Markets (4)**
- $6,400, $3,600, $6,600, $7,000, $3,000, $10,000

---

## Recommended Slippage Limits

Based on your risk tolerance:

### Conservative (9 low-slippage markets)
```json
"max_slippage_bps": 1500
```
**Opens**: BTC $100k, $15k, $10k, $250k, ETH $1k, $10k, GOLD $4.6k, $5.5k, $5.8k

### Moderate (35 markets)
```json
"max_slippage_bps": 6000
```
**Opens**: All low + moderate slippage markets

### Aggressive (all 54 markets)
```json
"max_slippage_bps": 12000
```
**Opens**: All available markets

---

## How to Use This Review

1. **Click links** to review markets on Polymarket
2. **Check orderbooks** to verify liquidity
3. **Decide slippage tolerance** based on your risk preferences
4. **Update config** with chosen `max_slippage_bps` value

---

*Note: Slippage estimates are conservative and include safety buffers. Actual execution may be better.*
