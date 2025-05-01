import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal, getcontext
import yfinance as yf

getcontext().prec = 10

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
    for portfolio in acct.findall(".//portfolio"):
        account_name = portfolio.findtext("name")
        for txn in portfolio.findall(".//portfolio-transaction"):
            type_ = txn.findtext("type")
            currency = txn.findtext("currencyCode")
            security_ref = txn.find("security")
            security_ref_text = security_ref.attrib.get("reference", "")

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
            amount_usd = convert_to_usd(amount, currency)

            fees = Decimal("0")
            for unit in txn.findall(".//unit[@type='FEE']"):
                fee_amount = Decimal(unit.find("amount").attrib["amount"]) / Decimal(
                    "1e8"
                )
                fees += convert_to_usd(fee_amount, currency)

            h = holdings[uuid]
            h["name"] = security["name"]
            h["ticker"] = security["ticker"]
            h["currency"] = "USD"
            h["account"] = account_name

            if type_ == "BUY":
                h["total_shares"] += shares
                h["total_cost"] += amount_usd + fees
            elif type_ == "SELL":
                h["total_shares"] -= shares
                h["total_cost"] -= amount_usd
            h["fees"] += fees
            number_of_transactions += 1

# === Compute Summary ===
print(
    f"{'Account':<20} {'Ticker':<12} {'Shares':>12} {'Avg Buy (USD)':>12} {'Last Price (USD)':>12} {'Value (USD)':>14} {'P/L (USD)':>12} {'P/L %':>8}"
)
print("-" * 120)

# Sort holdings by account first, then by value in descending order
sorted_holdings = sorted(
    holdings.items(),
    key=lambda x: (
        x[1]["account"],
        -x[1]["total_shares"]
        * convert_to_usd(
            security_map[x[0]]["latest_price"], security_map[x[0]]["currency"]
        ),
    ),
)

for uuid, h in sorted_holdings:
    if h["total_shares"] <= 0:
        continue
    avg_price = h["total_cost"] / h["total_shares"]
    latest_price_usd = convert_to_usd(
        security_map[uuid]["latest_price"], security_map[uuid]["currency"]
    )
    value = h["total_shares"] * latest_price_usd
    profit_loss = value - h["total_cost"]
    profit_loss_pct = (
        (profit_loss / h["total_cost"] * 100) if h["total_cost"] > 0 else Decimal("0")
    )
    print(
        f"{h['account']:<20} {h['ticker']:<12} {h['total_shares']:>12.4f} {avg_price:>12.2f} {latest_price_usd:>12.2f} {value:>14.2f} {profit_loss:>12.2f} {profit_loss_pct:>8.2f}%"
    )

# Calculate total portfolio value and profit/loss
total_value = Decimal("0")
total_cost = Decimal("0")
for uuid, h in holdings.items():
    if h["total_shares"] <= 0:
        continue
    latest_price_usd = convert_to_usd(
        security_map[uuid]["latest_price"], security_map[uuid]["currency"]
    )
    total_value += h["total_shares"] * latest_price_usd
    total_cost += h["total_cost"]

total_profit_loss = total_value - total_cost
profit_loss_percentage = (
    (total_profit_loss / total_cost * 100) if total_cost > 0 else Decimal("0")
)

print("\n" + "=" * 90)
print(f"{'Total Portfolio Value (USD)':<40} {total_value:>14.2f}")
print(f"{'Total Cost Basis (USD)':<40} {total_cost:>14.2f}")
print(f"{'Total Profit/Loss (USD)':<40} {total_profit_loss:>14.2f}")
print(f"{'Profit/Loss Percentage':<40} {profit_loss_percentage:>14.2f}%")
