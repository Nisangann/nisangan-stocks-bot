#!/usr/bin/env python3
"""
Stock Analysis Telegram Bot (Interactive)
Listens for /STOCKNAME commands on Telegram, performs deep analysis:
1. Distance from 52-week high
2. Support levels (pivot-based + swing lows)
3. P/E vs sector P/E
4. P/B ratio
5. Last 4 quarters: Revenue, Operating Profit, EPS
6. Recent news (why it's falling)

Usage: Send "/KPIT" or "/tata chemicals" or "/ITC" to the bot.
"""

import json
import ssl
import csv
import logging
import time
import os
import re
import html as html_mod
import urllib.request
from datetime import datetime

import yfinance as yf

# ── Configuration ──────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8758398799:AAHeDwol7nHrElVEUKbayMsLuVdM6eXoBFk")
CHAT_ID = os.environ.get("CHAT_ID", "927307437")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_CSV = os.path.join(SCRIPT_DIR, "My equities_Sheet1.csv")
SUMMARY_CSV = os.path.join(SCRIPT_DIR, "My equities_Summary.csv")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "stock_analyst.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

POLL_INTERVAL = 2  # seconds between Telegram polls

# ── Stock Name → Symbol Mapping ──────────────────────────────────────────
# Includes portfolio stocks + aliases for flexible matching
SYMBOL_MAP = {
    # Portfolio stocks (name → Yahoo Finance symbol)
    "Amara Raja Batteries": "ARE&M.NS",
    "ARE&M": "ARE&M.NS",
    "Amara Raja": "ARE&M.NS",
    "Aster DM Healthcare": "ASTERDM.NS",
    "Aster DM": "ASTERDM.NS",
    "Aster": "ASTERDM.NS",
    "Canara Bank": "CANBK.NS",
    "CANBK": "CANBK.NS",
    "COALINDIA": "COALINDIA.NS",
    "Coal India": "COALINDIA.NS",
    "Dr Reddy": "DRREDDY.NS",
    "DRREDDY": "DRREDDY.NS",
    "Dr Reddys": "DRREDDY.NS",
    "Eicher Motors": "EICHERMOT.NS",
    "EICHERMOT": "EICHERMOT.NS",
    "Eicher": "EICHERMOT.NS",
    "Equitas Small Fin Bank": "EQUITASBNK.NS",
    "Equitas": "EQUITASBNK.NS",
    "EQUITASBNK": "EQUITASBNK.NS",
    "Exide Ind": "EXIDEIND.NS",
    "Exide": "EXIDEIND.NS",
    "EXIDEIND": "EXIDEIND.NS",
    "Federal Bank": "FEDERALBNK.NS",
    "FEDERALBNK": "FEDERALBNK.NS",
    "HCL Tech": "HCLTECH.NS",
    "HCLTECH": "HCLTECH.NS",
    "HCL": "HCLTECH.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "HDFC": "HDFCBANK.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "ICICI": "ICICIBANK.NS",
    "IDFC First": "IDFCFIRSTB.NS",
    "IDFCFIRSTB": "IDFCFIRSTB.NS",
    "IDFC": "IDFCFIRSTB.NS",
    "INDUSIND Bank": "INDUSINDBK.NS",
    "INDUSINDBK": "INDUSINDBK.NS",
    "IndusInd": "INDUSINDBK.NS",
    "INFY": "INFY.NS",
    "Infosys": "INFY.NS",
    "IOC": "IOC.NS",
    "Indian Oil": "IOC.NS",
    "IRCTC": "IRCTC.NS",
    "ITC": "ITC.NS",
    "ITC HOTELS": "ITCHOTELS.NS",
    "ITCHOTELS": "ITCHOTELS.NS",
    "Kotak bank": "KOTAKBANK.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "Kotak": "KOTAKBANK.NS",
    "Kotak Mahindra": "KOTAKBANK.NS",
    "KPIT TECH": "KPITTECH.NS",
    "KPITTECH": "KPITTECH.NS",
    "KPIT": "KPITTECH.NS",
    "KTK Bank": "KTKBANK.NS",
    "KTKBANK": "KTKBANK.NS",
    "Karnataka Bank": "KTKBANK.NS",
    "Manappuram": "MANAPPURAM.NS",
    "MANAPPURAM": "MANAPPURAM.NS",
    "Motilal Oswald": "MOTILALOFS.NS",
    "MOTILALOFS": "MOTILALOFS.NS",
    "Motilal Oswal": "MOTILALOFS.NS",
    "Motilal": "MOTILALOFS.NS",
    "Muthoot Fin": "MUTHOOTFIN.NS",
    "MUTHOOTFIN": "MUTHOOTFIN.NS",
    "Muthoot": "MUTHOOTFIN.NS",
    "Natco Pharma": "NATCOPHARM.NS",
    "NATCOPHARM": "NATCOPHARM.NS",
    "Natco": "NATCOPHARM.NS",
    "ONGC": "ONGC.NS",
    "Piramal fin": "PPLPHARMA.NS",
    "Piramal": "PPLPHARMA.NS",
    "PPLPHARMA": "PPLPHARMA.NS",
    "South Indian Bank": "SOUTHBANK.NS",
    "SOUTHBANK": "SOUTHBANK.NS",
    "SIB": "SOUTHBANK.NS",
    "Stovekraft": "STOVEKRAFT.NS",
    "STOVEKRAFT": "STOVEKRAFT.NS",
    "Sunpharma": "SUNPHARMA.NS",
    "SUNPHARMA": "SUNPHARMA.NS",
    "Sun Pharma": "SUNPHARMA.NS",
    "Tata Chemicals": "TATACHEM.NS",
    "TATACHEM": "TATACHEM.NS",
    "Tata Chem": "TATACHEM.NS",
    "Tata Steel": "TATASTEEL.NS",
    "TATASTEEL": "TATASTEEL.NS",
    "TCS": "TCS.NS",
    "Tata Consultancy": "TCS.NS",
    "Tech Mahindra": "TECHM.NS",
    "TECHM": "TECHM.NS",
    "TechM": "TECHM.NS",
    "Thangamayil": "THANGAMAYL.NS",
    "THANGAMAYL": "THANGAMAYL.NS",
    "Thangamayil Jewellery": "THANGAMAYL.NS",
    "Tamilnadu mercantile Bank": "TMB.NS",
    "TMB": "TMB.NS",
    "TN Mercantile": "TMB.NS",
    "TMCV": "TMCV.NS",
    "Tata Motors CV": "TMCV.NS",
    "TMPV": "TMPV.NS",
    "Tata Motors PV": "TMPV.NS",
    "Tata Motors": "TMPV.NS",
    "Trident": "TRIDENT.NS",
    "TRIDENT": "TRIDENT.NS",
    "Ujjivan Small Fin Bank": "UJJIVANSFB.NS",
    "UJJIVANSFB": "UJJIVANSFB.NS",
    "Ujjivan": "UJJIVANSFB.NS",
    "Wipro": "WIPRO.NS",
    "WIPRO": "WIPRO.NS",
    "Zydus Life Sciences": "ZYDUSLIFE.NS",
    "ZYDUSLIFE": "ZYDUSLIFE.NS",
    "Zydus": "ZYDUSLIFE.NS",
}

