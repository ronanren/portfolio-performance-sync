import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal, getcontext
import yfinance as yf

getcontext().prec = 10  # Higher precision for financial calculations

# Get EUR/USD exchange rate
eur_usd = yf.Ticker("EURUSD=X")
eur_usd_rate = Decimal(str(eur_usd.history(period="1d")["Close"].iloc[-1]))


def convert_to_usd(amount, currency):
    if amount is None:
        return None
    amount = Decimal(str(amount))
    if currency == "EUR":
        return amount * eur_usd_rate
    elif currency == "USD":
        return amount
    else:
        raise ValueError(f"Unsupported currency: {currency}")


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
    latest = sec.find("latest")
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
number_of_transactions = 0
# Find all portfolio transactions
for acct in root.find("accounts").findall("account"):
    for txn in acct.findall(".//portfolio-transaction"):
        type_ = txn.findtext("type")
        security_ref = txn.find("security")
        if security_ref is None:
            continue
        security_ref_text = security_ref.attrib.get("reference", "")
        if not security_ref_text:
            continue

        # Extract the security index from the reference path
        try:
            security_index = (
                int(security_ref_text.split("/")[-1].split("[")[-1].rstrip("]")) - 1
            )
            if security_index < 0 or security_index >= len(security_map):
                continue
        except (ValueError, IndexError):
            continue

        security = list(security_map.values())[security_index]
        uuid = list(security_map.keys())[security_index]

        shares = Decimal(txn.findtext("shares", default="0")) / Decimal("1e8")
        amount = Decimal(txn.findtext("amount", default="0")) / Decimal("1e2")
        amount_usd = convert_to_usd(amount, security["currency"])

        fees = Decimal("0")
        number_of_transactions += 1
        for unit in txn.findall(".//unit[@type='FEE']"):
            fee_amount = Decimal(unit.find("amount").attrib["amount"]) / Decimal("1e8")
            fees += convert_to_usd(fee_amount, security["currency"])

        h = holdings[uuid]
        h["name"] = security["name"]
        h["ticker"] = security["ticker"]
        h["currency"] = "USD"  # All amounts will be in USD now

        if type_ == "BUY":
            h["total_shares"] += shares
            h["total_cost"] += amount_usd + fees
        elif type_ == "SELL":
            h["total_shares"] -= shares
            h["total_cost"] -= amount_usd
        h["fees"] += fees

print(number_of_transactions)
# === Compute Summary ===
print(
    f"{'Asset':<25} {'Ticker':<10} {'Shares':>12} {'Avg Buy (USD)':>12} {'Last Price (USD)':>12} {'Value (USD)':>14}"
)
print("-" * 90)
for uuid, h in holdings.items():
    if h["total_shares"] <= 0:
        continue
    avg_price = h["total_cost"] / h["total_shares"]
    latest_price_usd = convert_to_usd(
        security_map[uuid]["latest_price"], security_map[uuid]["currency"]
    )
    value = h["total_shares"] * latest_price_usd
    print(
        f"{h['name'][:25]:<25} {h['ticker']:<10} {h['total_shares']:>12.4f} {avg_price:>12.2f} {latest_price_usd:>12.2f} {value:>14.2f}"
    )
