#!/usr/bin/env python3
"""
Portfolio Price Monitor
Runs on market days (Mon-Fri, excluding holidays), every hour from 11 AM to 3 PM.
Fetches live NSE prices via yfinance, compares against avg holding price,
and sends a prioritized Telegram alert for stocks trading ≥5% below avg.

Also sends a full portfolio table with current prices.
"""

import json
import ssl
import csv
import logging
import time
import socket
import os
import urllib.request
from datetime import datetime, date

import yfinance as yf

# ── Configuration ──────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8758398799:AAHeDwol7nHrElVEUKbayMsLuVdM6eXoBFk")
CHAT_ID = os.environ.get("CHAT_ID", "927307437")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_CSV = os.path.join(SCRIPT_DIR, "My equities_Sheet1.csv")
SUMMARY_CSV = os.path.join(SCRIPT_DIR, "My equities_Summary.csv")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "portfolio_monitor.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# SSL context
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# Drop threshold
DROP_THRESHOLD = 0.05  # 5%

# ── NSE Symbol Mapping ────────────────────────────────────────────────────
# Maps portfolio stock names (from CSV) to Yahoo Finance NSE symbols
SYMBOL_MAP = {
    "Amara Raja Batteries": "ARE&M.NS",  # renamed to Amara Raja Energy & Mobility
    "Aster DM Healthcare": "ASTERDM.NS",
    "Canara Bank": "CANBK.NS",
    "COALINDIA": "COALINDIA.NS",
    "Dr Reddy": "DRREDDY.NS",
    "Eicher Motors": "EICHERMOT.NS",
    "Equitas Small Fin Bank": "EQUITASBNK.NS",
    "Exide Ind": "EXIDEIND.NS",
    "Federal Bank": "FEDERALBNK.NS",
    "Goldbees": None,  # ETF - skip
    "HCL Tech": "HCLTECH.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "IDFC First": "IDFCFIRSTB.NS",
    "INDUSIND Bank": "INDUSINDBK.NS",
    "INFY": "INFY.NS",
    "IOC": "IOC.NS",
    "IRCTC": "IRCTC.NS",
    "ITC": "ITC.NS",
    "ITC HOTELS": "ITCHOTELS.NS",
    "Kotak bank": "KOTAKBANK.NS",
    "KPIT TECH": "KPITTECH.NS",
    "KTK Bank": "KTKBANK.NS",
    "Manappuram": "MANAPPURAM.NS",
    "Motilal Oswald": "MOTILALOFS.NS",
    "Muthoot Fin": "MUTHOOTFIN.NS",
    "Natco Pharma": "NATCOPHARM.NS",
    "NIFTYBEES": None,  # ETF - skip
    "ONGC": "ONGC.NS",
    "Piramal fin": "PPLPHARMA.NS",  # Piramal Pharma (successor)
    "Silverbees": None,  # ETF - skip
    "South Indian Bank": "SOUTHBANK.NS",
    "Stovekraft": "STOVEKRAFT.NS",
    "Sunpharma": "SUNPHARMA.NS",
    "Tata Chemicals": "TATACHEM.NS",
    "Tata Steel": "TATASTEEL.NS",
    "TCS": "TCS.NS",
    "Tech Mahindra": "TECHM.NS",
    "Thangamayil": "THANGAMAYL.NS",
    "Tamilnadu mercantile Bank": "TMB.NS",
    "TMCV": "TMCV.NS",
    "TMPV": "TMPV.NS",
    "Trident": "TRIDENT.NS",
    "Ujjivan Small Fin Bank": "UJJIVANSFB.NS",
    "Wipro": "WIPRO.NS",
    "Zydus Life Sciences": "ZYDUSLIFE.NS",
}

# ── Priority Classification ──────────────────────────────────────────────
# Based on user strategy: push midcaps + defensives, reduce banking exposure
PRIORITY_SECTIONS = {
    1: {
        "name": "🟢 Midcap Opportunities (Priority Buy)",
        "desc": "Midcaps you want to build — good dip = strong add",
        "filter": lambda v, cap: cap == "Midcap" and v not in ("Banking",),
    },
    2: {
        "name": "🛡️ Defensive Positions (FMCG / Pharma)",
        "desc": "Defensive plays for portfolio stability",
        "filter": lambda v, cap: v in ("FMCG", "Pharmaceuticals", "Healthcare"),
    },
    3: {
        "name": "📈 Largecap & Nifty 50 Dips",
        "desc": "Quality largecaps at a discount",
        "filter": lambda v, cap: cap in ("Nifty 50 (Largecap)", "Largecap") and v not in ("Banking", "FMCG", "Pharmaceuticals", "Healthcare"),
    },
    4: {
        "name": "🏦 Banking (Already Overweight)",
        "desc": "You're heavy here — add only if conviction is very high",
        "filter": lambda v, cap: v == "Banking",
    },
    5: {
        "name": "📋 Others",
        "desc": "Other sectors trading below avg",
        "filter": lambda v, cap: True,  # catch-all
    },
}

