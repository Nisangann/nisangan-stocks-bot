#!/usr/bin/env python3
"""
FII/DII Activity Tracker
========================
Weekly Telegram digest showing FII & DII shareholding changes at the stock level.

Data Sources:
  - Screener.in: Quarterly shareholding patterns (FII%, DII%) for each stock
  - NSE fiidiiTradeReact: Latest aggregate FII/DII cash market flows

Sections:
  1. Aggregate FII/DII flows (latest available day)
  2. Portfolio stocks: FII/DII quarter-over-quarter changes
  3. Non-portfolio (Nifty 50) stocks with biggest FII/DII moves

Schedule: Sunday 3:00 PM via launchd
"""

import os
import re
import json
import ssl
import time
import logging
import http.cookiejar
import urllib.request
from datetime import datetime

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "fii_dii_data")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "fii_dii_tracker.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Portfolio stocks → Screener.in symbol mapping
# ──────────────────────────────────────────────────────────────────────────────

# Maps portfolio stock name → (Screener symbol, display name)
# ETFs (Goldbees, NIFTYBEES, Silverbees) are excluded — no FII/DII data
PORTFOLIO_STOCKS = {
    "ARE&M": "Amara Raja Energy",
    "ASTERDM": "Aster DM Healthcare",
    "CANBK": "Canara Bank",
    "COALINDIA": "Coal India",
    "DRREDDY": "Dr Reddy's Labs",
    "EICHERMOT": "Eicher Motors",
    "EQUITASBNK": "Equitas Small Fin Bank",
    "EXIDEIND": "Exide Industries",
    "FEDERALBNK": "Federal Bank",
    "HCLTECH": "HCL Technologies",
    "HDFCBANK": "HDFC Bank",
    "ICICIBANK": "ICICI Bank",
    "IDFCFIRSTB": "IDFC First Bank",
    "INDUSINDBK": "IndusInd Bank",
    "INFY": "Infosys",
    "IOC": "Indian Oil Corp",
    "IRCTC": "IRCTC",
    "ITC": "ITC",
    "ITCHOTELS": "ITC Hotels",
    "KOTAKBANK": "Kotak Bank",
    "KPITTECH": "KPIT Technologies",
    "KTKBANK": "Karnataka Bank",
    "MANAPPURAM": "Manappuram Finance",
    "MOTILALOFS": "Motilal Oswal",
    "MUTHOOTFIN": "Muthoot Finance",
    "NATCOPHARM": "Natco Pharma",
    "ONGC": "ONGC",
    "PPLPHARMA": "Piramal Pharma",
    "SOUTHBANK": "South Indian Bank",
    "STOVEKRAFT": "Stove Kraft",
    "SUNPHARMA": "Sun Pharma",
    "TATACHEM": "Tata Chemicals",
    "TATASTEEL": "Tata Steel",
    "TCS": "TCS",
    "TECHM": "Tech Mahindra",
    "THANGAMAYL": "Thangamayil Jewellery",
    "TMB": "Tamilnadu Merc Bank",
    "TATAMOTORS": "Tata Motors",
    "TRIDENT": "Trident",
    "UJJIVANSFB": "Ujjivan Small Fin Bank",
    "WIPRO": "Wipro",
    "ZYDUSLIFE": "Zydus Lifesciences",
}

# Additional Nifty 50 stocks (outside portfolio) to scan — top 15 by weight
NIFTY50_EXTRA = [
    "RELIANCE", "BHARTIARTL", "SBIN", "LT", "BAJFINANCE",
    "MARUTI", "M%26M", "AXISBANK", "TITAN",
    "NTPC", "ADANIENT", "JSWSTEEL", "BAJAJFINSV",
    "TRENT", "POWERGRID",
]

# ──────────────────────────────────────────────────────────────────────────────
# Screener.in: Fetch shareholding data
# ──────────────────────────────────────────────────────────────────────────────

def get_screener_session() -> requests.Session:
    """Create a requests session for Screener.in."""
    session = requests.Session()
    session.verify = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'close',
    })
    return session


