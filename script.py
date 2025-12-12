import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal
import yfinance as yf
from datetime import datetime
import pandas as pd
from typing import Dict, List, Any, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor


def get_historical_eur_usd_rate(date_str):
    """Get EUR/USD exchange rate for a specific date"""
    if not date_str:
        eur_usd = yf.Ticker("EURUSD=X")
        return Decimal(str(eur_usd.history(period="1d")["Close"].iloc[-1]))

    date = datetime.strptime(date_str.split("T")[0], "%Y-%m-%d")
    eur_usd = yf.Ticker("EURUSD=X")

    try:
        historical_data = eur_usd.history(start=date, end=date + pd.Timedelta(days=1))
        if not historical_data.empty:
            return Decimal(str(historical_data["Close"].iloc[0]))
    except:
        pass

    for days_back in range(1, 6):
        try:
            lookback_date = date - pd.Timedelta(days=days_back)
            historical_data = eur_usd.history(
                start=lookback_date, end=lookback_date + pd.Timedelta(days=1)
            )
            if not historical_data.empty:
                return Decimal(str(historical_data["Close"].iloc[0]))
        except:
            continue
    try:
        historical_data = eur_usd.history(period="1d")
        if not historical_data.empty:
            return Decimal(str(historical_data["Close"].iloc[-1]))
    except:
        return Decimal("1.0")


def get_latest_price(ticker: str) -> Decimal:
    """Get the latest price for a ticker with error handling"""
    try:
        ticker_data = yf.Ticker(ticker)
        history = ticker_data.history(period="1d")
        if not history.empty:
            return Decimal(str(history["Close"].iloc[-1]))
        else:
            print(f"Warning: No price data found for {ticker}")
            return Decimal("0")
    except Exception as e:
        print(f"Warning: Error getting price for {ticker}: {str(e)}")
        return Decimal("0")


async def fetch_security_prices(securities: List[Dict[str, Any]]) -> Dict[str, Decimal]:
    """Fetch security prices in parallel using ThreadPoolExecutor"""
    prices = {}

    def fetch_price(ticker: str) -> Tuple[str, Decimal]:
        return ticker, get_latest_price(ticker)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_price, sec["ticker"]) for sec in securities]

        for future in futures:
            ticker, price = future.result()
            prices[ticker] = price

    return prices


def convert_to_base_currency(amount, currency, date_str, base_currency="USD"):
    """Convert amount to base currency (USD or EUR)"""
    if amount is None:
        return None
    amount = Decimal(str(amount))

    if currency == base_currency:
        return amount

    if base_currency == "USD":
        if currency == "EUR":
            rate = get_historical_eur_usd_rate(date_str)
            return amount * rate
        else:
            raise ValueError(f"Unsupported currency: {currency}")
    elif base_currency == "EUR":
        if currency == "USD":
            rate = get_historical_eur_usd_rate(date_str)
            return amount / rate
        else:
            raise ValueError(f"Unsupported base_currency: {base_currency}")
    else:
        raise ValueError(f"Unsupported base_currency: {base_currency}")