# ── Market Holidays (India 2026-2027) ────────────────────────────────────
# Major NSE holidays - update yearly
MARKET_HOLIDAYS_2026 = {
    date(2026, 1, 26), date(2026, 3, 10), date(2026, 3, 30),
    date(2026, 3, 31), date(2026, 4, 14), date(2026, 4, 18),
    date(2026, 5, 1), date(2026, 6, 17), date(2026, 7, 17),
    date(2026, 8, 15), date(2026, 8, 16), date(2026, 10, 2),
    date(2026, 10, 20), date(2026, 10, 21), date(2026, 11, 5),
    date(2026, 11, 24), date(2026, 12, 25),
}
MARKET_HOLIDAYS_2027 = {
    date(2027, 1, 26), date(2027, 3, 11), date(2027, 3, 18),
    date(2027, 3, 30), date(2027, 4, 14), date(2027, 4, 10),
    date(2027, 5, 1), date(2027, 7, 7), date(2027, 8, 15),
    date(2027, 8, 17), date(2027, 10, 2), date(2027, 10, 9),
    date(2027, 10, 10), date(2027, 10, 25), date(2027, 11, 15),
    date(2027, 12, 25),
}
MARKET_HOLIDAYS = MARKET_HOLIDAYS_2026 | MARKET_HOLIDAYS_2027


def is_market_day() -> bool:
    """Check if today is a trading day (Mon-Fri, not a holiday)."""
    today = date.today()
    if today.weekday() >= 5:  # Saturday=5, Sunday=6
        logger.info(f"Weekend ({today.strftime('%A')}). Skipping.")
        return False
    if today in MARKET_HOLIDAYS:
        logger.info(f"Market holiday ({today}). Skipping.")
        return False
    return True


def has_internet() -> bool:
    """Quick internet check."""
    try:
        socket.create_connection(("dns.google", 443), timeout=5)
        return True
    except OSError:
        return False


