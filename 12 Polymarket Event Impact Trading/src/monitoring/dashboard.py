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
import pytz

# Page config
st.set_page_config(
    page_title="Polymarket Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants (needed early for helper functions)
DATA_DIR = Path("data")
DASHBOARD_PREFS = DATA_DIR / "dashboard_preferences.json"

# Helper functions for dashboard preferences
def load_dashboard_preferences() -> dict:
    """Load dashboard preferences from file."""
    try:
        if DASHBOARD_PREFS.exists():
            with open(DASHBOARD_PREFS, 'r') as f:
                return json.load(f)
    except Exception as e:
        st.warning(f"Could not load dashboard preferences: {e}")
    return {"timezone": "UTC"}

def save_dashboard_preferences(prefs: dict):
    """Save dashboard preferences to file."""
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with open(DASHBOARD_PREFS, 'w') as f:
            json.dump(prefs, f, indent=2)
    except Exception as e:
        st.error(f"Could not save dashboard preferences: {e}")

# Initialize session state for timezone from saved preferences
if 'timezone' not in st.session_state:
    prefs = load_dashboard_preferences()
    st.session_state.timezone = prefs.get('timezone', 'UTC')

# Additional constants
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


def get_circuit_breaker_status() -> dict:
    """Read persisted circuit breaker state for the short-expiry bot."""
    path = DATA_DIR / "circuit_breaker_short_expiry.json"
    try:
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {"active": False}


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


def convert_to_timezone(dt, from_tz='UTC'):
    """Convert datetime to user's selected timezone."""
    if dt is None or pd.isna(dt):
        return None

    try:
        # If it's a string, parse it first
        if isinstance(dt, str):
            dt = pd.to_datetime(dt, format='mixed')

        # If datetime is naive (no timezone), assume it's UTC
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)

        # Convert to target timezone
        target_tz = pytz.timezone(st.session_state.timezone)
        dt_converted = dt.astimezone(target_tz)

        return dt_converted
    except Exception as e:
        # Return original if conversion fails
        return dt


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