def fetch_shareholding(session: requests.Session, symbol: str) -> dict | None:
    """
    Fetch quarterly FII/DII shareholding % from Screener.in.
    Returns dict with quarterly FII% and DII% arrays, or None on failure.
    """
    # Try consolidated first, then standalone
    for suffix in ['/consolidated/', '/']:
        url = f'https://www.screener.in/company/{symbol}{suffix}'
        try:
            r = session.get(url, timeout=12)
            if r.status_code == 200 and '<section id="shareholding"' in r.text:
                break
        except Exception:
            continue
    else:
        return None

    text = r.text
    sh_start = text.find('<section id="shareholding"')
    if sh_start < 0:
        return None
    sh_end = text.find('</section>', sh_start)
    section = text[sh_start:sh_end]

    # Find quarterly table
    qt = section.find('id="quarterly-shp"')
    if qt < 0:
        return None

    table_start = section.find('<table', qt)
    table_end = section.find('</table>', table_start)
    table = section[table_start:table_end + 8]

    # Extract headers (quarter dates)
    thead = re.search(r'<thead>(.*?)</thead>', table, re.DOTALL)
    if not thead:
        return None
    headers = [
        re.sub(r'<[^>]+>', '', h).strip()
        for h in re.findall(r'<th[^>]*>(.*?)</th>', thead.group(1), re.DOTALL)
    ]

    # Extract data rows
    tbody = re.search(r'<tbody>(.*?)</tbody>', table, re.DOTALL)
    if not tbody:
        return None

    result = {'quarters': headers[1:]}  # skip first empty header
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody.group(1), re.DOTALL)
    for row_html in rows:
        cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row_html, re.DOTALL)
        cells_clean = [re.sub(r'<[^>]+>|\xa0|&nbsp;', '', c).strip() for c in cells]
        if not cells_clean:
            continue

        label = cells_clean[0].upper()
        values = []
        for v in cells_clean[1:]:
            try:
                values.append(float(v.replace('%', '').replace(',', '')))
            except ValueError:
                values.append(None)

        if 'FII' in label or 'FPI' in label:
            result['fii'] = values
        elif 'DII' in label:
            result['dii'] = values
        elif 'PROMOTER' in label:
            result['promoter'] = values

    if 'fii' not in result or 'dii' not in result:
        return None

    return result


def compute_changes(data: dict) -> dict | None:
    """
    Compute quarter-over-quarter FII/DII changes from shareholding data.
    Returns dict with latest and previous quarter values and changes.
    """
    if not data or 'fii' not in data or 'dii' not in data:
        return None

    quarters = data.get('quarters', [])
    fii = data['fii']
    dii = data['dii']

    # Need at least 2 quarters
    if len(fii) < 2 or len(dii) < 2:
        return None

    # Find latest two valid values
    fii_latest = fii[-1]
    fii_prev = fii[-2]
    dii_latest = dii[-1]
    dii_prev = dii[-2]

    if any(v is None for v in [fii_latest, fii_prev, dii_latest, dii_prev]):
        return None

    latest_q = quarters[-1] if quarters else '?'
    prev_q = quarters[-2] if len(quarters) > 1 else '?'

    return {
        'latest_q': latest_q,
        'prev_q': prev_q,
        'fii_now': fii_latest,
        'fii_prev': fii_prev,
        'fii_chg': round(fii_latest - fii_prev, 2),
        'dii_now': dii_latest,
        'dii_prev': dii_prev,
        'dii_chg': round(dii_latest - dii_prev, 2),
    }


# ──────────────────────────────────────────────────────────────────────────────
# NSE: Aggregate FII/DII flows
# ──────────────────────────────────────────────────────────────────────────────

