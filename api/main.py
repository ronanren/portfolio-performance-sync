from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import sys
import os
import time
from datetime import datetime
import asyncio
from contextlib import asynccontextmanager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from script import calculate_portfolio
from .security import get_api_key


# Cache structure
portfolio_cache = {
    "USD": {"data": None, "timestamp": 0},
    "EUR": {"data": None, "timestamp": 0},
}

# Lock to prevent concurrent cache updates
cache_update_lock = asyncio.Lock()

# Background task reference
background_task = None


async def update_portfolio_cache():
    """Update the portfolio cache for both currencies in the background"""
    if cache_update_lock.locked():
        print(f"Cache update already in progress, skipping...")
        return
    
    async with cache_update_lock:
        try:
            print(f"Starting cache update at {datetime.now().isoformat()}")
            
            summary_usd, _ = await calculate_portfolio("USD")
            portfolio_cache["USD"]["data"] = summary_usd
            portfolio_cache["USD"]["timestamp"] = time.time()

            summary_eur, _ = await calculate_portfolio("EUR")
            portfolio_cache["EUR"]["data"] = summary_eur
            portfolio_cache["EUR"]["timestamp"] = time.time()

            print(f"Cache updated successfully at {datetime.now().isoformat()}")
        except Exception as e:
            print(f"Error updating cache: {str(e)}")


async def cache_update_loop():
    """Background loop that updates the cache every 5 minutes"""
    while True:
        try:
            await asyncio.sleep(300)
            asyncio.create_task(update_portfolio_cache())
        except Exception as e:
            print(f"Error in cache update loop: {str(e)}")
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global background_task
    
    print("Initializing cache...")
    await update_portfolio_cache()
    
    background_task = asyncio.create_task(cache_update_loop())
    print("Background cache update loop started")
    
    yield
    
    if background_task:
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Portfolio API",
    description="API for retrieving portfolio information",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/portfolio", dependencies=[Depends(get_api_key)])
async def get_portfolio_value(base_currency: str = "USD") -> Dict[str, Any]:
    """
    Get the total portfolio value and details from cache.

    Args:
        base_currency (str): The base currency for calculations (USD or EUR)

    Returns:
        Dict containing portfolio information including summary and last update time
    """
    if base_currency not in ["USD", "EUR"]:
        raise HTTPException(
            status_code=400, detail="Base currency must be either USD or EUR"
        )

    cached_data = portfolio_cache[base_currency]

    if cached_data["data"] is None:
        raise HTTPException(
            status_code=503, detail="Portfolio data is not yet available"
        )

    return {
        "summary": cached_data["data"],
        "last_updated": datetime.fromtimestamp(cached_data["timestamp"]).isoformat(),
    }
