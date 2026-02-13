#!/usr/bin/env python3
"""
Polymarket Trading Dashboard

Real-time monitoring for all trading bots:
- Event Trader
- Price Level Trader
- Arbitrage Bot

Run with: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import sqlite3
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
import plotly.express as px
import plotly.graph_objects as go
import requests

# Page config
st.set_page_config(
    page_title="Polymarket Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
DATA_DIR = Path("data")
POSITIONS_DB = DATA_DIR / "positions_price_level.db"
EVENT_POSITIONS_DB = DATA_DIR / "positions.db"
SHORT_EXPIRY_POSITIONS_DB = DATA_DIR / "positions_short_expiry.db"
PRICE_LEVEL_BALANCE = DATA_DIR / "paper_trading_balance_price_level.json"
EVENT_BALANCE = DATA_DIR / "paper_trading_balance.json"
SHORT_EXPIRY_BALANCE = DATA_DIR / "paper_trading_balance_short_expiry.json"
ARBITRAGE_LOG_DIR = DATA_DIR / "arbitrage"
# Separate databases for collectors (to avoid corruption from concurrent writes)
GDELT_DB = DATA_DIR / "gdelt_news.db"
ALCHEMY_DB = DATA_DIR / "alchemy_trades.db"
# Legacy combined database (deprecated)
TRAINING_DB = DATA_DIR / "training_history.db"


def get_data_collection_stats() -> dict:
    """Get data collection progress stats from separate collector databases."""
    stats = {
        "on_chain_trades": 0,
        "token_mappings": 0,
        "markets": 0,
        "news_events": 0,
        "last_block": 0,
        "last_trade_time": None,
        "target_trades": 50_000_000,  # 50M target for 6 months
    }

    # Read from Alchemy database
    if ALCHEMY_DB.exists():
        try:
            conn = sqlite3.connect(ALCHEMY_DB)
            cursor = conn.cursor()

            # Count on-chain trades
            try:
                cursor.execute("SELECT COUNT(*) FROM on_chain_trades")
                stats["on_chain_trades"] = cursor.fetchone()[0]
            except:
                pass

            # Count token mappings
            try:
                cursor.execute("SELECT COUNT(*) FROM token_condition_map")
                stats["token_mappings"] = cursor.fetchone()[0]
            except:
                pass

            # Count markets
            try:
                cursor.execute("SELECT COUNT(*) FROM markets")
                stats["markets"] = cursor.fetchone()[0]
            except:
                pass

            # Get last block and trade time
            try:
                cursor.execute("SELECT MAX(block_number), MAX(block_timestamp) FROM on_chain_trades")
                row = cursor.fetchone()
                if row:
                    stats["last_block"] = row[0] or 0
                    stats["last_trade_time"] = row[1]
            except:
                pass

            conn.close()
        except Exception as e:
            pass

    # Read from GDELT database
    if GDELT_DB.exists():
        try:
            conn = sqlite3.connect(GDELT_DB)
            cursor = conn.cursor()

            # Count news events
            try:
                cursor.execute("SELECT COUNT(*) FROM news_events")
                stats["news_events"] = cursor.fetchone()[0]
            except:
                pass

            conn.close()
        except Exception as e:
            pass

    return stats


def get_bot_status():
    """Check which bots are running (supports both Docker and direct processes)."""
    status = {"event_trader": False, "price_level": False, "arbitrage": False, "short_expiry": False}

    # First check Docker containers
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}} {{.Status}}"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            output = result.stdout
            # Check for running containers (status contains "Up")
            for line in output.split('\n'):
                if 'polymarket-event-trader' in line and 'Up' in line:
                    status["event_trader"] = True
                if 'polymarket-price-level' in line and 'Up' in line:
                    status["price_level"] = True
                if 'polymarket-arbitrage' in line and 'Up' in line:
                    status["arbitrage"] = True
                if 'polymarket-short-expiry' in line and 'Up' in line:
                    status["short_expiry"] = True
            # If any Docker container found, return Docker status
            if any(status.values()):
                return status
    except:
        pass

    # Fallback to checking direct processes
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True
        )
        output = result.stdout
        # Check each line individually to properly distinguish processes
        for line in output.split('\n'):
            if 'trader.py' in line and 'price_levels' not in line and 'short_expiry' not in line:
                status["event_trader"] = True
            if 'trader_price_levels.py' in line:
                status["price_level"] = True
            if 'trader_short_expiry.py' in line:
                status["short_expiry"] = True
            if 'arbitrage_bot.py' in line:
                status["arbitrage"] = True
    except:
        pass

    return status


def get_collector_status():
    """Check which data collectors are running (Docker or direct process)."""
    status = {
        "gdelt_collector": {"running": False, "pid": None, "docker": False, "docker_status": None},
        "alchemy_collector": {"running": False, "pid": None, "docker": False, "docker_status": None}
    }

    # Check Docker containers first
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}} {{.Status}}"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'polymarket-gdelt-collector' in line:
                    status["gdelt_collector"]["running"] = True
                    status["gdelt_collector"]["docker"] = True
                    status["gdelt_collector"]["docker_status"] = line.split(' ', 1)[1] if ' ' in line else "Running"
                if 'polymarket-alchemy-collector' in line:
                    status["alchemy_collector"]["running"] = True
                    status["alchemy_collector"]["docker"] = True
                    status["alchemy_collector"]["docker_status"] = line.split(' ', 1)[1] if ' ' in line else "Running"
    except:
        pass

    # Fallback to checking direct processes
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True
        )
        output = result.stdout
        for line in output.split('\n'):
            if 'gdelt_collector.py' in line and 'grep' not in line:
                if not status["gdelt_collector"]["running"]:
                    status["gdelt_collector"]["running"] = True
                    parts = line.split()
                    if len(parts) > 1:
                        status["gdelt_collector"]["pid"] = parts[1]
            if 'alchemy_collector.py' in line and 'grep' not in line:
                if not status["alchemy_collector"]["running"]:
                    status["alchemy_collector"]["running"] = True
                    parts = line.split()
                    if len(parts) > 1:
                        status["alchemy_collector"]["pid"] = parts[1]
    except:
        pass

    return status


def get_collector_db_stats():
    """Get detailed stats from the separate collector databases."""
    stats = {
        "gdelt_db_size_mb": 0,
        "gdelt_events": 0,
        "gdelt_files_processed": 0,
        "gdelt_latest_event": None,
        "alchemy_db_size_mb": 0,
        "alchemy_trades": 0,
        "alchemy_last_block": None,
        "alchemy_last_trade": None,
    }

    # GDELT database stats
    if GDELT_DB.exists():
        try:
            stats["gdelt_db_size_mb"] = GDELT_DB.stat().st_size / (1024 * 1024)
            conn = sqlite3.connect(GDELT_DB)
            cursor = conn.cursor()

            try:
                cursor.execute("SELECT COUNT(*) FROM news_events")
                stats["gdelt_events"] = cursor.fetchone()[0]
            except:
                pass

            try:
                cursor.execute("SELECT COUNT(*) FROM gdelt_files_processed")
                stats["gdelt_files_processed"] = cursor.fetchone()[0]
            except:
                pass

            try:
                cursor.execute("SELECT MAX(timestamp) FROM news_events")
                row = cursor.fetchone()
                if row and row[0]:
                    stats["gdelt_latest_event"] = row[0]
            except:
                pass

            conn.close()
        except:
            pass

    # Alchemy database stats
    if ALCHEMY_DB.exists():
        try:
            stats["alchemy_db_size_mb"] = ALCHEMY_DB.stat().st_size / (1024 * 1024)
            conn = sqlite3.connect(ALCHEMY_DB)
            cursor = conn.cursor()

            try:
                cursor.execute("SELECT COUNT(*) FROM on_chain_trades")
                stats["alchemy_trades"] = cursor.fetchone()[0]
            except:
                pass

            try:
                cursor.execute("SELECT MAX(block_number), MAX(block_timestamp) FROM on_chain_trades")
                row = cursor.fetchone()
                if row:
                    stats["alchemy_last_block"] = row[0]
                    stats["alchemy_last_trade"] = row[1]
            except:
                pass

            conn.close()
        except:
            pass

    return stats


def load_balance(balance_file: Path) -> dict:
    """Load paper trading balance."""
    try:
        with open(balance_file, 'r') as f:
            return json.load(f)
    except:
        return {"balance": 0, "last_updated": "N/A"}


def load_positions(db_path: Path) -> pd.DataFrame:
    """Load positions from database."""
    if not db_path.exists():
        return pd.DataFrame()

    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query("SELECT * FROM positions", conn)
        conn.close()

        # Parse metadata
        if 'metadata' in df.columns:
            df['meta'] = df['metadata'].apply(lambda x: json.loads(x) if x else {})
            df['asset'] = df['meta'].apply(lambda x: x.get('asset', 'Unknown'))
            df['question'] = df['meta'].apply(lambda x: x.get('question', '')[:50])
            df['strike'] = df['meta'].apply(lambda x: x.get('strike_price', 0))
            df['slug'] = df['meta'].apply(lambda x: x.get('slug', ''))

        # Create Polymarket URL using parent event slugs (not individual market slugs)
        # Polymarket URL format: /event/{parent_event_slug}
        EVENT_SLUGS = {
            'BTC': 'what-price-will-bitcoin-hit-before-2027',
            'ETH': 'what-price-will-ethereum-hit-before-2027',
        }

        if 'market_id' in df.columns and 'asset' in df.columns:
            def get_polymarket_url(row):
                asset = str(row['asset']) if pd.notna(row['asset']) else ''
                if asset in EVENT_SLUGS:
                    return f"https://polymarket.com/event/{EVENT_SLUGS[asset]}"
                # Fallback to search
                question = str(row['question'])[:40] if 'question' in row and pd.notna(row['question']) else ''
                return f"https://polymarket.com/markets?_q={quote(question)}"

            df['polymarket_url'] = df.apply(get_polymarket_url, axis=1)

        return df
    except Exception as e:
        st.error(f"Error loading positions: {e}")
        return pd.DataFrame()


def load_arbitrage_opportunities() -> pd.DataFrame:
    """Load recent arbitrage opportunities."""
    all_file = ARBITRAGE_LOG_DIR / "all_opportunities.jsonl"
    if not all_file.exists():
        return pd.DataFrame()

    opportunities = []
    try:
        with open(all_file, 'r') as f:
            for line in f:
                try:
                    opportunities.append(json.loads(line))
                except:
                    continue
    except:
        pass

    if not opportunities:
        return pd.DataFrame()

    df = pd.DataFrame(opportunities)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df.sort_values('timestamp', ascending=False)


def format_currency(value):
    """Format value as currency."""
    if pd.isna(value):
        return "N/A"
    return f"${value:,.2f}"


def format_percent(value):
    """Format value as percentage."""
    if pd.isna(value):
        return "N/A"
    return f"{value:.1%}"


@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_current_prices(market_id: str) -> dict:
    """Fetch current YES and NO prices from Polymarket CLOB API."""
    result = {'yes': None, 'no': None}
    try:
        url = f"https://clob.polymarket.com/markets/{market_id}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            tokens = data.get('tokens', [])
            for token in tokens:
                outcome = token.get('outcome', '').lower()
                if outcome in ('yes', 'no'):
                    result[outcome] = float(token.get('price', 0))
        return result
    except:
        return result


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_market_name(market_id: str) -> str:
    """Fetch market name/question from Polymarket CLOB API."""
    try:
        url = f"https://clob.polymarket.com/markets/{market_id}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Try question first, fall back to description
            question = data.get('question', data.get('description', 'Unknown Market'))
            return str(question) if question else 'Unknown Market'
        return 'Unknown Market'
    except:
        return 'Unknown Market'


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_market_info(market_id: str) -> dict:
    """Fetch market info (name and slug) from Polymarket CLOB API."""
    try:
        url = f"https://clob.polymarket.com/markets/{market_id}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                'name': data.get('question', data.get('description', 'Unknown Market')),
                'slug': data.get('market_slug', None)
            }
        return {'name': 'Unknown Market', 'slug': None}
    except:
        return {'name': 'Unknown Market', 'slug': None}


def get_current_price(market_id: str) -> float:
    """Fetch current YES price from Polymarket CLOB API (legacy wrapper)."""
    prices = get_current_prices(market_id)
    return prices.get('yes')


# Sidebar
st.sidebar.title("🎯 Polymarket Bots")

# Polymarket links
st.sidebar.subheader("🌐 Polymarket")
st.sidebar.markdown("""
- [🏠 Home](https://polymarket.com)
- [₿ Crypto Markets](https://polymarket.com/markets?_c=crypto)
- [📊 All Markets](https://polymarket.com/markets)
- [🔥 Trending](https://polymarket.com/markets?_ob=volume_24h)
""")
st.sidebar.divider()

# Bot status
st.sidebar.subheader("Trading Bots")
bot_status = get_bot_status()

# Debug timestamp to verify refresh
from datetime import datetime
st.sidebar.caption(f"Last check: {datetime.now().strftime('%H:%M:%S')}")

for bot_name, is_running in bot_status.items():
    display_name = bot_name.replace("_", " ").title()
    status = "🟢" if is_running else "🔴"
    st.sidebar.write(f"{status} {display_name}")

# Collector status
st.sidebar.subheader("Data Collectors")
collector_status = get_collector_status()

for collector_name, info in collector_status.items():
    display_name = collector_name.replace("_", " ").title()
    status = "🟢" if info["running"] else "🔴"
    st.sidebar.write(f"{status} {display_name}")

# Refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

# Auto-refresh
auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=False)
if auto_refresh:
    st.sidebar.write("Next refresh in 30s...")
    import time
    time.sleep(30)
    st.rerun()

# Main content
st.title("📈 Polymarket Trading Dashboard")

# Summary metrics
col1, col2, col3, col4 = st.columns(4)

# Load data
price_level_balance = load_balance(PRICE_LEVEL_BALANCE)
event_balance = load_balance(EVENT_BALANCE)
short_expiry_balance = load_balance(SHORT_EXPIRY_BALANCE)
price_level_positions = load_positions(POSITIONS_DB)
event_positions = load_positions(EVENT_POSITIONS_DB)
short_expiry_positions = load_positions(SHORT_EXPIRY_POSITIONS_DB)

# Calculate metrics
pl_open = price_level_positions[price_level_positions['status'] == 'OPEN'].copy() if not price_level_positions.empty else pd.DataFrame()
pl_closed = price_level_positions[price_level_positions['status'] == 'CLOSED'].copy() if not price_level_positions.empty else pd.DataFrame()

total_deployed = pl_open['size'].sum() if not pl_open.empty else 0
total_pnl = pl_closed['pnl'].sum() if not pl_closed.empty and 'pnl' in pl_closed.columns else 0
total_portfolio = price_level_balance.get('balance', 0) + total_deployed

with col1:
    st.metric(
        "Portfolio Value",
        format_currency(total_portfolio),
        delta=format_currency(total_pnl) if total_pnl != 0 else None
    )

with col2:
    st.metric(
        "Available Balance",
        format_currency(price_level_balance.get('balance', 0))
    )

with col3:
    st.metric(
        "Deployed Capital",
        format_currency(total_deployed),
        delta=f"{len(pl_open)} positions"
    )

with col4:
    st.metric(
        "Realized P&L",
        format_currency(total_pnl),
        delta=f"{len(pl_closed)} closed" if not pl_closed.empty else None
    )

st.divider()

# Tabs for different views
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Positions", "⚡ Short Expiry", "📈 Performance", "🔄 Arbitrage", "📦 Data Collection", "⚙️ Settings"])

with tab1:
    st.subheader("Open Positions")

    if not pl_open.empty:
        # Display positions with Polymarket links
        st.markdown("*Click 🔗 to view on Polymarket*")

        # Column headers
        hcol1, hcol2, hcol3, hcol4, hcol5, hcol6, hcol7, hcol8 = st.columns([2, 0.6, 0.6, 0.7, 0.7, 0.7, 0.9, 1])
        with hcol1:
            st.markdown("**Market**")
        with hcol2:
            st.markdown("**Asset**")
        with hcol3:
            st.markdown("**Side**")
        with hcol4:
            st.markdown("**Entry**")
        with hcol5:
            st.markdown("**Current**")
        with hcol6:
            st.markdown("**Size**")
        with hcol7:
            st.markdown("**Entry Date**")
        with hcol8:
            st.markdown("**P&L**")

        for idx, row in pl_open.iterrows():
            # Use pre-extracted columns from load_positions()
            question = row.get('question', 'Unknown') if pd.notna(row.get('question')) else 'Unknown'
            question = question[:60] if question else 'Unknown'
            strike = row.get('strike', 0) or 0
            asset = row.get('asset', 'Unknown') if pd.notna(row.get('asset')) else 'Unknown'
            side = 'YES' if row.get('side') in ['BUY', 'YES'] else 'NO'
            entry = row.get('entry_price', 0) or 0
            size = row.get('size', 0) or 0
            market_id = row.get('market_id', '')
            entry_time = row.get('entry_time', '')

            # Format entry date
            if pd.notna(entry_time):
                try:
                    entry_date = pd.to_datetime(entry_time, format='mixed').strftime('%m/%d %H:%M')
                except:
                    entry_date = str(entry_time)[:16] if entry_time else 'N/A'
            else:
                entry_date = 'N/A'

            # Use pre-built URL from load_positions()
            if pd.notna(row.get('polymarket_url')) and row.get('polymarket_url'):
                poly_url = row['polymarket_url']
            else:
                # Fallback: use parent event slug based on asset
                EVENT_SLUGS = {
                    'BTC': 'what-price-will-bitcoin-hit-before-2027',
                    'ETH': 'what-price-will-ethereum-hit-before-2027',
                }
                if asset in EVENT_SLUGS:
                    poly_url = f"https://polymarket.com/event/{EVENT_SLUGS[asset]}"
                else:
                    search_term = quote(str(question)[:30])
                    poly_url = f"https://polymarket.com/markets?_q={search_term}"

            # Fetch current prices (both YES and NO)
            prices = get_current_prices(market_id)
            # Use actual token price based on position side
            if side == "YES":
                current_price = prices.get('yes')
            else:
                current_price = prices.get('no')
                if current_price is None and prices.get('yes') is not None:
                    # Fallback to inferred price only if API doesn't return NO price
                    current_price = 1.0 - prices.get('yes')

            # Calculate unrealized P&L
            # entry_price and current_price are both actual token prices (YES or NO)
            if current_price is not None and entry > 0:
                tokens = size / entry
                payout = tokens * current_price
                unrealized_pnl = payout - size
                pnl_pct = (unrealized_pnl / size) * 100 if size > 0 else 0
            else:
                unrealized_pnl = None
                pnl_pct = None

            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 0.6, 0.6, 0.7, 0.7, 0.7, 0.9, 1])
            with col1:
                st.markdown(f"**{question}** [🔗]({poly_url})")
            with col2:
                st.write(f"{asset}")
            with col3:
                color = "🟢" if side == "YES" else "🔴"
                st.write(f"{color} {side}")
            with col4:
                st.write(f"${entry:.3f}")
            with col5:
                if current_price is not None:
                    st.write(f"${current_price:.3f}")
                else:
                    st.write("N/A")
            with col6:
                st.write(f"${size:.2f}")
            with col7:
                st.write(f"{entry_date}")
            with col8:
                if unrealized_pnl is not None:
                    pnl_color = "🟢" if unrealized_pnl >= 0 else "🔴"
                    st.write(f"{pnl_color} ${unrealized_pnl:+.2f}")

        st.divider()

        # Also show as table for easy copying
        with st.expander("📋 Table View"):
            display_df = pl_open[['question', 'asset', 'side', 'entry_price', 'size', 'strike', 'entry_time']].copy()
            display_df.columns = ['Market', 'Asset', 'Side', 'Entry', 'Size', 'Strike', 'Entry Time']
            display_df['Side'] = display_df['Side'].map({'BUY': 'YES', 'SELL': 'NO', 'YES': 'YES', 'NO': 'NO'})
            display_df['Entry'] = display_df['Entry'].apply(lambda x: f"${x:.3f}")
            display_df['Size'] = display_df['Size'].apply(lambda x: f"${x:.2f}")
            display_df['Strike'] = display_df['Strike'].apply(lambda x: f"${x:,.0f}" if x else "N/A")
            display_df['Entry Time'] = pd.to_datetime(display_df['Entry Time'], format='mixed').dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(display_df, width='stretch', hide_index=True)

        # Exposure by asset
        st.subheader("Exposure by Asset")
        if 'asset' in pl_open.columns:
            exposure = pl_open.groupby('asset')['size'].sum().reset_index()
            exposure.columns = ['Asset', 'Exposure']

            fig = px.pie(exposure, values='Exposure', names='Asset',
                        title='Capital Allocation by Asset')
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No open positions")

    # Closed positions
    st.subheader("Recent Closed Positions")
    if not pl_closed.empty:
        closed_sorted = pl_closed.sort_values('exit_time', ascending=False).head(10)

        # Exit reason emoji mapping
        exit_reason_icons = {
            'stop_loss': '🛑',
            'take_profit': '💰',
            'trailing_stop': '📉',
            'time_exit': '⏰',
            'expiry': '📅',
            'manual': '✋',
            None: '—'
        }

        # Column headers for closed positions
        st.markdown("---")
        hcol1, hcol2, hcol3, hcol4, hcol5, hcol6, hcol7, hcol8 = st.columns([2, 0.6, 0.9, 0.7, 0.9, 0.9, 0.9, 0.5])
        with hcol1:
            st.markdown("**Market**")
        with hcol2:
            st.markdown("**Side**")
        with hcol3:
            st.markdown("**Entry→Exit**")
        with hcol4:
            st.markdown("**Size**")
        with hcol5:
            st.markdown("**Entry Date**")
        with hcol6:
            st.markdown("**Exit Date**")
        with hcol7:
            st.markdown("**P&L**")
        with hcol8:
            st.markdown("**Reason**")

        for idx, row in closed_sorted.iterrows():
            # Use pre-extracted columns from load_positions()
            question = row.get('question', 'Unknown') if pd.notna(row.get('question')) else 'Unknown'
            side = 'YES' if row.get('side') in ['BUY', 'YES'] else 'NO'
            entry = row.get('entry_price', 0) or 0
            exit_p = row.get('exit_price', 0) or 0
            size = row.get('size', 0) or 0
            pnl = row.get('pnl', 0) or 0
            exit_reason = row.get('exit_reason', None)
            entry_time = row.get('entry_time', '')
            exit_time = row.get('exit_time', '')

            # Format dates
            if pd.notna(entry_time):
                try:
                    entry_date = pd.to_datetime(entry_time, format='mixed').strftime('%m/%d %H:%M')
                except:
                    entry_date = str(entry_time)[:16] if entry_time else 'N/A'
            else:
                entry_date = 'N/A'

            if pd.notna(exit_time):
                try:
                    exit_date = pd.to_datetime(exit_time, format='mixed').strftime('%m/%d %H:%M')
                except:
                    exit_date = str(exit_time)[:16] if exit_time else 'N/A'
            else:
                exit_date = 'N/A'

            # Use pre-built URL from load_positions()
            if pd.notna(row.get('polymarket_url')) and row.get('polymarket_url'):
                poly_url = row['polymarket_url']
            else:
                # Fallback: use parent event slug based on asset
                EVENT_SLUGS = {
                    'BTC': 'what-price-will-bitcoin-hit-before-2027',
                    'ETH': 'what-price-will-ethereum-hit-before-2027',
                }
                if asset in EVENT_SLUGS:
                    poly_url = f"https://polymarket.com/event/{EVENT_SLUGS[asset]}"
                else:
                    search_term = quote(str(question)[:30])
                    poly_url = f"https://polymarket.com/markets?_q={search_term}"

            # Color code P&L
            pnl_color = "🟢" if pnl and pnl > 0 else "🔴"

            # Exit reason icon
            exit_icon = exit_reason_icons.get(exit_reason, '—')

            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 0.6, 0.9, 0.7, 0.9, 0.9, 0.9, 0.5])
            with col1:
                st.markdown(f"{question} [🔗]({poly_url})")
            with col2:
                st.write(f"{side}")
            with col3:
                st.write(f"${entry:.2f}→${exit_p:.2f}" if exit_p else f"${entry:.2f}")
            with col4:
                st.write(f"${size:.2f}")
            with col5:
                st.write(f"{entry_date}")
            with col6:
                st.write(f"{exit_date}")
            with col7:
                st.write(f"{pnl_color} ${pnl:+.2f}" if pnl else "N/A")
            with col8:
                st.write(f"{exit_icon}")
    else:
        st.info("No closed positions")

with tab2:
    st.subheader("⚡ Short Expiry Bot (2h-7d Markets)")

    # Bot status
    bot_status = get_bot_status()
    if bot_status.get("short_expiry"):
        st.success("✅ Short Expiry Bot: RUNNING")
    else:
        st.warning("⚠️ Short Expiry Bot: STOPPED")

    # Balance
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Balance", format_currency(short_expiry_balance.get('balance', 0)))
    with col2:
        open_positions = short_expiry_positions[short_expiry_positions['status'] == 'open'] if not short_expiry_positions.empty else pd.DataFrame()
        st.metric("Open Positions", len(open_positions))
    with col3:
        closed_positions = short_expiry_positions[short_expiry_positions['status'] == 'closed'] if not short_expiry_positions.empty else pd.DataFrame()
        total_pnl_se = closed_positions['pnl'].sum() if not closed_positions.empty and 'pnl' in closed_positions.columns else 0
        st.metric("Total P&L", format_currency(total_pnl_se))

    st.divider()

    # Bucket breakdown
    if not open_positions.empty and 'bucket' in open_positions.columns:
        st.subheader("Positions by Time Bucket")
        bucket_counts = open_positions['bucket'].value_counts()

        col1, col2, col3 = st.columns(3)
        with col1:
            ultra_count = bucket_counts.get('ultra_short', 0)
            st.metric("⚡ Ultra-Short (0-24h)", ultra_count)
        with col2:
            short_count = bucket_counts.get('short', 0)
            st.metric("🔥 Short (24-72h)", short_count)
        with col3:
            medium_count = bucket_counts.get('medium', 0)
            st.metric("📊 Medium (72-168h)", medium_count)

    # Show positions
    st.subheader("Open Positions")
    if not open_positions.empty:
        st.markdown("*Click 🔗 to view on Polymarket*")

        # Column headers
        hcol1, hcol2, hcol3, hcol4, hcol5, hcol6, hcol7, hcol8 = st.columns([2, 0.5, 0.6, 0.7, 0.7, 0.6, 0.9, 0.9])
        with hcol1:
            st.markdown("**Market**")
        with hcol2:
            st.markdown("**Bucket**")
        with hcol3:
            st.markdown("**Side**")
        with hcol4:
            st.markdown("**Entry**")
        with hcol5:
            st.markdown("**Current**")
        with hcol6:
            st.markdown("**Size**")
        with hcol7:
            st.markdown("**Entry Date**")
        with hcol8:
            st.markdown("**P&L / Expiry**")

        for idx, row in open_positions.iterrows():
            bucket_emoji = {"ultra_short": "⚡", "short": "🔥", "medium": "📊"}
            bucket = row.get('bucket', 'unknown')
            market_id = row.get('market_id', '')
            outcome = row.get('outcome', 'N/A')
            entry_price = row.get('entry_price', 0) or 0
            size = row.get('size', 0) or 0
            entry_time = row.get('entry_time', '')
            hours_to_expiry = row.get('hours_to_expiry_at_entry', 0) or 0

            # Get market name and slug for direct link
            if 'question' in row and pd.notna(row.get('question')) and row.get('question'):
                market_name = str(row.get('question'))[:60]
                # Try to fetch slug for direct link
                market_info = get_market_info(market_id)
                market_slug = market_info.get('slug')
            else:
                market_info = get_market_info(market_id)
                market_name = market_info.get('name', 'Unknown Market')[:60]
                market_slug = market_info.get('slug')

            # Format entry date
            if pd.notna(entry_time):
                try:
                    entry_date = pd.to_datetime(entry_time, format='mixed').strftime('%m/%d %H:%M')
                except:
                    entry_date = str(entry_time)[:16] if entry_time else 'N/A'
            else:
                entry_date = 'N/A'

            # Create Polymarket URL - use direct link if slug available
            if market_slug:
                poly_url = f"https://polymarket.com/event/{market_slug}"
            else:
                # Fallback to search if no slug
                poly_url = f"https://polymarket.com/markets?_q={quote(str(market_name)[:30])}"

            # Get current price
            prices = get_current_prices(market_id)
            if outcome.upper() == "YES":
                current_price = prices.get('yes')
            else:
                current_price = prices.get('no')
                if current_price is None and prices.get('yes') is not None:
                    current_price = 1.0 - prices.get('yes')

            # Calculate unrealized P&L
            if current_price is not None and entry_price > 0:
                tokens = size / entry_price
                payout = tokens * current_price
                unrealized_pnl = payout - size
                pnl_pct = (unrealized_pnl / size) * 100 if size > 0 else 0
            else:
                unrealized_pnl = None
                pnl_pct = None

            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 0.5, 0.6, 0.7, 0.7, 0.6, 0.9, 0.9])
            with col1:
                st.markdown(f"**{market_name}** [🔗]({poly_url})")
            with col2:
                st.write(f"{bucket_emoji.get(bucket, '📈')}")
            with col3:
                color = "🟢" if outcome.upper() == "YES" else "🔴"
                st.write(f"{color} {outcome}")
            with col4:
                st.write(f"${entry_price:.3f}")
            with col5:
                if current_price is not None:
                    st.write(f"${current_price:.3f}")
                else:
                    st.write("N/A")
            with col6:
                st.write(f"${size:.2f}")
            with col7:
                st.write(f"{entry_date}")
            with col8:
                if unrealized_pnl is not None:
                    pnl_color = "🟢" if unrealized_pnl >= 0 else "🔴"
                    st.write(f"{pnl_color} ${unrealized_pnl:+.2f}")
                else:
                    st.write(f"⏱️ {hours_to_expiry:.1f}h")

        st.divider()

        # Table view
        with st.expander("📋 Table View"):
            display_cols = ['bucket', 'outcome', 'entry_price', 'size', 'hours_to_expiry_at_entry', 'entry_time', 'signal_reason']
            if all(col in open_positions.columns for col in display_cols):
                display_df = open_positions[display_cols].copy()
                display_df.columns = ['Bucket', 'Side', 'Entry', 'Size', 'Expiry (h)', 'Entry Time', 'Signal']
                display_df['Bucket'] = display_df['Bucket'].apply(lambda x: x.replace('_', ' ').title() if pd.notna(x) else 'N/A')
                display_df['Entry'] = display_df['Entry'].apply(lambda x: f"${x:.3f}" if pd.notna(x) else 'N/A')
                display_df['Size'] = display_df['Size'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else 'N/A')
                display_df['Expiry (h)'] = display_df['Expiry (h)'].apply(lambda x: f"{x:.1f}h" if pd.notna(x) else 'N/A')
                display_df['Entry Time'] = pd.to_datetime(display_df['Entry Time'], format='mixed').dt.strftime('%Y-%m-%d %H:%M')
                display_df['Signal'] = display_df['Signal'].apply(lambda x: x.replace('_', ' ').title() if pd.notna(x) else 'N/A')
                st.dataframe(display_df, width='stretch', hide_index=True)
    else:
        st.info("No open positions")

    # Closed positions
    st.subheader("Recent Closed Positions")
    if not closed_positions.empty:
        # Show last 10
        closed_sorted = closed_positions.sort_values('exit_time', ascending=False).head(10) if 'exit_time' in closed_positions.columns else closed_positions.head(10)

        # Exit reason emoji mapping
        exit_reason_icons = {
            'stop_loss': '🛑',
            'take_profit': '💰',
            'trailing_stop': '📉',
            'time_exit': '⏰',
            'expiry': '📅',
            'expiry_time': '⏱️',
            'expiry_closed': '🔒',
            'market_closed': '🔒',
            'manual': '✋',
            None: '—'
        }

        # Column headers
        st.markdown("---")
        hcol1, hcol2, hcol3, hcol4, hcol5, hcol6, hcol7, hcol8, hcol9 = st.columns([2, 0.5, 0.6, 0.9, 0.6, 0.9, 0.9, 0.9, 0.5])
        with hcol1:
            st.markdown("**Market**")
        with hcol2:
            st.markdown("**Bucket**")
        with hcol3:
            st.markdown("**Side**")
        with hcol4:
            st.markdown("**Entry→Exit**")
        with hcol5:
            st.markdown("**Size**")
        with hcol6:
            st.markdown("**Entry Date**")
        with hcol7:
            st.markdown("**Exit Date**")
        with hcol8:
            st.markdown("**P&L**")
        with hcol9:
            st.markdown("**Reason**")

        for idx, row in closed_sorted.iterrows():
            bucket_emoji = {"ultra_short": "⚡", "short": "🔥", "medium": "📊"}
            bucket = row.get('bucket', 'unknown')
            market_id = row.get('market_id', '')
            outcome = row.get('outcome', 'N/A')
            entry_price = row.get('entry_price', 0) or 0
            exit_price = row.get('exit_price', 0) or 0
            size = row.get('size', 0) or 0
            pnl = row.get('pnl', 0) or 0
            exit_reason = row.get('exit_reason', None)
            entry_time = row.get('entry_time', '')
            exit_time = row.get('exit_time', '')

            # Get market name and slug for direct link
            if 'question' in row and pd.notna(row.get('question')) and row.get('question'):
                market_name = str(row.get('question'))[:50]
                # Try to fetch slug for direct link
                market_info = get_market_info(market_id)
                market_slug = market_info.get('slug')
            else:
                market_info = get_market_info(market_id)
                market_name = market_info.get('name', 'Unknown Market')[:50]
                market_slug = market_info.get('slug')

            # Format dates
            if pd.notna(entry_time):
                try:
                    entry_date = pd.to_datetime(entry_time, format='mixed').strftime('%m/%d %H:%M')
                except:
                    entry_date = str(entry_time)[:16] if entry_time else 'N/A'
            else:
                entry_date = 'N/A'

            if pd.notna(exit_time):
                try:
                    exit_date = pd.to_datetime(exit_time, format='mixed').strftime('%m/%d %H:%M')
                except:
                    exit_date = str(exit_time)[:16] if exit_time else 'N/A'
            else:
                exit_date = 'N/A'

            # Create Polymarket URL - use direct link if slug available
            if market_slug:
                poly_url = f"https://polymarket.com/event/{market_slug}"
            else:
                # Fallback to search if no slug
                poly_url = f"https://polymarket.com/markets?_q={quote(str(market_name)[:30])}"

            # Color code P&L
            pnl_color = "🟢" if pnl and pnl > 0 else "🔴"

            # Exit reason icon
            exit_icon = exit_reason_icons.get(exit_reason, '—')

            col1, col2, col3, col4, col5, col6, col7, col8, col9 = st.columns([2, 0.5, 0.6, 0.9, 0.6, 0.9, 0.9, 0.9, 0.5])
            with col1:
                st.markdown(f"{market_name} [🔗]({poly_url})")
            with col2:
                st.write(f"{bucket_emoji.get(bucket, '📈')}")
            with col3:
                st.write(f"{outcome}")
            with col4:
                st.write(f"${entry_price:.3f}→${exit_price:.3f}" if exit_price else f"${entry_price:.3f}")
            with col5:
                st.write(f"${size:.2f}")
            with col6:
                st.write(f"{entry_date}")
            with col7:
                st.write(f"{exit_date}")
            with col8:
                st.write(f"{pnl_color} ${pnl:+.2f}" if pnl else "N/A")
            with col9:
                st.write(f"{exit_icon}")
    else:
        st.info("No closed positions yet")

with tab3:
    st.subheader("Performance Analytics")

    if not pl_closed.empty and 'pnl' in pl_closed.columns:
        # P&L over time
        pl_closed['exit_time'] = pd.to_datetime(pl_closed['exit_time'], format='mixed')
        pl_closed_sorted = pl_closed.sort_values('exit_time')
        pl_closed_sorted['cumulative_pnl'] = pl_closed_sorted['pnl'].cumsum()

        fig = px.line(pl_closed_sorted, x='exit_time', y='cumulative_pnl',
                     title='Cumulative P&L Over Time')
        fig.update_layout(xaxis_title='Date', yaxis_title='Cumulative P&L ($)')
        st.plotly_chart(fig, use_container_width=True)

        # Win rate
        wins = (pl_closed['pnl'] > 0).sum()
        losses = (pl_closed['pnl'] <= 0).sum()
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Win Rate", f"{win_rate:.1%}")
        with col2:
            st.metric("Winning Trades", wins)
        with col3:
            st.metric("Losing Trades", losses)

        # P&L distribution
        fig2 = px.histogram(pl_closed, x='pnl', nbins=20,
                           title='P&L Distribution')
        fig2.update_layout(xaxis_title='P&L ($)', yaxis_title='Count')
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No closed trades yet for performance analysis")

with tab4:
    st.subheader("Arbitrage Monitor")

    arb_df = load_arbitrage_opportunities()

    if not arb_df.empty:
        st.write(f"Total opportunities logged: {len(arb_df)}")

        # Recent opportunities
        st.subheader("Recent Opportunities")
        recent = arb_df.head(20)

        display_arb = recent[['timestamp', 'type', 'question', 'yes_price', 'no_price', 'profit_pct', 'profitable']].copy()
        display_arb.columns = ['Time', 'Type', 'Market', 'YES', 'NO', 'Profit %', 'Actionable']
        display_arb['Time'] = display_arb['Time'].dt.strftime('%Y-%m-%d %H:%M')
        display_arb['YES'] = display_arb['YES'].apply(lambda x: f"${x:.3f}" if pd.notna(x) else "N/A")
        display_arb['NO'] = display_arb['NO'].apply(lambda x: f"${x:.3f}" if pd.notna(x) else "N/A")

        st.dataframe(display_arb, width='stretch', hide_index=True)

        # Opportunities by type
        if 'type' in arb_df.columns:
            type_counts = arb_df['type'].value_counts().reset_index()
            type_counts.columns = ['Type', 'Count']

            fig = px.bar(type_counts, x='Type', y='Count',
                        title='Opportunities by Type')
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No arbitrage opportunities logged yet")
        st.write("The arbitrage bot logs opportunities to `data/arbitrage/`")

with tab5:
    st.subheader("Data Collection Progress")

    dc_stats = get_data_collection_stats()

    # Progress metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        trades = dc_stats["on_chain_trades"]
        target = dc_stats["target_trades"]
        pct = (trades / target * 100) if target > 0 else 0
        st.metric(
            "On-Chain Trades",
            f"{trades:,}",
            delta=f"{pct:.1f}% of target"
        )

    with col2:
        st.metric(
            "Token Mappings",
            f"{dc_stats['token_mappings']:,}"
        )

    with col3:
        st.metric(
            "Markets Indexed",
            f"{dc_stats['markets']:,}"
        )

    with col4:
        st.metric(
            "News Events",
            f"{dc_stats['news_events']:,}"
        )

    st.divider()

    # Collection status
    st.subheader("Data Collectors Status")

    collector_status = get_collector_status()
    db_stats = get_collector_db_stats()

    # Two columns for collectors
    col1, col2 = st.columns(2)

    with col1:
        st.write("### GDELT News Collector")
        gdelt_info = collector_status["gdelt_collector"]
        status_icon = "🟢 Running" if gdelt_info["running"] else "🔴 Stopped"
        st.write(f"**Status:** {status_icon}")
        if gdelt_info["docker"]:
            st.write(f"**Mode:** Docker ({gdelt_info['docker_status']})")
        elif gdelt_info["pid"]:
            st.write(f"**Mode:** Process (PID: {gdelt_info['pid']})")

        st.write(f"**Database:** gdelt_news.db ({db_stats['gdelt_db_size_mb']:.1f} MB)")
        st.write(f"**News Events:** {db_stats['gdelt_events']:,}")
        st.write(f"**Files Processed:** {db_stats['gdelt_files_processed']:,}")
        if db_stats['gdelt_latest_event']:
            st.write(f"**Latest Event:** {db_stats['gdelt_latest_event'][:19]}")

        # GDELT Progress bar (96 files/day * 180 days = 17,280 files for 6 months)
        target_files = 17_280
        files_processed = db_stats['gdelt_files_processed']
        gdelt_progress = min(files_processed / target_files, 1.0) if target_files > 0 else 0
        st.progress(gdelt_progress, text=f"Files: {files_processed:,} / {target_files:,} ({gdelt_progress*100:.1f}%)")

        st.write("---")
        st.caption("Collects global news from GDELT Project with sentiment, themes, entities, and locations.")

    with col2:
        st.write("### Alchemy On-Chain Collector")
        alchemy_info = collector_status["alchemy_collector"]
        status_icon = "🟢 Running" if alchemy_info["running"] else "🔴 Stopped"
        st.write(f"**Status:** {status_icon}")
        if alchemy_info["docker"]:
            st.write(f"**Mode:** Docker ({alchemy_info['docker_status']})")
        elif alchemy_info["pid"]:
            st.write(f"**Mode:** Process (PID: {alchemy_info['pid']})")

        st.write(f"**Database:** alchemy_trades.db ({db_stats['alchemy_db_size_mb']:.1f} MB)")
        st.write(f"**On-Chain Trades:** {db_stats['alchemy_trades']:,}")
        if db_stats['alchemy_last_block']:
            st.write(f"**Last Block:** {db_stats['alchemy_last_block']:,}")
        if db_stats['alchemy_last_trade']:
            st.write(f"**Last Trade:** {db_stats['alchemy_last_trade'][:19]}")

        # Alchemy Progress bar (50M target trades for 6 months)
        target_trades = 50_000_000
        alchemy_trades = db_stats['alchemy_trades']
        alchemy_progress = min(alchemy_trades / target_trades, 1.0) if target_trades > 0 else 0
        st.progress(alchemy_progress, text=f"Trades: {alchemy_trades:,} / {target_trades:,} ({alchemy_progress*100:.1f}%)")

        st.write("---")
        st.caption("Collects OrderFilled events from Polymarket's CTF Exchange on Polygon.")

    st.divider()

    # Collector logs
    st.subheader("Recent Collector Logs")
    log_choice = st.selectbox("Select Collector Log",
                              ["gdelt_collection.out", "alchemy_collection.out"])

    try:
        result = subprocess.run(
            ["tail", "-30", log_choice],
            capture_output=True, text=True
        )
        if result.stdout:
            st.code(result.stdout, language="text")
        else:
            st.info("No recent logs")
    except Exception as e:
        st.warning(f"Could not fetch logs: {e}")

with tab6:
    st.subheader("Configuration")

    # Load configs
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Price Level Bot Config**")
        try:
            with open("config_price_levels.json", 'r') as f:
                config_pl = json.load(f)
            st.json(config_pl)
        except:
            st.error("Could not load config_price_levels.json")

    with col2:
        st.write("**Arbitrage Bot Config**")
        try:
            with open("config_arbitrage.json", 'r') as f:
                config_arb = json.load(f)
            st.json(config_arb)
        except:
            st.error("Could not load config_arbitrage.json")

    st.divider()

    # Bot logs
    st.subheader("Recent Logs")

    log_choice = st.selectbox("Select Log",
                              ["trading_price_levels.out", "trading.out", "arbitrage.out"])

    try:
        result = subprocess.run(
            ["tail", "-50", log_choice],
            capture_output=True, text=True
        )
        st.code(result.stdout, language="text")
    except Exception as e:
        st.error(f"Could not read log: {e}")

# Footer
st.divider()
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
