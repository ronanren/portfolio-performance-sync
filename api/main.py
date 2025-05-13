from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
import sys
import os
import time
from datetime import datetime
import aiocron
from contextlib import asynccontextmanager
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from script import calculate_portfolio
from .security import get_api_key, URL_RENDER


# Cache structure
portfolio_cache = {
    "USD": {"data": None, "timestamp": 0},
    "EUR": {"data": None, "timestamp": 0},
}


async def update_portfolio_cache(health=True):
    """Update the portfolio cache for both currencies"""
    try:
        # call health check to stay Render active
        if health:
            r = requests.get(URL_RENDER + "/api/health")
            print(r.status_code)

        # Update USD cache
        summary_usd, _ = await calculate_portfolio("USD")
        portfolio_cache["USD"]["data"] = summary_usd
        portfolio_cache["USD"]["timestamp"] = time.time()

        # Update EUR cache
        summary_eur, _ = await calculate_portfolio("EUR")
        portfolio_cache["EUR"]["data"] = summary_eur
        portfolio_cache["EUR"]["timestamp"] = time.time()

        print(f"Cache updated at {datetime.now().isoformat()}")
    except Exception as e:
        print(f"Error updating cache: {str(e)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await update_portfolio_cache(health=False)
    aiocron.crontab("*/5 * * * *", func=update_portfolio_cache)
    yield
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