# Sector P/E benchmarks (approximate NSE sector PEs)
SECTOR_PE = {
    "Technology": 28,
    "Financial Services": 18,
    "Healthcare": 32,
    "Consumer Defensive": 35,
    "Industrials": 25,
    "Basic Materials": 15,
    "Energy": 12,
    "Consumer Cyclical": 30,
    "Communication Services": 20,
    "Utilities": 14,
    # Specific Indian sector averages
    "IT": 28,
    "Banking": 14,
    "NBFC": 20,
    "Pharmaceuticals": 32,
    "FMCG": 45,
    "Auto Components": 25,
    "Automobile": 22,
    "Oil & Gas": 12,
    "Metals & Mining": 10,
    "Mining": 10,
    "Chemicals": 25,
    "Textiles": 18,
    "Consumer Durables": 35,
    "Tourism / Railways": 40,
    "Hospitality": 40,
    "Retail / Jewellery": 30,
    "Financial Services": 20,
}


def resolve_symbol(query: str) -> tuple:
    """
    Resolve a user query to a Yahoo Finance symbol.
    Returns (symbol, display_name) or (None, None).
    Supports fuzzy matching: case-insensitive, partial match.
    """
    query_clean = query.strip().strip("/").strip()
    query_lower = query_clean.lower()

    # Exact match (case-insensitive)
    for name, sym in SYMBOL_MAP.items():
        if name.lower() == query_lower:
            return sym, name

    # Partial match — check if query is a substring
    matches = []
    for name, sym in SYMBOL_MAP.items():
        if query_lower in name.lower() or name.lower() in query_lower:
            matches.append((name, sym))

    if len(matches) == 1:
        return matches[0][1], matches[0][0]
    elif len(matches) > 1:
        # Prefer shortest name (most specific match)
        matches.sort(key=lambda x: len(x[0]))
        return matches[0][1], matches[0][0]

    # Try as direct symbol
    if not query_clean.endswith('.NS'):
        test_sym = query_clean.upper() + '.NS'
        try:
            t = yf.Ticker(test_sym)
            price = t.fast_info.last_price
            if price and price > 0:
                return test_sym, query_clean.upper()
        except:
            pass

    return None, None