def build_polymarket_url(market_id: str = None, asset: str = None,
                         market_slug: str = None, question: str = None) -> str:
    """
    Build Polymarket URL with fallback chain.

    Priority order:
    1. Parent event slug (for BTC/ETH price-level markets)
    2. Individual market slug (for short-expiry and other markets)
    3. Search query (fallback)

    Args:
        market_id: Market condition ID (optional, used to fetch slug if needed)
        asset: Asset name (BTC, ETH) for parent event lookup
        market_slug: Individual market slug from API
        question: Market question for search fallback

    Returns:
        Polymarket URL string
    """
    # Priority 1: Parent event slugs for known assets (BTC/ETH price-level markets)
    PARENT_EVENT_SLUGS = {
        'BTC': 'what-price-will-bitcoin-hit-before-2027',
        'ETH': 'what-price-will-ethereum-hit-before-2027',
    }

    if asset and asset in PARENT_EVENT_SLUGS:
        return f"https://polymarket.com/event/{PARENT_EVENT_SLUGS[asset]}"

    # Priority 2: Individual market slug (for short-expiry, sports, politics, etc.)
    if market_slug:
        return f"https://polymarket.com/market/{market_slug}"

    # Priority 3: Fetch slug from API if we have market_id
    if market_id and not market_slug:
        market_info = get_market_info(market_id)
        fetched_slug = market_info.get('slug')
        if fetched_slug:
            return f"https://polymarket.com/market/{fetched_slug}"

    # Fallback: Search query
    search_term = question[:30] if question else 'polymarket'
    return f"https://polymarket.com/markets?_q={quote(search_term)}"


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
current_time = convert_to_timezone(datetime.now(pytz.UTC))
time_str = current_time.strftime('%H:%M:%S %Z') if current_time else datetime.now().strftime('%H:%M:%S')
st.sidebar.caption(f"Last check: {time_str}")

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
pl_open = price_level_positions[price_level_positions['status'] == 'open'].copy() if not price_level_positions.empty else pd.DataFrame()
pl_closed = price_level_positions[price_level_positions['status'] == 'closed'].copy() if not price_level_positions.empty else pd.DataFrame()

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
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(["📊 Positions", "⚡ Short Expiry", "📈 Performance", "🔄 Arbitrage", "📦 Data Collection", "⚙️ Settings", "🔍 Feature Drift", "🔭 Market Funnel"])

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
            # Handle both V1 'side' and V2 'outcome' fields
            outcome_value = row.get('outcome', row.get('side', 'YES'))
            side = 'YES' if outcome_value in ['BUY', 'YES'] else 'NO'
            entry = row.get('entry_price', 0) or 0
            size = row.get('size', 0) or 0
            market_id = row.get('market_id', '')
            entry_time = row.get('entry_time', '')

            # Format entry date with timezone conversion
            if pd.notna(entry_time):
                try:
                    dt_converted = convert_to_timezone(entry_time)
                    if dt_converted:
                        entry_date = dt_converted.strftime('%m/%d %H:%M')
                    else:
                        entry_date = str(entry_time)[:16] if entry_time else 'N/A'
                except:
                    entry_date = str(entry_time)[:16] if entry_time else 'N/A'
            else:
                entry_date = 'N/A'

            # Build Polymarket URL using centralized function
            poly_url = build_polymarket_url(asset=asset, question=question)

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
            # Handle both V1 'side' and V2 'outcome' columns
            outcome_col = 'outcome' if 'outcome' in pl_open.columns else 'side'
            display_df = pl_open[['question', 'asset', outcome_col, 'entry_price', 'size', 'strike', 'entry_time']].copy()
            display_df.columns = ['Market', 'Asset', 'Side', 'Entry', 'Size', 'Strike', 'Entry Time']
            display_df['Side'] = display_df['Side'].map({'BUY': 'YES', 'SELL': 'NO', 'YES': 'YES', 'NO': 'NO'})
            display_df['Entry'] = display_df['Entry'].apply(lambda x: f"${x:.3f}")
            display_df['Size'] = display_df['Size'].apply(lambda x: f"${x:.2f}")
            display_df['Strike'] = display_df['Strike'].apply(lambda x: f"${x:,.0f}" if x else "N/A")
            # Convert to timezone before formatting
            display_df['Entry Time'] = display_df['Entry Time'].apply(lambda x: convert_to_timezone(x).strftime('%Y-%m-%d %H:%M') if convert_to_timezone(x) else str(x)[:16] if x else 'N/A')
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
            # Handle both V1 'side' and V2 'outcome' fields
            outcome_value = row.get('outcome', row.get('side', 'YES'))
            side = 'YES' if outcome_value in ['BUY', 'YES'] else 'NO'
            entry = row.get('entry_price', 0) or 0
            exit_p = row.get('exit_price', 0) or 0
            size = row.get('size', 0) or 0
            pnl = row.get('pnl', 0) or 0
            exit_reason = row.get('exit_reason', None)
            entry_time = row.get('entry_time', '')
            exit_time = row.get('exit_time', '')

            # Format dates with timezone conversion
            if pd.notna(entry_time):
                try:
                    dt_converted = convert_to_timezone(entry_time)
                    if dt_converted:
                        entry_date = dt_converted.strftime('%m/%d %H:%M')
                    else:
                        entry_date = str(entry_time)[:16] if entry_time else 'N/A'
                except:
                    entry_date = str(entry_time)[:16] if entry_time else 'N/A'
            else:
                entry_date = 'N/A'

            if pd.notna(exit_time):
                try:
                    dt_converted = convert_to_timezone(exit_time)
                    if dt_converted:
                        exit_date = dt_converted.strftime('%m/%d %H:%M')
                    else:
                        exit_date = str(exit_time)[:16] if exit_time else 'N/A'
                except:
                    exit_date = str(exit_time)[:16] if exit_time else 'N/A'
            else:
                exit_date = 'N/A'

            # Build Polymarket URL using centralized function
            poly_url = build_polymarket_url(asset=asset, question=question)

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

    # Circuit breaker status
    cb = get_circuit_breaker_status()
    if cb.get("active"):
        triggered_at = cb.get("triggered_at", "")
        resume_at = cb.get("resume_at", "")
        losses = cb.get("consecutive_losses", "?")
        cooldown = cb.get("cooldown_hours", 4.0)
        # Calculate remaining time
        remaining_str = ""
        if resume_at:
            try:
                resume_dt = datetime.fromisoformat(resume_at)
                now_utc = datetime.now(resume_dt.tzinfo)
                remaining = max(0, (resume_dt - now_utc).total_seconds() / 3600)
                remaining_str = f" — **{remaining:.1f}h remaining**"
            except Exception:
                pass
        st.error(
            f"🚨 **CIRCUIT BREAKER ACTIVE** | {losses} consecutive losses | "
            f"{cooldown:.0f}h cooldown{remaining_str} | "
            f"Resumes: {resume_at[:16].replace('T', ' ')} UTC"
        )
    elif cb.get("updated_at"):
        st.info("✅ Circuit breaker: inactive")

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

            # Get market name
            if 'question' in row and pd.notna(row.get('question')) and row.get('question'):
                market_name = str(row.get('question'))[:60]
            else:
                market_info = get_market_info(market_id)
                market_name = market_info.get('name', 'Unknown Market')[:60]

            # Format entry date with timezone conversion
            if pd.notna(entry_time):
                try:
                    dt_converted = convert_to_timezone(entry_time)
                    if dt_converted:
                        entry_date = dt_converted.strftime('%m/%d %H:%M')
                    else:
                        entry_date = str(entry_time)[:16] if entry_time else 'N/A'
                except:
                    entry_date = str(entry_time)[:16] if entry_time else 'N/A'
            else:
                entry_date = 'N/A'

            # Build Polymarket URL using centralized function
            poly_url = build_polymarket_url(market_id=market_id, question=market_name)

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
                # Convert to timezone before formatting
                display_df['Entry Time'] = display_df['Entry Time'].apply(lambda x: convert_to_timezone(x).strftime('%Y-%m-%d %H:%M') if convert_to_timezone(x) else str(x)[:16] if x else 'N/A')
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

            # Get market name
            if 'question' in row and pd.notna(row.get('question')) and row.get('question'):
                market_name = str(row.get('question'))[:50]
            else:
                market_info = get_market_info(market_id)
                market_name = market_info.get('name', 'Unknown Market')[:50]

            # Format dates with timezone conversion
            if pd.notna(entry_time):
                try:
                    dt_converted = convert_to_timezone(entry_time)
                    if dt_converted:
                        entry_date = dt_converted.strftime('%m/%d %H:%M')
                    else:
                        entry_date = str(entry_time)[:16] if entry_time else 'N/A'
                except:
                    entry_date = str(entry_time)[:16] if entry_time else 'N/A'
            else:
                entry_date = 'N/A'

            if pd.notna(exit_time):
                try:
                    dt_converted = convert_to_timezone(exit_time)
                    if dt_converted:
                        exit_date = dt_converted.strftime('%m/%d %H:%M')
                    else:
                        exit_date = str(exit_time)[:16] if exit_time else 'N/A'
                except:
                    exit_date = str(exit_time)[:16] if exit_time else 'N/A'
            else:
                exit_date = 'N/A'

            # Build Polymarket URL using centralized function
            poly_url = build_polymarket_url(market_id=market_id, question=market_name)

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
        # Convert to timezone before formatting
        display_arb['Time'] = display_arb['Time'].apply(lambda x: convert_to_timezone(x).strftime('%Y-%m-%d %H:%M') if convert_to_timezone(x) else str(x)[:16] if x else 'N/A')
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
            latest_dt = convert_to_timezone(db_stats['gdelt_latest_event'])
            latest_str = latest_dt.strftime('%Y-%m-%d %H:%M') if latest_dt else db_stats['gdelt_latest_event'][:19]
            st.write(f"**Latest Event:** {latest_str}")

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
            last_trade_dt = convert_to_timezone(db_stats['alchemy_last_trade'])
            last_trade_str = last_trade_dt.strftime('%Y-%m-%d %H:%M') if last_trade_dt else db_stats['alchemy_last_trade'][:19]
            st.write(f"**Last Trade:** {last_trade_str}")

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

    # Timezone selector
    st.write("### 🌍 Display Timezone")
    col_tz1, col_tz2 = st.columns([2, 3])

    with col_tz1:
        # Popular timezones
        popular_timezones = [
            'UTC',
            'US/Eastern',
            'US/Central',
            'US/Mountain',
            'US/Pacific',
            'Europe/London',
            'Europe/Paris',
            'Europe/Berlin',
            'Asia/Tokyo',
            'Asia/Shanghai',
            'Asia/Singapore',
            'Asia/Hong_Kong',
            'Australia/Sydney',
        ]

        selected_tz = st.selectbox(
            "Select Timezone",
            options=popular_timezones,
            index=popular_timezones.index(st.session_state.timezone) if st.session_state.timezone in popular_timezones else 0,
            help="All timestamps will be displayed in this timezone"
        )

        # Update session state and save to file if changed
        if selected_tz != st.session_state.timezone:
            st.session_state.timezone = selected_tz
            # Persist to file
            save_dashboard_preferences({"timezone": selected_tz})
            st.success(f"Timezone saved: {selected_tz}")
            st.rerun()

    with col_tz2:
        # Show current time in selected timezone
        try:
            tz = pytz.timezone(st.session_state.timezone)
            current_time = datetime.now(tz)
            st.info(f"**Current time in {st.session_state.timezone}:**\n\n{current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        except Exception as e:
            st.warning(f"Could not display current time: {e}")

    st.divider()

    # Balance Management
    st.write("### 💰 Balance Management")

    MANAGE_BOTS_SCRIPT = Path("manage_bots.sh")

    BALANCE_CONFIGS = [
        {
            "label": "Price Level Trader",
            "file": PRICE_LEVEL_BALANCE,
            "key": "price_level",
            "bot_arg": "price-level",   # manage_bots.sh argument
            "default": 500.0,
        },
        {
            "label": "Event Trader",
            "file": EVENT_BALANCE,
            "key": "event",
            "bot_arg": "event",
            "default": 1000.0,
        },
        {
            "label": "Short Expiry Trader",
            "file": SHORT_EXPIRY_BALANCE,
            "key": "short_expiry",
            "bot_arg": "short-expiry",
            "default": 500.0,
        },
    ]

    for cfg in BALANCE_CONFIGS:
        current = load_balance(cfg["file"])
        current_balance = current.get("balance", 0)
        last_updated = current.get("last_updated", "N/A")

        with st.expander(f"{cfg['label']} — current: **${current_balance:,.2f}**"):
            st.caption(f"File: `{cfg['file']}` | Last updated: {last_updated}")

            new_amount = st.number_input(
                "New balance ($)",
                min_value=0.0,
                max_value=100_000.0,
                value=float(cfg["default"]),
                step=50.0,
                format="%.2f",
                key=f"reset_amount_{cfg['key']}",
            )

            restart_bot = st.checkbox(
                "Restart bot after reset (recommended — picks up new balance immediately)",
                value=True,
                key=f"restart_check_{cfg['key']}",
            )

            confirm = st.checkbox(
                f"I confirm I want to reset {cfg['label']} balance to ${new_amount:,.2f}"
                + (" and restart the bot" if restart_bot else ""),
                key=f"reset_confirm_{cfg['key']}",
            )

            if st.button(f"Reset {cfg['label']} Balance", key=f"reset_btn_{cfg['key']}", disabled=not confirm):
                # 1. Write new balance file
                try:
                    cfg["file"].parent.mkdir(parents=True, exist_ok=True)
                    with open(cfg["file"], "w") as f:
                        json.dump({
                            "balance": new_amount,
                            "last_updated": datetime.now().isoformat(),
                            "reset_by": "dashboard",
                            "previous_balance": current_balance,
                        }, f, indent=2)
                    st.success(f"✅ Balance reset: ${current_balance:,.2f} → ${new_amount:,.2f}")
                except Exception as e:
                    st.error(f"Failed to write balance file: {e}")
                    continue

                # 2. Optionally restart the bot via manage_bots.sh
                if restart_bot:
                    if not MANAGE_BOTS_SCRIPT.exists():
                        st.warning("⚠️ manage_bots.sh not found — bot not restarted. Reload the balance file manually.")
                    else:
                        # Kill ALL instances of the bot (not just the PID file one)
                        bot_script = {
                            "price_level": "trader_price_levels.py",
                            "event": "trader.py",
                            "short_expiry": "trader_short_expiry.py"
                        }.get(cfg["key"])

                        if bot_script:
                            with st.spinner(f"Stopping all {cfg['label']} instances…"):
                                # Kill all instances matching the script name
                                subprocess.run(
                                    ["pkill", "-f", bot_script],
                                    capture_output=True,
                                    timeout=10
                                )
                                # Wait for processes to die
                                import time
                                time.sleep(3)

                        with st.spinner(f"Restarting {cfg['label']}…"):
                            result = subprocess.run(
                                ["bash", str(MANAGE_BOTS_SCRIPT), "restart", cfg["bot_arg"]],
                                capture_output=True,
                                text=True,
                                timeout=30,
                            )
                        combined = (result.stdout + result.stderr).strip()
                        if result.returncode == 0:
                            st.success(f"✅ {cfg['label']} restarted")
                        else:
                            st.error(f"❌ Restart failed (exit {result.returncode})")
                        if combined:
                            st.code(combined, language="text")

                st.rerun()

    st.divider()

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

with tab7:
    st.subheader("🔍 Feature Importance & Drift Monitoring")

    # Import drift detection modules
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))

        from ml.feature_importance_tracker import FeatureImportanceTracker
        from ml.drift_detector import DriftDetector

        # Bot type selector
        bot_type = st.selectbox(
            "Select Bot Type",
            ['event', 'price_level', 'short_expiry'],
            key='drift_bot_type'
        )

        # Initialize tracker and detector
        tracker = FeatureImportanceTracker(db_path='data/training_history.db')
        detector = DriftDetector(db_path='data/training_history.db')

        # Check if data exists
        timestamps = tracker.get_training_timestamps(bot_type)

        if not timestamps:
            st.warning(f"No training data found for {bot_type} bot. Train a model first to see drift metrics.")
        else:
            st.success(f"Found {len(timestamps)} training runs for {bot_type}")

            # === SECTION 1: Drift Metrics Dashboard ===
            st.subheader("Current Drift Metrics")

            col1, col2, col3 = st.columns(3)

            try:
                # Get current and baseline
                current = tracker.get_latest_importance(bot_type)
                baseline = detector.get_baseline(bot_type, strategy='ewma', lookback_runs=5)

                if not current.empty and not baseline.empty:
                    # Calculate metrics
                    current_ranks = current.set_index('feature_name')['importance_rank']
                    baseline_ranks = baseline.set_index('feature_name')['importance_rank']
                    current_imp = current.set_index('feature_name')['normalized_importance']
                    baseline_imp = baseline.set_index('feature_name')['normalized_importance']

                    tau, p_value = detector.calculate_rank_stability(baseline_ranks, current_ranks)
                    l1_dist = detector.calculate_importance_shift(baseline_imp, current_imp)

                    current_top_5 = current.nsmallest(5, 'importance_rank')['feature_name'].tolist()
                    baseline_top_5 = baseline.nsmallest(5, 'importance_rank')['feature_name'].tolist()
                    top_5_overlap = detector.calculate_top_k_overlap(baseline_top_5, current_top_5, k=5)

                    # Display metrics
                    with col1:
                        color = "normal"
                        if tau < 0.5:
                            color = "inverse"
                        elif tau < 0.7:
                            color = "off"

                        st.metric(
                            "Rank Stability (Kendall's Tau)",
                            f"{tau:.3f}",
                            delta=None,
                            help="1.0 = perfect stability, <0.7 = warning, <0.5 = critical"
                        )

                    with col2:
                        color = "normal"
                        if l1_dist > 0.6:
                            color = "inverse"
                        elif l1_dist > 0.4:
                            color = "off"

                        st.metric(
                            "L1 Distribution Shift",
                            f"{l1_dist:.3f}",
                            delta=None,
                            help="0.0 = identical, >0.4 = warning, >0.6 = critical"
                        )

                    with col3:
                        st.metric(
                            "Top-5 Overlap",
                            f"{top_5_overlap*100:.0f}%",
                            delta=None,
                            help="100% = perfect overlap, <60% = warning, <40% = critical"
                        )
                else:
                    st.info("Not enough data to calculate drift metrics (need at least 2 training runs)")

            except Exception as e:
                st.error(f"Could not calculate drift metrics: {e}")

            st.divider()

            # === SECTION 2: Feature Importance Timeline ===
            st.subheader("Feature Importance Timeline")

            try:
                history = tracker.get_importance_history(bot_type, last_n_runs=10)

                if not history.empty:
                    # Get top 10 features
                    top_features = (
                        history.groupby('feature_name')['normalized_importance']
                        .mean()
                        .nlargest(10)
                        .index
                        .tolist()
                    )

                    # Filter to top features
                    plot_data = history[history['feature_name'].isin(top_features)]

                    # Create line chart using plotly
                    import plotly.express as px

                    fig = px.line(
                        plot_data,
                        x='training_timestamp',
                        y='normalized_importance',
                        color='feature_name',
                        title=f'Top 10 Features - Importance Over Time ({bot_type})',
                        labels={
                            'training_timestamp': 'Training Timestamp',
                            'normalized_importance': 'Normalized Importance',
                            'feature_name': 'Feature'
                        },
                        markers=True
                    )

                    fig.update_layout(
                        height=500,
                        hovermode='x unified',
                        legend=dict(
                            orientation="v",
                            yanchor="top",
                            y=1,
                            xanchor="left",
                            x=1.02
                        )
                    )

                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No historical importance data available")

            except Exception as e:
                st.error(f"Could not plot timeline: {e}")

            st.divider()

            # === SECTION 3: Current vs Baseline Comparison ===
            st.subheader("Current vs Baseline Feature Importance")

            try:
                current = tracker.get_latest_importance(bot_type)
                baseline = detector.get_baseline(bot_type, strategy='ewma', lookback_runs=5)

                if not current.empty and not baseline.empty:
                    # Merge current and baseline
                    comparison = current[['feature_name', 'normalized_importance', 'importance_rank']].merge(
                        baseline[['feature_name', 'normalized_importance', 'importance_rank']],
                        on='feature_name',
                        how='outer',
                        suffixes=('_current', '_baseline')
                    ).fillna(0)

                    # Sort by current importance
                    comparison = comparison.sort_values('normalized_importance_current', ascending=False).head(15)

                    # Create grouped bar chart
                    import plotly.graph_objects as go

                    fig = go.Figure()

                    fig.add_trace(go.Bar(
                        name='Baseline (EWMA)',
                        x=comparison['feature_name'],
                        y=comparison['normalized_importance_baseline'],
                        marker_color='lightblue'
                    ))

                    fig.add_trace(go.Bar(
                        name='Current',
                        x=comparison['feature_name'],
                        y=comparison['normalized_importance_current'],
                        marker_color='darkblue'
                    ))

                    fig.update_layout(
                        title=f'Top 15 Features - Current vs Baseline ({bot_type})',
                        xaxis_title='Feature Name',
                        yaxis_title='Normalized Importance',
                        barmode='group',
                        height=500,
                        hovermode='x unified'
                    )

                    fig.update_xaxes(tickangle=45)

                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Not enough data for comparison")

            except Exception as e:
                st.error(f"Could not create comparison chart: {e}")

            st.divider()

            # === SECTION 4: Recent Drift Alerts ===
            st.subheader("Recent Drift Alerts")

            try:
                recent_alerts = detector.get_recent_alerts(
                    bot_type=bot_type,
                    hours=168,  # Last 7 days
                    acknowledged=False
                )

                if not recent_alerts.empty:
                    # Color-code by severity
                    def severity_color(severity):
                        if severity == 'critical':
                            return '🚨'
                        elif severity == 'warning':
                            return '⚠️'
                        else:
                            return 'ℹ️'

                    recent_alerts['icon'] = recent_alerts['severity'].apply(severity_color)

                    # Display alerts
                    for _, alert in recent_alerts.iterrows():
                        with st.expander(
                            f"{alert['icon']} {alert['alert_type']} - {alert['alert_timestamp'][:19]}",
                            expanded=(alert['severity'] == 'critical')
                        ):
                            st.markdown(f"**Severity:** {alert['severity'].upper()}")
                            st.markdown(f"**Drift Score:** {alert['drift_score']:.3f}")
                            st.markdown(f"**Message:** {alert['message']}")
                            st.markdown(f"**Affected Features:** {', '.join(alert['affected_features'][:5])}")

                            # Acknowledge button
                            if st.button(f"Acknowledge Alert #{alert['id']}", key=f"ack_{alert['id']}"):
                                detector.acknowledge_alert(alert['id'])
                                st.success("Alert acknowledged!")
                                st.rerun()
                else:
                    st.success("✅ No unacknowledged drift alerts in the last 7 days")

            except Exception as e:
                st.error(f"Could not load alerts: {e}")

    except ImportError as e:
        st.error(f"Feature drift detection not available: {e}")
        st.info("Install required dependencies or train ML models to enable drift detection.")
    except Exception as e:
        st.error(f"Error loading drift detection: {e}")

