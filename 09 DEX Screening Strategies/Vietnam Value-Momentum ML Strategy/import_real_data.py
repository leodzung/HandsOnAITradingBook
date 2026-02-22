"""
Import Real Q4 2025 Fundamental Data from CSV
"""

import pandas as pd

# Read the CSV with real data
df = pd.read_csv('fundamental_data_template.csv')

# Clean the data - remove % signs and convert to float
df['roe'] = df['roe'].str.rstrip('%').astype(float)
df['roa'] = df['roa'].str.rstrip('%').astype(float)

# Convert to the format needed for fundamental_screener.py
print("=" * 70)
print("Q4 2025 REAL FUNDAMENTAL DATA (Updated November 17, 2025)")
print("=" * 70)
print(f"\nImported {len(df)} stocks with real data from SSI\n")

# Generate Python code for manual_data list
print("# Copy this into fundamental_screener.py create_manual_fundamental_data():")
print("\nmanual_data = [")

for _, row in df.iterrows():
    print(f"    {{'symbol': '{row['symbol']}', 'pe_ratio': {row['pe_ratio']}, 'pb_ratio': {row['pb_ratio']}, 'roe': {row['roe']}, 'roa': {row['roa']}, 'sector': '{row['sector']}'}},")

print("]")

print("\n" + "=" * 70)
print("QUICK ANALYSIS OF Q4 2025 DATA")
print("=" * 70)

# Display summary
print(f"\n📊 Data Summary:")
print(f"   Stocks analyzed: {len(df)}")
print(f"   Data date: {df['data_date'].iloc[0]}")
print(f"   Source: {df['source'].iloc[0]}")

print(f"\n🏆 Top 5 by Low P/E (Best Value):")
top_pe = df.nsmallest(5, 'pe_ratio')[['symbol', 'pe_ratio', 'pb_ratio', 'roe', 'sector']]
print(top_pe.to_string(index=False))

print(f"\n🏆 Top 5 by High ROE (Best Profitability):")
top_roe = df.nlargest(5, 'roe')[['symbol', 'pe_ratio', 'pb_ratio', 'roe', 'sector']]
print(top_roe.to_string(index=False))

print(f"\n💎 Deep Value Stocks (P/E < 10, P/B < 1.7):")
deep_value = df[(df['pe_ratio'] < 10) & (df['pb_ratio'] < 1.7)]
if len(deep_value) > 0:
    print(deep_value[['symbol', 'pe_ratio', 'pb_ratio', 'roe', 'sector']].to_string(index=False))
else:
    print("   None found in current dataset")

print(f"\n⭐ Quality Value (P/E < 15, ROE > 18%):")
quality = df[(df['pe_ratio'] < 15) & (df['roe'] > 18)]
if len(quality) > 0:
    print(quality[['symbol', 'pe_ratio', 'pb_ratio', 'roe', 'sector']].to_string(index=False))
else:
    print("   None found")

# Calculate value score
df['pe_rank'] = df['pe_ratio'].rank(ascending=True)
df['pb_rank'] = df['pb_ratio'].rank(ascending=True)
df['roe_rank'] = df['roe'].rank(ascending=False)
df['value_score'] = df['pe_rank'] + df['pb_rank'] + df['roe_rank']
df = df.sort_values('value_score', ascending=False)

print(f"\n🎯 Top 10 by Combined Value Score (Q4 2025):")
print(df.head(10)[['symbol', 'pe_ratio', 'pb_ratio', 'roe', 'sector']].to_string(index=False))

print("\n" + "=" * 70)
print("✅ Data ready to import into fundamental_screener.py")
print("=" * 70)