async def calculate_portfolio(
    base_currency="USD",
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Calculate portfolio values and return structured data

    Returns:
        Tuple containing:
        - Summary dictionary with total values
        - List of dictionaries containing individual holding details
    """
    tree = ET.parse("portfolio.xml")
    root = tree.getroot()

    securities = []
    security_map = {}
    for sec in root.find("securities").findall("security"):
        uuid = sec.findtext("uuid")
        ticker = sec.findtext("tickerSymbol")
        name = sec.findtext("name")
        currency = sec.findtext("currencyCode")

        securities.append(
            {"uuid": uuid, "ticker": ticker, "name": name, "currency": currency}
        )

    prices = await fetch_security_prices(securities)

    for sec in securities:
        security_map[sec["uuid"]] = {
            "name": sec["name"],
            "ticker": sec["ticker"],
            "currency": sec["currency"],
            "latest_price": prices[sec["ticker"]],
        }

    holdings = defaultdict(
        lambda: {
            "name": None,
            "ticker": None,
            "currency": None,
            "total_shares": Decimal("0"),
            "total_cost": Decimal("0"),
            "fees": Decimal("0"),
            "is_account": False,
        }
    )

    for acct in root.find("accounts").findall("account"):
        for portfolio in acct.findall(".//portfolio"):
            account_name = portfolio.findtext("name")
            for txn in portfolio.findall(".//portfolio-transaction"):
                type_ = txn.findtext("type")
                currency = txn.findtext("currencyCode")
                date = txn.findtext("date")
                security_ref = txn.find("security")
                security_ref_text = security_ref.attrib.get("reference", "")

                try:
                    if "[" in security_ref_text:
                        security_index = (
                            int(security_ref_text.split("/")[-1].split("[")[-1].rstrip("]"))
                            - 1
                        )
                    else:
                        security_index = 0
                    
                    if security_index < 0 or security_index >= len(security_map):
                        continue
                except (ValueError, IndexError):
                    continue

                security = list(security_map.values())[security_index]
                uuid = list(security_map.keys())[security_index]

                shares = Decimal(txn.findtext("shares", default="0")) / Decimal("1e8")
                amount = Decimal(txn.findtext("amount", default="0")) / Decimal("1e2")
                amount_base = convert_to_base_currency(
                    amount, currency, date, base_currency
                )

                fees = Decimal("0")
                for unit in txn.findall(".//unit[@type='FEE']"):
                    fee_amount = Decimal(
                        unit.find("amount").attrib["amount"]
                    ) / Decimal("1e8")
                    fees += convert_to_base_currency(
                        fee_amount, currency, date, base_currency
                    )

                h = holdings[uuid]
                h["name"] = security["name"]
                h["ticker"] = security["ticker"]
                h["currency"] = base_currency
                h["account"] = account_name
                h["is_account"] = False

                if type_ == "BUY":
                    h["total_shares"] += shares
                    h["total_cost"] += amount_base + fees
                elif type_ == "SELL":
                    h["total_shares"] -= shares
                    h["total_cost"] -= amount_base
                h["fees"] += fees

    for acct in root.find("accounts").findall("account"):
        name = acct.findtext("name")
        currency = acct.findtext("currencyCode")
        if currency is None:
            continue

        if name in ["USD", "EUR"]:
            continue

        h = holdings[name]
        h["name"] = name
        h["ticker"] = "CASH"
        h["currency"] = base_currency
        h["is_account"] = True

        for txn in acct.findall(".//account-transaction"):
            type_ = txn.findtext("type")
            txn_currency = txn.findtext("currencyCode")
            if txn_currency is None:
                continue
            date = txn.findtext("date")

            amount = Decimal(txn.findtext("amount", default="0")) / Decimal("1e2")
            amount_base = convert_to_base_currency(
                amount, txn_currency, date, base_currency
            )

            if type_ == "DEPOSIT":
                h["total_cost"] += amount_base
                h["total_shares"] += amount_base
            elif type_ == "REMOVAL":
                h["total_cost"] -= amount_base
                h["total_shares"] -= amount_base
            elif type_ == "DIVIDEND":
                h["total_cost"] += amount_base
                h["total_shares"] += amount_base
            elif type_ == "INTEREST":
                h["total_cost"] += amount_base
                h["total_shares"] += amount_base
            elif type_ == "FEE":
                h["total_cost"] -= amount_base
                h["total_shares"] -= amount_base

    holdings_list = []
    total_value = Decimal("0")
    total_cost = Decimal("0")

    for uuid, h in holdings.items():
        if h["total_shares"] <= 0:
            continue

        latest_price_base = (
            Decimal("1.0")
            if h["is_account"]
            else convert_to_base_currency(
                security_map[uuid]["latest_price"],
                security_map[uuid]["currency"],
                "",
                base_currency,
            )
        )

        value = h["total_shares"] * latest_price_base
        avg_price = h["total_cost"] / h["total_shares"]
        profit_loss = value - h["total_cost"]
        profit_loss_pct = (
            (profit_loss / h["total_cost"] * 100)
            if h["total_cost"] > 0
            else Decimal("0")
        )

        holdings_list.append(
            {
                "name": h["name"],
                "ticker": h["ticker"],
                "shares": float(h["total_shares"]),
                "average_price": float(avg_price),
                "latest_price": float(latest_price_base),
                "value": float(value),
                "profit_loss": float(profit_loss),
                "profit_loss_percentage": float(profit_loss_pct),
                "account": h.get("account", ""),
                "is_account": h["is_account"],
            }
        )

        total_value += value
        total_cost += h["total_cost"]

    total_profit_loss = total_value - total_cost
    profit_loss_percentage = (
        (total_profit_loss / total_cost * 100) if total_cost > 0 else Decimal("0")
    )

    summary = {
        "base_currency": base_currency,
        "total_portfolio_value": round(float(total_value), 2),
        "total_cost_basis": round(float(total_cost), 2),
        "total_profit_loss": round(float(total_profit_loss), 2),
        "profit_loss_percentage": round(float(profit_loss_percentage), 2),
    }

    return summary, holdings_list


async def display_portfolio(base_currency="USD"):
    """Display portfolio information in a formatted table"""
    summary, holdings = await calculate_portfolio(base_currency)

    print(
        f"{'Account':<20} {'Ticker':<12} {'Shares':>12} {'Avg Buy (' + base_currency + ')':>12} {'Last Price (' + base_currency + ')':>12} {'Value (' + base_currency + ')':>14} {'P/L (' + base_currency + ')':>12} {'P/L %':>8}"
    )
    print("-" * 120)

    for h in holdings:
        print(
            f"{h['name']:<20} {h['ticker']:<12} {h['shares']:>12.4f} {h['average_price']:>12.2f} {h['latest_price']:>12.2f} {h['value']:>14.2f} {h['profit_loss']:>12.2f} {h['profit_loss_percentage']:>8.2f}%"
        )

    print("\n" + "=" * 90)
    print(
        f"{'Total Portfolio Value (' + base_currency + ')':<40} {summary['total_portfolio_value']:>14.2f}"
    )
    print(
        f"{'Total Cost Basis (' + base_currency + ')':<40} {summary['total_cost_basis']:>14.2f}"
    )
    print(
        f"{'Total Profit/Loss (' + base_currency + ')':<40} {summary['total_profit_loss']:>14.2f}"
    )
    print(f"{'Profit/Loss Percentage':<40} {summary['profit_loss_percentage']:>14.2f}%")


async def main(base_currency="USD"):
    """Main function that displays the portfolio"""
    await display_portfolio(base_currency)


if __name__ == "__main__":
    import sys

    base_currency = sys.argv[1] if len(sys.argv) > 1 else "USD"
    if base_currency not in ["USD", "EUR"]:
        print("Error: Base currency must be either USD or EUR")
        sys.exit(1)
    asyncio.run(main(base_currency))
