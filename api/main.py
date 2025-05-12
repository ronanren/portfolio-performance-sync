from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from script import calculate_portfolio
from .security import get_api_key

app = FastAPI(
    title="Portfolio API",
    description="API for retrieving portfolio information",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/portfolio", dependencies=[Depends(get_api_key)])
async def get_portfolio_value(base_currency: str = "USD") -> Dict[str, Any]:
    """
    Get the total portfolio value.

    Args:
        base_currency (str): The base currency for calculations (USD or EUR)

    Returns:
        Dict containing portfolio information including summary
    """
    if base_currency not in ["USD", "EUR"]:
        raise HTTPException(
            status_code=400, detail="Base currency must be either USD or EUR"
        )

    try:
        summary = calculate_portfolio(base_currency)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating portfolio value: {str(e)}"
        )