def load_portfolio_avg(stock_name: str) -> float:
    """Load avg holding price for a stock from portfolio CSV."""
    with open(PORTFOLIO_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Stock", "").strip().lower() == stock_name.lower():
                try:
                    return float(row.get("Avg. holding price", 0))
                except:
                    return 0.0
    return 0.0


def get_sector_from_summary(stock_name: str) -> str:
    """Get industry vertical from Summary CSV."""
    with open(SUMMARY_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Stock", "").strip().lower() == stock_name.lower():
                return row.get("Industry Vertical", "").strip()
    return ""


def calculate_supports(hist) -> dict:
    """Calculate support levels from historical data."""
    if hist is None or hist.empty or len(hist) < 20:
        return {}

    closes = hist['Close'].tolist()
    lows = hist['Low'].tolist()
    dates = hist.index.tolist()
    current = closes[-1]

    # Pivot point based support (last 20 days)
    recent_high = max(closes[-20:])
    recent_low = min(closes[-20:])
    pivot = (recent_high + recent_low + current) / 3
    s1 = 2 * pivot - recent_high
    s2 = pivot - (recent_high - recent_low)

    # Swing lows (local minima) in last 3 months
    swing_lows = []
    for i in range(2, len(lows) - 2):
        if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and
                lows[i] < lows[i+1] and lows[i] < lows[i+2]):
            if lows[i] < current:  # only supports below current price
                swing_lows.append({
                    'price': round(lows[i], 2),
                    'date': dates[i].strftime('%d %b'),
                })

    # Keep only the 3 most recent swing lows
    swing_lows = swing_lows[-3:]

    return {
        'pivot': round(pivot, 2),
        's1': round(s1, 2),
        's2': round(s2, 2),
        'swing_lows': swing_lows,
    }


def fetch_stock_news(stock_name: str, symbol: str) -> list:
    """Fetch recent news about a stock from Google News RSS. Returns list of {title, url}."""
    news = []
    try:
        # Use stock name for search
        search_terms = [stock_name.replace(' ', '+')]
        # Also try the NSE symbol without .NS
        nse_sym = symbol.replace('.NS', '').replace('&', '%26')
        if nse_sym.lower() != stock_name.lower():
            search_terms.append(nse_sym)

        query = '+OR+'.join(search_terms) + '+stock+NSE'
        url = f'https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en'

        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        resp = urllib.request.urlopen(req, timeout=10, context=_SSL_CTX)
        data = resp.read().decode('utf-8', errors='replace')

        # Parse RSS items (title + link)
        items = re.findall(
            r'<item>.*?<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>.*?<link>(.*?)</link>',
            data, re.DOTALL
        )
        if not items:
            # Fallback: separate extraction
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', data)
            links = re.findall(r'<link>(https?://[^<]+)</link>', data)
            if not titles:
                titles = re.findall(r'<title>(.*?)</title>', data)
            items = list(zip(titles, links)) if links else [(t, '') for t in titles]

        for title, link in items[:6]:
            clean_title = html_mod.unescape(title).strip()
            clean_link = link.strip()
            if clean_title and 'Google News' not in clean_title:
                news.append({'title': clean_title, 'url': clean_link})
    except Exception as e:
        logger.warning(f"News fetch failed: {e}")

    return news[:5]


def generate_fall_narrative(info: dict, fast, hist, qi, w52_high: float,
                            cmp: float, sector_vertical: str) -> list:
    """
    Generate a narrative analysis on why the stock is falling.
    Synthesizes: price action, earnings trends, valuation, and sector context.
    """
    lines = []
    reasons = []

    # 1. Magnitude of fall from 52W high
    pct_from_high = ((cmp - w52_high) / w52_high) * 100
    if pct_from_high < -30:
        reasons.append(f"deep correction of {pct_from_high:.0f}% from 52W high (₹{w52_high:,.0f})")
    elif pct_from_high < -15:
        reasons.append(f"significant decline of {pct_from_high:.0f}% from 52W high")

    # 2. Below key moving averages
    if cmp < fast.two_hundred_day_average:
        pct_below_200 = ((cmp - fast.two_hundred_day_average) / fast.two_hundred_day_average) * 100
        reasons.append(f"trading {abs(pct_below_200):.0f}% below 200-DMA — sustained bearish trend")

    # 3. Earnings deterioration
    if qi is not None and not qi.empty:
        if 'Net Income' in qi.index:
            net_profits = qi.loc['Net Income'].head(4).tolist()
            valid = [n for n in net_profits if n and n == n]
            if len(valid) >= 2:
                if valid[0] < valid[-1]:
                    decline_pct = ((valid[0] - valid[-1]) / abs(valid[-1])) * 100
                    if decline_pct < -10:
                        reasons.append(f"net profit declined {decline_pct:.0f}% QoQ (latest ₹{valid[0]/1e7:.0f} Cr vs ₹{valid[-1]/1e7:.0f} Cr)")

        if 'Diluted EPS' in qi.index:
            eps_vals = qi.loc['Diluted EPS'].head(4).tolist()
            valid_eps = [e for e in eps_vals if e and e == e]
            if len(valid_eps) >= 2 and valid_eps[0] < valid_eps[1]:
                reasons.append(f"EPS weakening (₹{valid_eps[0]:.2f} vs ₹{valid_eps[1]:.2f} prev quarter)")

    # 4. Valuation concern
    pe = info.get('trailingPE')
    sector_pe = SECTOR_PE.get(sector_vertical, 25)
    if pe and pe > sector_pe * 1.3:
        reasons.append(f"P/E ({pe:.1f}x) still elevated vs sector ({sector_pe}x) despite the fall — re-rating risk")

    # 5. Promoter / structural issues
    pb = info.get('priceToBook')
    if pb and pb > 5:
        reasons.append(f"expensive on P/B ({pb:.1f}x) — market correcting premium valuations")

    # 6. Recent volume spike (capitulation signal)
    if hist is not None and not hist.empty and len(hist) > 20:
        recent_vol = hist['Volume'].tail(5).mean()
        avg_vol = hist['Volume'].tail(50).mean()
        if recent_vol > avg_vol * 1.5:
            reasons.append("recent volume spike (1.5x above average) — indicates active selling pressure")

    # Build narrative
    if reasons:
        lines.append("  📝 *Analysis:*")
        narrative = f"  {info.get('shortName', 'This stock')} is under pressure due to "
        if len(reasons) == 1:
            narrative += reasons[0] + "."
        elif len(reasons) == 2:
            narrative += reasons[0] + ", compounded by " + reasons[1] + "."
        else:
            narrative += reasons[0] + ". Additionally, " + "; ".join(reasons[1:3]) + "."
        lines.append(narrative)

        # Conclude with actionable insight
        if pct_from_high < -40 and pe and pe < sector_pe:
            lines.append("  💡 _Valuation now below sector avg — potential accumulation zone if earnings stabilize._")
        elif pct_from_high < -30 and qi is not None:
            net_profits = qi.loc['Net Income'].head(4).tolist() if 'Net Income' in qi.index else []
            valid = [n for n in net_profits if n and n == n]
            if len(valid) >= 2 and valid[0] > valid[1]:
                lines.append("  💡 _Despite price fall, latest quarter shows profit recovery — watch for trend confirmation._")
            else:
                lines.append("  ⚠️ _Earnings still declining — wait for stabilization before adding._")
        elif pct_from_high < -20:
            lines.append("  ⏳ _In correction territory. Monitor next quarterly results before building position._")
    else:
        lines.append("  📝 _No significant red flags in fundamentals. Price action likely driven by sector rotation or market-wide correction._")

    return lines


def build_analysis(symbol: str, display_name: str) -> str:
    """Build the full stock analysis message."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        fast = ticker.fast_info

        # Initialize variables used across sections
        hist = None
        qi = None

        # Current price
        cmp = fast.last_price
        if not cmp or cmp <= 0:
            return f"❌ Could not fetch price for {display_name} ({symbol})"

        now = datetime.now().strftime("%d %b %Y, %I:%M %p")
        lines = [f"📊 *Stock Analysis: {info.get('shortName', display_name)}*",
                 f"_Generated at {now}_\n"]

        # ── Section 1: Price & 52-week position ──
        w52_high = info.get('fiftyTwoWeekHigh', fast.year_high)
        w52_low = info.get('fiftyTwoWeekLow', fast.year_low)
        pct_from_high = ((cmp - w52_high) / w52_high) * 100 if w52_high else 0
        pct_from_low = ((cmp - w52_low) / w52_low) * 100 if w52_low else 0

        lines.append("*1️⃣ Price & 52-Week Position*")
        lines.append(f"  • CMP: *₹{cmp:,.2f}*")
        lines.append(f"  • 52W High: ₹{w52_high:,.2f} (*{pct_from_high:+.1f}%*)")
        lines.append(f"  • 52W Low: ₹{w52_low:,.2f} ({pct_from_low:+.1f}%)")
        lines.append(f"  • 50-DMA: ₹{fast.fifty_day_average:,.2f}")
        lines.append(f"  • 200-DMA: ₹{fast.two_hundred_day_average:,.2f}")

        # Portfolio holding comparison
        # Try to match display name to portfolio
        avg_holding = 0
        for pname in SYMBOL_MAP:
            if SYMBOL_MAP[pname] == symbol:
                avg_holding = load_portfolio_avg(pname)
                if avg_holding > 0:
                    break
        if avg_holding > 0:
            pct_from_avg = ((cmp - avg_holding) / avg_holding) * 100
            lines.append(f"  • Your Avg: ₹{avg_holding:,.2f} (*{pct_from_avg:+.1f}% from holding*)")

        # ── Section 2: Support Levels ──
        lines.append("\n*2️⃣ Support Levels*")
        try:
            hist = ticker.history(period="6mo", interval="1d")
            supports = calculate_supports(hist)
            if supports:
                lines.append(f"  • Pivot: ₹{supports['pivot']:,.2f}")
                lines.append(f"  • Support 1 (S1): ₹{supports['s1']:,.2f}")
                lines.append(f"  • Support 2 (S2): ₹{supports['s2']:,.2f}")
                if supports['swing_lows']:
                    lines.append("  • Recent Swing Lows:")
                    for sl in supports['swing_lows']:
                        lines.append(f"    ◦ ₹{sl['price']:,.2f} ({sl['date']})")
            else:
                lines.append("  _Insufficient data for support calculation_")
        except Exception as e:
            lines.append(f"  _Support data unavailable_")

        # Trend signal
        if cmp < fast.fifty_day_average < fast.two_hundred_day_average:
            lines.append("  📉 *Trend: Bearish* (below both 50 & 200 DMA)")
        elif cmp > fast.fifty_day_average > fast.two_hundred_day_average:
            lines.append("  📈 *Trend: Bullish* (above both 50 & 200 DMA)")
        elif cmp > fast.fifty_day_average:
            lines.append("  ↗️ *Trend: Recovery* (above 50 DMA, below 200 DMA)")
        else:
            lines.append("  ↘️ *Trend: Weakening* (below 50 DMA)")

        # ── Section 3: Valuation (P/E & P/B) ──
        lines.append("\n*3️⃣ Valuation*")
        trailing_pe = info.get('trailingPE')
        forward_pe = info.get('forwardPE')
        pb = info.get('priceToBook')
        sector = info.get('sector', '')

        # Get sector P/E
        sector_vertical = get_sector_from_summary(display_name)
        sector_pe = SECTOR_PE.get(sector_vertical) or SECTOR_PE.get(sector, 25)

        if trailing_pe:
            pe_vs_sector = "✅ Below" if trailing_pe < sector_pe else "⚠️ Above"
            lines.append(f"  • Trailing P/E: *{trailing_pe:.1f}* ({pe_vs_sector} sector avg ~{sector_pe})")
        else:
            lines.append("  • Trailing P/E: _N/A_")

        if forward_pe:
            lines.append(f"  • Forward P/E: *{forward_pe:.1f}*")

        if pb:
            pb_status = "Reasonable" if pb < 3 else ("Expensive" if pb > 5 else "Moderate")
            lines.append(f"  • P/B: *{pb:.2f}* ({pb_status})")

        # Additional metrics
        roe = info.get('returnOnEquity')
        debt_eq = info.get('debtToEquity')
        if roe:
            lines.append(f"  • ROE: {roe*100:.1f}%")
        if debt_eq:
            lines.append(f"  • Debt/Equity: {debt_eq:.1f}")

        # ── Section 4: Quarterly Performance ──
        lines.append("\n*4️⃣ Last 4 Quarters*")
        try:
            qi = ticker.quarterly_income_stmt
            if qi is not None and not qi.empty:
                quarters = qi.columns[:4]
                q_labels = [q.strftime('%b %y') for q in quarters]

                lines.append(f"  `{'Quarter':<10}| {''.join(f'{q:>8}' for q in q_labels)}`")
                lines.append(f"  `{'-'*10}|{'-'*32}`")

                # Revenue in Cr
                if 'Total Revenue' in qi.index:
                    revs = qi.loc['Total Revenue'].head(4).tolist()
                    rev_str = ''.join(f'{r/1e7:>8.0f}' if r and r == r else f'{"N/A":>8}' for r in revs)
                    lines.append(f"  `{'Revenue Cr':<10}|{rev_str}`")

                # Operating Income in Cr
                if 'Operating Income' in qi.index:
                    ops = qi.loc['Operating Income'].head(4).tolist()
                    ops_str = ''.join(f'{o/1e7:>8.0f}' if o and o == o else f'{"N/A":>8}' for o in ops)
                    lines.append(f"  `{'Op Profit':<10}|{ops_str}`")

                # Net Income in Cr
                if 'Net Income' in qi.index:
                    nets = qi.loc['Net Income'].head(4).tolist()
                    net_str = ''.join(f'{n/1e7:>8.0f}' if n and n == n else f'{"N/A":>8}' for n in nets)
                    lines.append(f"  `{'Net Profit':<10}|{net_str}`")

                # EPS
                if 'Diluted EPS' in qi.index:
                    eps = qi.loc['Diluted EPS'].head(4).tolist()
                    eps_str = ''.join(f'{e:>8.2f}' if e and e == e else f'{"N/A":>8}' for e in eps)
                    lines.append(f"  `{'EPS':<10}|{eps_str}`")
            else:
                lines.append("  _Quarterly data unavailable_")
        except Exception as e:
            lines.append(f"  _Quarterly data error_")

        # ── Section 5: Why is it falling? (News + Analysis) ──
        lines.append("\n*5️⃣ Recent News / Why the Move?*")

        # Synthesized analysis paragraph
        narrative_lines = generate_fall_narrative(
            info, fast, hist, qi, w52_high, cmp, sector_vertical or sector
        )
        lines.extend(narrative_lines)

        # Hyperlinked news
        news = fetch_stock_news(display_name, symbol)
        if news:
            lines.append("")
            lines.append("  📰 *Key Headlines:*")
            for item in news[:4]:
                headline = item['title'][:90] + "…" if len(item['title']) > 90 else item['title']
                # Escape markdown special chars in headline
                headline = headline.replace('[', '(').replace(']', ')').replace('_', ' ')
                if item['url']:
                    lines.append(f"  • [{headline}]({item['url']})")
                else:
                    lines.append(f"  • {headline}")
        else:
            lines.append("  _No recent news found_")

        # ── Footer ──
        lines.append(f"\n_Sector: {sector_vertical or sector} | Cap: ₹{fast.market_cap/1e9:.0f}B_")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Analysis error for {symbol}: {e}")
        return f"❌ Error analyzing {display_name}: {str(e)[:100]}"


def send_telegram(text: str, reply_to: int = None) -> bool:
    """Send a message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    if reply_to:
        payload["reply_to_message_id"] = reply_to

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=15, context=_SSL_CTX)
        result = json.loads(resp.read())
        return result.get("ok", False)
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def send_typing_action():
    """Send 'typing...' indicator on Telegram."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendChatAction"
    payload = {"chat_id": CHAT_ID, "action": "typing"}
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5, context=_SSL_CTX)
    except:
        pass


def poll_telegram(offset: int = 0) -> tuple:
    """Long-poll Telegram for new messages. Returns (updates, new_offset)."""
    url = (f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
           f"?offset={offset}&timeout=30&allowed_updates=[\"message\"]")
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=35, context=_SSL_CTX)
        data = json.loads(resp.read())
        if data.get("ok"):
            return data.get("result", []), offset
        return [], offset
    except Exception as e:
        logger.warning(f"Poll error: {e}")
        return [], offset


def main():
    """Main polling loop."""
    logger.info("Stock Analyst Bot starting...")
    logger.info("Listening for /STOCKNAME commands...")

    offset = 0

    # Get current offset (skip old messages)
    updates, _ = poll_telegram(offset)
    if updates:
        offset = updates[-1]["update_id"] + 1
        logger.info(f"Skipped {len(updates)} old messages. Starting fresh.")

    while True:
        try:
            updates, _ = poll_telegram(offset)

            for update in updates:
                offset = update["update_id"] + 1

                msg = update.get("message", {})
                text = msg.get("text", "").strip()
                msg_id = msg.get("message_id")
                chat_id = msg.get("chat", {}).get("id")

                # Only respond to messages from our chat
                if str(chat_id) != CHAT_ID:
                    continue

                # Must start with / to be a command
                if not text.startswith("/"):
                    continue

                # Extract stock name (remove the /)
                query = text[1:].strip()

                # Skip bot commands like /start, /help
                if query.lower() in ("start", "help", "stop"):
                    if query.lower() == "help":
                        send_telegram(
                            "📖 *Stock Analysis Bot*\n\n"
                            "Send `/STOCKNAME` to get deep analysis.\n\n"
                            "Examples:\n"
                            "• `/KPIT`\n"
                            "• `/Tata Chemicals`\n"
                            "• `/ITC`\n"
                            "• `/Dr Reddy`\n\n"
                            "Works with portfolio stocks + NSE symbols.\n"
                            "Case-insensitive, partial matches OK."
                        )
                    continue

                logger.info(f"Received query: /{query}")

                # Resolve to symbol
                symbol, display_name = resolve_symbol(query)
                if not symbol:
                    send_telegram(
                        f"❓ Could not find stock matching `{query}`.\n"
                        "Try the full name or NSE symbol (e.g., /KPIT, /Tata Chemicals)",
                        reply_to=msg_id,
                    )
                    continue

                # Send typing indicator
                send_typing_action()

                # Build analysis
                logger.info(f"Analyzing {display_name} ({symbol})...")
                analysis = build_analysis(symbol, display_name)

                # Send response
                if len(analysis) > 4000:
                    # Split at section boundaries
                    parts = analysis.split("\n*")
                    current_part = parts[0]
                    for part in parts[1:]:
                        if len(current_part) + len(part) + 2 > 4000:
                            send_telegram(current_part, reply_to=msg_id)
                            current_part = "*" + part
                        else:
                            current_part += "\n*" + part
                    if current_part:
                        send_telegram(current_part, reply_to=msg_id)
                else:
                    send_telegram(analysis, reply_to=msg_id)

                logger.info(f"Analysis sent for {display_name}")

        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
            break
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