with tab8:
    st.subheader("Market Discovery Funnel")
    st.caption("Tracks how many markets survive each filter stage per bot per discovery cycle.")

    TELEMETRY_DB = DATA_DIR / "telemetry.db"

    FUNNEL_STAGES = {
        'event_trader': ['api_fetched', 'event_fetched', 'combined', 'after_category', 'after_quality'],
        'short_expiry_ultra_short': ['api_fetched', 'event_fetched', 'combined', 'after_quality'],
        'short_expiry_short': ['api_fetched', 'event_fetched', 'combined', 'after_quality'],
        'short_expiry_medium': ['api_fetched', 'event_fetched', 'combined', 'after_quality'],
        'price_level_trader': ['api_fetched', 'event_fetched', 'combined', 'after_expiry', 'after_quality'],
    }

    REJECTION_SUFFIXES = [
        'rejected_spread', 'rejected_no_id', 'rejected_no_prices',
        'rejected_both_none', 'rejected_out_of_range', 'rejected_no_trade',
    ]

    def load_funnel_metrics(hours_back: int = 24) -> pd.DataFrame:
        if not TELEMETRY_DB.exists():
            return pd.DataFrame()
        try:
            conn = sqlite3.connect(str(TELEMETRY_DB))
            since = (datetime.utcnow() - timedelta(hours=hours_back)).isoformat()
            df = pd.read_sql_query(
                "SELECT metric_name, metric_value, timestamp FROM metrics "
                "WHERE metric_name LIKE 'funnel_%' AND timestamp >= ? "
                "ORDER BY timestamp DESC",
                conn, params=(since,)
            )
            conn.close()
            return df
        except Exception as e:
            st.error(f"Could not load telemetry: {e}")
            return pd.DataFrame()

    hours_back = st.slider("Look-back window (hours)", 1, 168, 24, key="funnel_hours")
    df_funnel = load_funnel_metrics(hours_back)

    if df_funnel.empty:
        st.info("No funnel metrics yet — wait for the next discovery cycle (a few minutes after bot start).")
    else:
        df_funnel['timestamp'] = pd.to_datetime(df_funnel['timestamp'])
        df_funnel['source'] = df_funnel['metric_name'].str.extract(r'^funnel_([^_]+(?:_[^_]+)*)_(?:api_fetched|event_fetched|combined|after_\w+|rejected_\w+)$')[0]
        df_funnel['stage'] = df_funnel['metric_name'].str.split('_').str[-1]

        # ── Latest snapshot per stage ──────────────────────────────────────
        st.markdown("### Latest Funnel Snapshot")
        latest = df_funnel.groupby('metric_name').first().reset_index()

        for source, stages in FUNNEL_STAGES.items():
            stage_metrics = [f"funnel_{source}_{s}" for s in stages]
            rows = latest[latest['metric_name'].isin(stage_metrics)].set_index('metric_name')
            if rows.empty:
                continue

            counts = [int(rows.loc[m, 'metric_value']) if m in rows.index else None for m in stage_metrics]
            labels = stages

            # Build funnel chart
            fig = go.Figure(go.Funnel(
                y=labels,
                x=counts,
                textinfo="value+percent initial",
                marker_color=['#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd', '#d62728'][:len(labels)]
            ))
            fig.update_layout(
                title=source.replace('_', ' ').title(),
                height=300,
                margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)

        # ── Rejection breakdown ────────────────────────────────────────────
        st.markdown("### Quality Filter Rejection Breakdown")
        rejection_names = {
            'rejected_spread': 'Spread too wide',
            'rejected_no_id': 'No market ID',
            'rejected_no_prices': 'No entry prices',
            'rejected_both_none': 'Both prices None',
            'rejected_out_of_range': 'Price out of range',
            'rejected_no_trade': 'No last trade',
        }
        rej_rows = []
        for source in FUNNEL_STAGES:
            for suffix, label in rejection_names.items():
                metric = f"funnel_{source}_{suffix}"
                row = latest[latest['metric_name'] == metric]
                if not row.empty:
                    rej_rows.append({
                        'source': source.replace('_', ' ').title(),
                        'reason': label,
                        'count': int(row.iloc[0]['metric_value']),
                        'last_seen': row.iloc[0]['timestamp'],
                    })
        if rej_rows:
            rej_df = pd.DataFrame(rej_rows)
            fig_rej = px.bar(
                rej_df[rej_df['count'] > 0],
                x='source', y='count', color='reason', barmode='stack',
                labels={'source': 'Bot', 'count': 'Rejections', 'reason': 'Reason'},
                title='Quality filter rejections by bot (latest cycle)',
                height=350
            )
            st.plotly_chart(fig_rej, use_container_width=True)
        else:
            st.info("No rejection data yet.")

        # ── Time-series: after_quality over time ──────────────────────────
        st.markdown("### Tradeable Market Count Over Time")
        aq_metrics = [f"funnel_{s}_after_quality" for s in FUNNEL_STAGES]
        ts_df = df_funnel[df_funnel['metric_name'].isin(aq_metrics)].copy()
        if not ts_df.empty:
            ts_df['bot'] = ts_df['metric_name'].str.replace('funnel_', '').str.replace('_after_quality', '').str.replace('_', ' ').str.title()
            fig_ts = px.line(
                ts_df, x='timestamp', y='metric_value', color='bot',
                labels={'metric_value': 'Markets passing all filters', 'timestamp': 'Time', 'bot': 'Bot'},
                title='Markets reaching after_quality over time',
                height=350
            )
            st.plotly_chart(fig_ts, use_container_width=True)
        else:
            st.info("Not enough history for time-series yet.")

        # ── Raw data ──────────────────────────────────────────────────────
        with st.expander("Raw funnel data"):
            st.dataframe(
                df_funnel[['metric_name', 'metric_value', 'timestamp']].rename(columns={
                    'metric_name': 'Metric', 'metric_value': 'Value', 'timestamp': 'Time'
                }),
                use_container_width=True
            )

# Footer
st.divider()
footer_time = convert_to_timezone(datetime.now(pytz.UTC))
time_str = footer_time.strftime('%Y-%m-%d %H:%M:%S %Z') if footer_time else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
st.caption(f"Last updated: {time_str}")
