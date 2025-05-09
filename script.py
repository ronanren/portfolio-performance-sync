import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal, getcontext
import yfinance as yf
from datetime import datetime
import pandas as pd


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
            raise ValueError(f"Unsupported currency: {currency}")
    else:
        raise ValueError(f"Unsupported base currency: {base_currency}")


def main(base_currency="USD"):
    # === Load XML ===
    tree = ET.parse("portfolio.xml")
    root = tree.getroot()

    # === Parse Securities ===
    security_map = {}
    for sec in root.find("securities").findall("security"):
        uuid = sec.findtext("uuid")
        ticker = sec.findtext("tickerSymbol")
        name = sec.findtext("name")
        currency = sec.findtext("currencyCode")
        price = Decimal(str(yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1]))
        security_map[uuid] = {
            "name": name,
            "ticker": ticker,
            "currency": currency,
            "latest_price": price,
        }

    # === Process Holdings from Accounts and Portfolios ===
    holdings = defaultdict(
        lambda: {
            "name": None,
            "ticker": None,
            "currency": None,
            "total_shares": Decimal("0"),
            "total_cost": Decimal("0"),
            "fees": Decimal("0"),
        }
    )

    # Find all portfolio transactions
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
                    security_index = (
                        int(security_ref_text.split("/")[-1].split("[")[-1].rstrip("]"))
                        - 1
                    )
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

                if type_ == "BUY":
                    h["total_shares"] += shares
                    h["total_cost"] += amount_base + fees
                elif type_ == "SELL":
                    h["total_shares"] -= shares
                    h["total_cost"] -= amount_base
                h["fees"] += fees

    # === Compute Summary ===
    print(
        f"{'Account':<20} {'Ticker':<12} {'Shares':>12} {'Avg Buy (' + base_currency + ')':>12} {'Last Price (' + base_currency + ')':>12} {'Value (' + base_currency + ')':>14} {'P/L (' + base_currency + ')':>12} {'P/L %':>8}"
    )
    print("-" * 120)

    # Sort by value in descending order
    sorted_holdings = sorted(
        holdings.items(),
        key=lambda x: (
            -x[1]["total_shares"]
            * convert_to_base_currency(
                security_map[x[0]]["latest_price"],
                security_map[x[0]]["currency"],
                "",
                base_currency,
            ),
        ),
    )

    for uuid, h in sorted_holdings:
        if h["total_shares"] <= 0:
            continue
        avg_price = h["total_cost"] / h["total_shares"]
        latest_price_base = convert_to_base_currency(
            security_map[uuid]["latest_price"],
            security_map[uuid]["currency"],
            "",
            base_currency,
        )
        value = h["total_shares"] * latest_price_base
        profit_loss = value - h["total_cost"]
        profit_loss_pct = (
            (profit_loss / h["total_cost"] * 100)
            if h["total_cost"] > 0
            else Decimal("0")
        )
        print(
            f"{h['account']:<20} {h['ticker']:<12} {h['total_shares']:>12.4f} {avg_price:>12.2f} {latest_price_base:>12.2f} {value:>14.2f} {profit_loss:>12.2f} {profit_loss_pct:>8.2f}%"
        )

    # Calculate total portfolio value and profit/loss
    total_value = Decimal("0")
    total_cost = Decimal("0")
    for uuid, h in holdings.items():
        if h["total_shares"] <= 0:
            continue
        latest_price_base = convert_to_base_currency(
            security_map[uuid]["latest_price"],
            security_map[uuid]["currency"],
            "",
            base_currency,
        )
        total_value += h["total_shares"] * latest_price_base
        total_cost += h["total_cost"]

    total_profit_loss = total_value - total_cost
    profit_loss_percentage = (
        (total_profit_loss / total_cost * 100) if total_cost > 0 else Decimal("0")
    )

    print("\n" + "=" * 90)
    print(f"{'Total Portfolio Value (' + base_currency + ')':<40} {total_value:>14.2f}")
    print(f"{'Total Cost Basis (' + base_currency + ')':<40} {total_cost:>14.2f}")
    print(
        f"{'Total Profit/Loss (' + base_currency + ')':<40} {total_profit_loss:>14.2f}"
    )
    print(f"{'Profit/Loss Percentage':<40} {profit_loss_percentage:>14.2f}%")


if __name__ == "__main__":
    import sys

    base_currency = sys.argv[1] if len(sys.argv) > 1 else "USD"
    if base_currency not in ["USD", "EUR"]:
        print("Error: Base currency must be either USD or EUR")
        sys.exit(1)
    main(base_currency)