def load_portfolio() -> list[dict]:
    """Load portfolio from CSV."""
    portfolio = []
    with open(PORTFOLIO_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stock = row.get("Stock", "").strip()
            if not stock or stock == "Total Amount Invested":
                continue
            try:
                invested = float(row.get("Total invested amount", 0))
                units = float(row.get("Total units purchased", 0))
                avg_price = float(row.get("Avg. holding price", 0))
            except (ValueError, TypeError):
                continue
            if avg_price > 0 and units > 0:
                portfolio.append({
                    "stock": stock,
                    "invested": invested,
                    "units": units,
                    "avg_price": avg_price,
                })
    return portfolio


def load_classifications() -> dict:
    """Load industry vertical and market cap from Summary CSV."""
    classifications = {}
    with open(SUMMARY_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stock = row.get("Stock", "").strip()
            vertical = row.get("Industry Vertical", "").strip()
            cap = row.get("Market Cap Classification", "").strip()
            if stock and vertical:
                classifications[stock] = {"vertical": vertical, "cap": cap}
    return classifications


def fetch_live_prices(portfolio: list[dict]) -> dict:
    """Fetch live prices for all portfolio stocks using yfinance."""
    # Collect symbols to fetch
    symbols_to_fetch = []
    stock_to_symbol = {}
    for item in portfolio:
        sym = SYMBOL_MAP.get(item["stock"])
        if sym:
            symbols_to_fetch.append(sym)
            stock_to_symbol[item["stock"]] = sym

    if not symbols_to_fetch:
        return {}

    logger.info(f"Fetching prices for {len(symbols_to_fetch)} stocks...")

    # Batch fetch using yfinance
    prices = {}
    try:
        tickers = yf.Tickers(" ".join(symbols_to_fetch))
        for stock_name, symbol in stock_to_symbol.items():
            try:
                ticker = tickers.tickers[symbol]
                price = ticker.fast_info.last_price
                if price and price > 0:
                    prices[stock_name] = round(price, 2)
            except Exception as e:
                logger.warning(f"  Failed to get price for {symbol}: {e}")
    except Exception as e:
        logger.error(f"yfinance batch fetch failed: {e}")

    logger.info(f"Got prices for {len(prices)}/{len(symbols_to_fetch)} stocks")
    return prices


def classify_drop(stock_name: str, classifications: dict) -> tuple:
    """Return (vertical, cap) for a stock."""
    info = classifications.get(stock_name, {})
    return info.get("vertical", "Other"), info.get("cap", "Other")


def build_portfolio_table(portfolio: list, prices: dict) -> str:
    """Build a full portfolio table message."""
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")
    lines = [
        f"Good day Nisangan, here's an update on your portfolio at *{now}*\n",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # Table header
    lines.append("`Stock           | Avg   | CMP   | %Chg`")
    lines.append("`----------------|-------|-------|------`")

    for item in portfolio:
        stock = item["stock"]
        avg = item["avg_price"]
        cmp = prices.get(stock)
        if cmp is None:
            lines.append(f"`{stock[:16]:16s}| {avg:>5.0f} |  N/A  |  N/A`")
            continue
        pct = ((cmp - avg) / avg) * 100
        # Arrow indicator
        if pct <= -5:
            indicator = "🔴"
        elif pct < 0:
            indicator = "🟡"
        else:
            indicator = "🟢"

        lines.append(
            f"`{stock[:16]:16s}| {avg:>5.0f} | {cmp:>5.0f} |{pct:>+5.1f}%` {indicator}"
        )

    lines.append("`━━━━━━━━━━━━━━━━|━━━━━━━|━━━━━━━|━━━━━━`")

    # Summary stats
    total_invested = sum(p["invested"] for p in portfolio)
    total_current = sum(
        prices.get(p["stock"], p["avg_price"]) * p["units"]
        for p in portfolio
    )
    overall_pct = ((total_current - total_invested) / total_invested) * 100
    lines.append(f"\n💰 *Total Invested:* ₹{total_invested:,.0f}")
    lines.append(f"📊 *Current Value:* ₹{total_current:,.0f} ({overall_pct:+.1f}%)")

    return "\n".join(lines)


def build_alert_message(drops: list, classifications: dict) -> str:
    """Build prioritized alert for stocks ≥5% below avg."""
    if not drops:
        return ""

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "⚠️ *STOCKS TRADING ≥5% BELOW YOUR AVG*\n",
    ]

    # Assign each drop to a priority section
    assigned = {i: [] for i in PRIORITY_SECTIONS}
    for drop in drops:
        stock = drop["stock"]
        vertical, cap = classify_drop(stock, classifications)
        placed = False
        for priority in sorted(PRIORITY_SECTIONS.keys()):
            section = PRIORITY_SECTIONS[priority]
            if priority == 5:  # catch-all
                if not placed:
                    assigned[priority].append(drop)
                break
            if section["filter"](vertical, cap):
                assigned[priority].append(drop)
                placed = True
                break

    # Build sections
    for priority in sorted(PRIORITY_SECTIONS.keys()):
        section_drops = assigned[priority]
        if not section_drops:
            continue
        sec = PRIORITY_SECTIONS[priority]
        lines.append(f"\n*{sec['name']}*")
        lines.append(f"_{sec['desc']}_")
        for d in sorted(section_drops, key=lambda x: x["pct_drop"]):
            lines.append(
                f"  • {d['stock']}: ₹{d['cmp']:.0f} "
                f"(avg ₹{d['avg']:.0f}, *{d['pct_drop']:+.1f}%*)"
            )

    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    """Send a message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=15, context=_SSL_CTX)
        result = json.loads(resp.read())
        if result.get("ok"):
            logger.info("Message sent successfully")
            return True
        else:
            logger.error(f"Telegram API error: {result}")
            return False
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def main():
    """Main execution flow."""
    logger.info("=" * 50)
    logger.info("Portfolio Monitor starting...")

    # Check if market day (skip on weekends/holidays)
    if not is_market_day():
        return

    # Check internet
    if not has_internet():
        logger.warning("No internet. Waiting 60s and retrying...")
        time.sleep(60)
        if not has_internet():
            logger.error("Still no internet. Aborting.")
            return

    # Load data
    portfolio = load_portfolio()
    classifications = load_classifications()
    logger.info(f"Loaded {len(portfolio)} stocks from portfolio")

    # Fetch live prices
    prices = fetch_live_prices(portfolio)
    if not prices:
        logger.error("Could not fetch any prices. Aborting.")
        return

    # Find stocks ≥5% below avg
    drops = []
    for item in portfolio:
        stock = item["stock"]
        cmp = prices.get(stock)
        if cmp is None:
            continue
        avg = item["avg_price"]
        pct_change = ((cmp - avg) / avg) * 100
        if pct_change <= -(DROP_THRESHOLD * 100):
            drops.append({
                "stock": stock,
                "avg": avg,
                "cmp": cmp,
                "pct_drop": pct_change,
                "units": item["units"],
            })

    logger.info(f"Found {len(drops)} stocks trading ≥5% below avg holding")

    # Build messages
    table_msg = build_portfolio_table(portfolio, prices)
    alert_msg = build_alert_message(drops, classifications)

    # Combine into final message
    final_msg = table_msg
    if alert_msg:
        final_msg += "\n\n" + alert_msg

    # Telegram has 4096 char limit - split if needed
    if len(final_msg) > 4000:
        # Send table first, then alert separately
        send_telegram(table_msg)
        if alert_msg:
            send_telegram(alert_msg)
    else:
        send_telegram(final_msg)

    logger.info("Portfolio monitor complete.")


if __name__ == "__main__":
    main()
