#!/usr/bin/env python3
"""
Orderbook Microservice

Provides a centralized WebSocket orderbook service via HTTP API.
All trading bots connect to this service instead of managing their own WebSocket connections.

Run with: python3 src/services/orderbook_service.py
API will be available at: http://localhost:8765
"""

import sys
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Optional
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.core.polymarket_client import PolymarketClient
from src.core.orderbook_manager import OrderbookManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
client: Optional[PolymarketClient] = None
orderbook_manager: Optional[OrderbookManager] = None


@asynccontextmanager
async def lifespan(app):
    """Manage startup and shutdown of the orderbook service."""
    global client, orderbook_manager

    # Startup
    logger.info("Starting Orderbook Microservice...")
    client = PolymarketClient()
    orderbook_manager = OrderbookManager(
        client=client,
        source='websocket',
        config={'cache_ttl_seconds': 5}
    )
    success = orderbook_manager.start()
    if success:
        logger.info("WebSocket orderbook manager started successfully")
    else:
        logger.warning("WebSocket failed to start, using REST fallback")
    logger.info("Orderbook Microservice ready at http://localhost:8765")

    yield

    # Shutdown
    logger.info("Shutting down Orderbook Microservice...")
    if orderbook_manager:
        orderbook_manager.stop()
    logger.info("Orderbook Microservice stopped")


# FastAPI app
app = FastAPI(
    title="Polymarket Orderbook Service",
    description="Centralized WebSocket orderbook service for trading bots",
    version="1.0.0",
    lifespan=lifespan
)


class OrderbookResponse(BaseModel):
    """Response model for orderbook data."""
    bids: list
    asks: list
    timestamp: str
    source: str  # 'websocket' or 'rest'


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    websocket_connected: bool
    uptime_seconds: float


# Startup time tracking
startup_time = datetime.now()



@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns:
        Service status and WebSocket connection state
    """
    uptime = (datetime.now() - startup_time).total_seconds()

    websocket_connected = False
    if orderbook_manager:
        stats = orderbook_manager.get_stats()
        websocket_connected = stats.get('running', False)

    return HealthResponse(
        status="healthy" if orderbook_manager else "initializing",
        websocket_connected=websocket_connected,
        uptime_seconds=uptime
    )


@app.get("/orderbook/{token_id}", response_model=OrderbookResponse)
async def get_orderbook(token_id: str):
    """
    Get orderbook for a specific token.

    Args:
        token_id: Token ID (e.g., "809867501248...")

    Returns:
        Orderbook with bids and asks

    Example:
        GET /orderbook/8098675012482234707628271061400964058077760012953569850977649297591097740723
    """
    if not orderbook_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        orderbook = orderbook_manager.get_orderbook(token_id)

        if not orderbook:
            raise HTTPException(status_code=404, detail="Orderbook not available")

        return OrderbookResponse(
            bids=orderbook.get('bids', []),
            asks=orderbook.get('asks', []),
            timestamp=datetime.now().isoformat(),
            source=orderbook_manager.source
        )

    except Exception as e:
        logger.error(f"Error fetching orderbook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/subscribe/{condition_id}")
async def subscribe_market(condition_id: str, question: str = ""):
    """
    Register a market for orderbook tracking (WebSocket subscription).

    Args:
        condition_id: Market condition ID
        question: Optional market question

    Returns:
        Success status
    """
    if not client:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        client.register_market_for_orderbook(condition_id, question=question)
        return {"status": "subscribed", "condition_id": condition_id}

    except Exception as e:
        logger.error(f"Error subscribing to market: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """
    Get orderbook manager statistics.

    Returns:
        Stats about WebSocket connection, messages, etc.
    """
    if not orderbook_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        stats = orderbook_manager.get_stats()
        return stats

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Run the microservice."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8765,
        log_level="info"
    )


if __name__ == "__main__":
    main()
