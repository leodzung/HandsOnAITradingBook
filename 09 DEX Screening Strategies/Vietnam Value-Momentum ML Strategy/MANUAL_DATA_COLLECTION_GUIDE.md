# 📊 Manual Data Collection Guide for Q3/Q4 2025

**Date**: November 2025
**Purpose**: Get current fundamental data for Vietnamese stocks
**Status**: Automated APIs blocked, manual collection required

---

## 🎯 Quick Summary

We need to collect **Q3 2025 fundamental ratios** for Vietnamese stocks:
- **P/E Ratio** (Price to Earnings)
- **P/B Ratio** (Price to Book)
- **ROE** (Return on Equity)
- **ROA** (Return on Assets) - optional

---

## 📍 Where to Find Current Data

### **Option 1: SSI iBoard** (Recommended - Most Reliable)

**Website**: https://iboard.ssi.com.vn/

**Steps**:
1. Go to https://iboard.ssi.com.vn/
2. In the search box (top right), type stock symbol (e.g., "VCB")
3. Click on the stock to open its page
4. Look for "Chỉ số tài chính" (Financial Ratios) section
5. Note down:
   - P/E (Giá/Thu nhập)
   - P/B (Giá/Sổ sách)
   - ROE (Lợi nhuận/Vốn CSH)
   - ROA (Lợi nhuận/Tài sản)

**Example for VCB**:
- URL: https://iboard.ssi.com.vn/dchart/vn30/VCB
- Find the "Chỉ số cơ bản" (Basic Ratios) panel
- Copy the current values (Q3 2025 or latest available)

---

### **Option 2: VietStock** (Alternative)

**Website**: https://finance.vietstock.vn/

**Steps**:
1. Go to https://finance.vietstock.vn/
2. Search for stock (e.g., "VCB")
3. Click "Tài chính" (Finance) tab
4. Look for "Chỉ số tài chính" section
5. Copy P/E, P/B, ROE values

---

### **Option 3: Company Investor Relations**

For the most accurate data:
1. Go to company website
2. Find "Investor Relations" or "Quan hệ cổ đông" section
3. Download Q3 2025 financial report
4. Calculate ratios manually from financial statements

---

## 🎯 Priority Stocks to Collect (Top 20)

Focus on these high-priority stocks first:

### **Banking** (Top performers):
1. **VCB** (Vietcombank)
2. **TCB** (Techcombank)
3. **MBB** (MB Bank)
4. **BID** (BIDV)
5. **CTG** (VietinBank)

### **Consumer & Pharma** (High ROE):
6. **VNM** (Vinamilk)
7. **SAB** (Sabeco)
8. **DHG** (Hau Giang Pharma)
9. **PNJ** (PNJ Gold)
10. **FPT** (FPT Corp)

### **Materials & Energy**:
11. **HPG** (Hoa Phat)
12. **GAS** (PetroVietnam Gas)
13. **PLX** (Petrolimex)

### **Others**:
14. **MSN** (Masan)
15. **MWG** (Mobile World)
16. **VIC** (Vingroup)
17. **VHM** (Vinhomes)
18. **POW** (PV Power)
19. **SSI** (SSI Securities)
20. **HCM** (HCM Securities)

---

## 📝 Data Collection Template

Use this template to record data:

```
Symbol | P/E | P/B | ROE | ROA | Source | Date
-------|-----|-----|-----|-----|--------|-----
VCB    | ??? | ??? | ??? | ??? | SSI    | 2025-11-12
BID    | ??? | ??? | ??? | ??? | SSI    | 2025-11-12
TCB    | ??? | ??? | ??? | ??? | SSI    | 2025-11-12
...
```

---

## 🔄 How to Update fundamental_screener.py

Once you've collected the data:

1. Open `fundamental_screener.py`
2. Find the `create_manual_fundamental_data()` function
3. Update the `manual_data` list with your collected values

**Example**:
```python
# Banking sector (UPDATE WITH REAL Q3 2025 DATA)
{'symbol': 'VCB', 'pe_ratio': 8.5, 'pb_ratio': 1.8, 'roe': 21.5, 'roa': 1.5, 'sector': 'Banking'},

# Change to (with real data you collected):
{'symbol': 'VCB', 'pe_ratio': 9.2, 'pb_ratio': 1.9, 'roe': 22.3, 'roa': 1.6, 'sector': 'Banking'},
```

---

## ⚡ Quick Start: Collect Top 10 First

Don't collect all 78 stocks at once. Start with top 10:

1. **VCB, BID, TCB** (Banking - likely best value)
2. **VNM, SAB** (Consumer - likely high ROE)
3. **DHG, FPT** (Pharma/Tech - likely high quality)
4. **HPG, GAS** (Materials/Energy - cyclical value)
5. **MSN** (Conglomerate)

With just these 10 stocks, you can already run a meaningful backtest!

---

## 📊 What to Look For

When collecting data, note:

### **Good Value Stocks** (for contrarian/value strategy):
- P/E < 10
- P/B < 1.5
- ROE > 15%

### **Quality Growth Stocks**:
- ROE > 20%
- P/E < 15
- Stable/growing earnings

### **Deep Value Stocks**:
- P/E < 8
- P/B < 1.2
- Any positive ROE

---

## 🛠️ After Collection

Once you've collected data for at least 10-20 stocks:

1. Update `fundamental_screener.py` with real values
2. Run the screener:
   ```bash
   python3 fundamental_screener.py
   ```

3. Review the updated rankings
4. Use top-ranked stocks for your trading strategy

---

## 💡 Tips

1. **Start small**: Collect 10 stocks, test, then expand
2. **Focus on quality**: Better to have 10 accurate values than 78 questionable estimates
3. **Document source**: Note where you got each value (SSI, VietStock, etc.)
4. **Check dates**: Ensure you're using Q3 2025 or most recent data
5. **Verify calculations**: If P/E seems too low/high, double-check

---

## 📌 Alternative: Use Latest Available Data

If Q3 2025 data isn't fully released yet for all stocks:

- Use **Q2 2025** data (released July/August 2025)
- Or **FY 2024 annual** data (released March/April 2025)
- Mark which stocks have which data vintage

**Note**: Mixing data from different quarters is okay for screening purposes, just be aware of the time differences.

---

## ⏱️ Time Estimate

- **10 stocks**: ~30 minutes
- **20 stocks**: ~1 hour
- **50 stocks**: ~2-3 hours
- **78 stocks**: ~4-5 hours

**Recommendation**: Start with 20 key stocks, which gives you enough diversity without spending all day collecting data.

---

## 🎯 Next Steps

1. Spend 1 hour collecting top 20 stocks' data
2. Update `fundamental_screener.py` with real values
3. Re-run screener to get accurate Q3/Q4 2025 rankings
4. Build value-based strategy using real current data

This manual approach ensures you have the most accurate, current fundamental data for Q4 2025 trading decisions!