def fetch_nse_fii_dii() -> dict | None:
    """Fetch latest aggregate FII/DII cash market data from NSE."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=_SSL_CTX),
    )
    ua = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')

    url = 'https://www.nseindia.com/api/fiidiiTradeReact'
    req = urllib.request.Request(url, headers={
        'User-Agent': ua,
        'Accept': 'application/json',
    })
    try:
        r = opener.open(req, timeout=10)
        data = json.loads(r.read().decode())
        result = {}
        for item in data:
            cat = item.get('category', '')
            result[cat] = {
                'date': item.get('date', ''),
                'buy': float(item.get('buyValue', 0)),
                'sell': float(item.get('sellValue', 0)),
                'net': float(item.get('netValue', 0)),
            }
        return result
    except Exception as e:
        logger.warning(f"NSE FII/DII fetch failed: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Build digest message
# ──────────────────────────────────────────────────────────────────────────────

def build_fii_dii_digest() -> str:
    """Build the full FII/DII activity digest."""
    now = datetime.now()
    lines = [
        "🏛️ *FII / DII Activity Tracker*",
        f"_Week ending {now.strftime('%d %b %Y')}_\n",
    ]

    # ── Section 1: Aggregate FII/DII flows ──
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 *Aggregate Cash Market Flows*")

    nse_data = fetch_nse_fii_dii()
    if nse_data:
        for cat in ['FII/FPI', 'DII']:
            d = nse_data.get(cat, {})
            if d:
                net = d['net']
                emoji = "🟢" if net > 0 else "🔴"
                label = "FII/FPI" if "FII" in cat else "DII"
                lines.append(
                    f"  {emoji} *{label}* ({d['date']}): "
                    f"Buy ₹{d['buy']:,.0f}Cr | Sell ₹{d['sell']:,.0f}Cr | "
                    f"Net *₹{net:+,.0f}Cr*"
                )
    else:
        lines.append("  _NSE data unavailable_")

    # ── Section 2 & 3: Stock-level changes ──
    session = get_screener_session()

    # Fetch portfolio stocks
    logger.info("Fetching portfolio stock shareholding data...")
    portfolio_changes = []
    for symbol, name in PORTFOLIO_STOCKS.items():
        try:
            data = fetch_shareholding(session, symbol)
            changes = compute_changes(data)
            if changes:
                portfolio_changes.append({
                    'symbol': symbol,
                    'name': name,
                    **changes,
                })
        except Exception as e:
            logger.warning(f"  {symbol}: {e}")
        time.sleep(0.5)  # Rate limit

    logger.info(f"  Got data for {len(portfolio_changes)} portfolio stocks")

    # Fetch Nifty 50 extra stocks
    logger.info("Fetching Nifty 50 extra stock shareholding data...")
    nifty_changes = []
    for symbol in NIFTY50_EXTRA:
        try:
            data = fetch_shareholding(session, symbol)
            changes = compute_changes(data)
            if changes:
                nifty_changes.append({
                    'symbol': symbol,
                    'name': symbol,
                    **changes,
                })
        except Exception as e:
            logger.warning(f"  {symbol}: {e}")
        time.sleep(0.5)

    logger.info(f"  Got data for {len(nifty_changes)} Nifty 50 stocks")

    # ── Section 2: Portfolio FII/DII changes ──
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📁 *Your Portfolio — FII/DII Changes*")

    if portfolio_changes:
        quarter_label = portfolio_changes[0].get('latest_q', '?')
        lines.append(f"_Latest quarter: {quarter_label}_\n")

        # Split into FII increased, FII decreased
        fii_up = sorted([s for s in portfolio_changes if s['fii_chg'] > 0.1],
                        key=lambda x: x['fii_chg'], reverse=True)
        fii_down = sorted([s for s in portfolio_changes if s['fii_chg'] < -0.1],
                          key=lambda x: x['fii_chg'])
        dii_up = sorted([s for s in portfolio_changes if s['dii_chg'] > 0.1],
                        key=lambda x: x['dii_chg'], reverse=True)
        dii_down = sorted([s for s in portfolio_changes if s['dii_chg'] < -0.1],
                          key=lambda x: x['dii_chg'])

        if fii_up:
            lines.append("🟢 *FII Buying (increased stake):*")
            for s in fii_up[:10]:
                lines.append(
                    f"  ▲ {s['name']}: {s['fii_prev']:.1f}% → {s['fii_now']:.1f}% "
                    f"(*+{s['fii_chg']:.2f}%*)"
                )

        if fii_down:
            lines.append("\n🔴 *FII Selling (decreased stake):*")
            for s in fii_down[:10]:
                lines.append(
                    f"  ▼ {s['name']}: {s['fii_prev']:.1f}% → {s['fii_now']:.1f}% "
                    f"(*{s['fii_chg']:.2f}%*)"
                )

        if dii_up:
            lines.append("\n🟢 *DII Buying (increased stake):*")
            for s in dii_up[:10]:
                lines.append(
                    f"  ▲ {s['name']}: {s['dii_prev']:.1f}% → {s['dii_now']:.1f}% "
                    f"(*+{s['dii_chg']:.2f}%*)"
                )

        if dii_down:
            lines.append("\n🔴 *DII Selling (decreased stake):*")
            for s in dii_down[:10]:
                lines.append(
                    f"  ▼ {s['name']}: {s['dii_prev']:.1f}% → {s['dii_now']:.1f}% "
                    f"(*{s['dii_chg']:.2f}%*)"
                )

        if not (fii_up or fii_down or dii_up or dii_down):
            lines.append("  _No significant changes (>0.1%) this quarter_")
    else:
        lines.append("  _Data unavailable_")

    # ── Section 3: Non-portfolio (Nifty 50) FII/DII movers ──
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🌐 *Outside Portfolio — Big FII/DII Moves*")

    if nifty_changes:
        # Combine FII + DII change magnitude, show biggest movers
        fii_movers = sorted(nifty_changes, key=lambda x: abs(x['fii_chg']), reverse=True)
        dii_movers = sorted(nifty_changes, key=lambda x: abs(x['dii_chg']), reverse=True)

        # Top FII moves
        top_fii = [s for s in fii_movers if abs(s['fii_chg']) > 0.2][:8]
        if top_fii:
            lines.append("\n*Top FII Moves:*")
            for s in top_fii:
                emoji = "🟢 ▲" if s['fii_chg'] > 0 else "🔴 ▼"
                lines.append(
                    f"  {emoji} {s['symbol']}: {s['fii_prev']:.1f}% → {s['fii_now']:.1f}% "
                    f"(*{s['fii_chg']:+.2f}%*)"
                )

        # Top DII moves
        top_dii = [s for s in dii_movers if abs(s['dii_chg']) > 0.2][:8]
        if top_dii:
            lines.append("\n*Top DII Moves:*")
            for s in top_dii:
                emoji = "🟢 ▲" if s['dii_chg'] > 0 else "🔴 ▼"
                lines.append(
                    f"  {emoji} {s['symbol']}: {s['dii_prev']:.1f}% → {s['dii_now']:.1f}% "
                    f"(*{s['dii_chg']:+.2f}%*)"
                )

        if not (top_fii or top_dii):
            lines.append("  _No significant moves (>0.2%) this quarter_")
    else:
        lines.append("  _Data unavailable_")

    # Footer
    lines.append(f"\n{'─' * 30}")
    lines.append("_Source: Screener.in (quarterly), NSE (daily)_")
    lines.append(f"_Data reflects latest quarterly disclosures_")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Telegram
# ──────────────────────────────────────────────────────────────────────────────

def send_telegram(text: str) -> bool:
    """Send message via Telegram. Splits if too long."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    messages = []
    if len(text) <= 4000:
        messages = [text]
    else:
        # Split at section boundaries
        parts = text.split("\n━━━━━━━━━━━━━━━━━━━━━━")
        current = parts[0]
        for part in parts[1:]:
            chunk = "\n━━━━━━━━━━━━━━━━━━━━━━" + part
            if len(current) + len(chunk) > 3800:
                messages.append(current)
                current = chunk
            else:
                current += chunk
        if current:
            messages.append(current)

    success = True
    for msg in messages:
        payload = {
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=15, context=_SSL_CTX)
            result = json.loads(resp.read())
            if not result.get("ok"):
                logger.error(f"Telegram send failed: {result}")
                success = False
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            success = False

    return success


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 50)
    logger.info("FII/DII Activity Tracker starting...")
    logger.info("=" * 50)

    try:
        digest = build_fii_dii_digest()
        logger.info(f"Digest built ({len(digest)} chars)")

        if send_telegram(digest):
            logger.info("FII/DII digest sent successfully!")
        else:
            logger.error("Failed to send FII/DII digest")

    except Exception as e:
        logger.error(f"FII/DII Tracker failed: {e}")
        import traceback
        traceback.print_exc()
        try:
            send_telegram(f"⚠️ FII/DII Tracker failed: {str(e)[:200]}")
        except:
            pass


if __name__ == "__main__":
    main()
