#!/usr/bin/env python3
"""
Weekly Portfolio Digest – Dividends, Earnings & Corporate Actions
Sends a comprehensive weekly summary to Telegram every Sunday at 7:00 PM.

Covers:
  1. Upcoming Dividends (ex-dates in next 30 days)
  2. Recent Dividends Paid (last 7 days)
  3. Quarterly Results Summary (latest quarter vs previous)
  4. Upcoming Earnings Dates
  5. Corporate Actions & Key News (buybacks, splits, bonuses)
"""

import os
import sys
import json
import re
import ssl
import csv
import logging
import urllib.request
import html as html_mod
from datetime import datetime, timedelta, date
from typing import Optional

# ── Configuration ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "weekly_digest.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

PORTFOLIO_CSV = os.path.join(SCRIPT_DIR, "My equities_Sheet1.csv")
SUMMARY_CSV = os.path.join(SCRIPT_DIR, "My equities_Summary.csv")

# SSL context for macOS
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# ── Portfolio Stocks (unique symbols only) ──
PORTFOLIO_STOCKS = {
    "Amara Raja": "ARE&M.NS",
    "Aster DM Healthcare": "ASTERDM.NS",
    "Canara Bank": "CANBK.NS",
    "Coal India": "COALINDIA.NS",
    "Dr Reddy": "DRREDDY.NS",
    "Eicher Motors": "EICHERMOT.NS",
    "Equitas SFB": "EQUITASBNK.NS",
    "Exide Ind": "EXIDEIND.NS",
    "Federal Bank": "FEDERALBNK.NS",
    "HCL Tech": "HCLTECH.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "IDFC First": "IDFCFIRSTB.NS",
    "IndusInd Bank": "INDUSINDBK.NS",
    "Infosys": "INFY.NS",
    "Indian Oil": "IOC.NS",
    "IRCTC": "IRCTC.NS",
    "ITC": "ITC.NS",
    "ITC Hotels": "ITCHOTELS.NS",
    "Kotak Bank": "KOTAKBANK.NS",
    "KPIT Tech": "KPITTECH.NS",
    "Karnataka Bank": "KTKBANK.NS",
    "Manappuram": "MANAPPURAM.NS",
    "Motilal Oswal": "MOTILALOFS.NS",
    "Muthoot Fin": "MUTHOOTFIN.NS",
    "Natco Pharma": "NATCOPHARM.NS",
    "ONGC": "ONGC.NS",
    "Piramal Pharma": "PPLPHARMA.NS",
    "South Indian Bank": "SOUTHBANK.NS",
    "Stovekraft": "STOVEKRAFT.NS",
    "Sun Pharma": "SUNPHARMA.NS",
    "Tata Chemicals": "TATACHEM.NS",
    "Tata Steel": "TATASTEEL.NS",
    "TCS": "TCS.NS",
    "Tech Mahindra": "TECHM.NS",
    "Thangamayil": "THANGAMAYL.NS",
    "TMB": "TMB.NS",
    "Tata Motors CV": "TMCV.NS",
    "Tata Motors PV": "TMPV.NS",
    "Trident": "TRIDENT.NS",
    "Ujjivan SFB": "UJJIVANSFB.NS",
    "Wipro": "WIPRO.NS",
    "Zydus Life": "ZYDUSLIFE.NS",
}


# ──────────────────────────────────────────────────────────────────────────────
# Data Fetching
# ──────────────────────────────────────────────────────────────────────────────

def get_yfinance():
    """Import yfinance (lazy import to reduce startup time)."""
    import yfinance as yf
    return yf


def fetch_dividend_data(yf) -> tuple:
    """
    Fetch dividend info for all portfolio stocks.
    Returns (upcoming_dividends, recent_dividends)
    - upcoming: stocks with ex-date in next 30 days
    - recent: dividends paid in last 14 days
    """
    upcoming = []
    recent = []
    today = date.today()
    window_future = today + timedelta(days=30)
    window_past = today - timedelta(days=14)

    for name, symbol in PORTFOLIO_STOCKS.items():
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Check for upcoming ex-dividend date
            ex_div_ts = info.get('exDividendDate')
            if ex_div_ts:
                ex_date = date.fromtimestamp(ex_div_ts)
                div_rate = info.get('lastDividendValue', 0)
                div_yield = info.get('dividendYield', 0)
                cmp = info.get('currentPrice') or info.get('regularMarketPrice', 0)

                if today <= ex_date <= window_future:
                    upcoming.append({
                        'name': name,
                        'symbol': symbol,
                        'ex_date': ex_date,
                        'amount': div_rate,
                        'yield': div_yield * 100 if div_yield else 0,
                        'cmp': cmp,
                    })

            # Check recent dividend history
            divs = ticker.dividends
            if divs is not None and not divs.empty:
                for div_date, amount in divs.tail(3).items():
                    d = div_date.date() if hasattr(div_date, 'date') else div_date
                    if window_past <= d <= today:
                        recent.append({
                            'name': name,
                            'symbol': symbol,
                            'date': d,
                            'amount': amount,
                        })

        except Exception as e:
            logger.warning(f"Dividend fetch failed for {name}: {e}")
            continue

    # Sort upcoming by date
    upcoming.sort(key=lambda x: x['ex_date'])
    recent.sort(key=lambda x: x['date'], reverse=True)

    return upcoming, recent


def fetch_quarterly_summary(yf) -> list:
    """
    Check latest quarterly results for all portfolio stocks.
    Returns list of stocks with notable YoY or QoQ changes.
    """
    results = []

    for name, symbol in PORTFOLIO_STOCKS.items():
        try:
            ticker = yf.Ticker(symbol)
            qi = ticker.quarterly_income_stmt
            if qi is None or qi.empty or len(qi.columns) < 2:
                continue

            latest_q = qi.columns[0]
            prev_q = qi.columns[1]

            # Only consider if latest quarter is within 45 days
            if (date.today() - latest_q.date()).days > 45:
                continue

            # Get metrics
            revenue_new = qi.loc['Total Revenue', latest_q] if 'Total Revenue' in qi.index else None
            revenue_old = qi.loc['Total Revenue', prev_q] if 'Total Revenue' in qi.index else None
            profit_new = qi.loc['Net Income', latest_q] if 'Net Income' in qi.index else None
            profit_old = qi.loc['Net Income', prev_q] if 'Net Income' in qi.index else None

            if revenue_new and revenue_old and revenue_old != 0:
                rev_change = ((revenue_new - revenue_old) / abs(revenue_old)) * 100
            else:
                rev_change = None

            if profit_new and profit_old and profit_old != 0:
                profit_change = ((profit_new - profit_old) / abs(profit_old)) * 100
            else:
                profit_change = None

            # Also check YoY if we have 4+ quarters
            yoy_profit_change = None
            if len(qi.columns) >= 5 and 'Net Income' in qi.index:
                yoy_q = qi.columns[4]
                profit_yoy = qi.loc['Net Income', yoy_q]
                if profit_yoy and profit_yoy != 0 and profit_new:
                    yoy_profit_change = ((profit_new - profit_yoy) / abs(profit_yoy)) * 100

            results.append({
                'name': name,
                'quarter': latest_q.strftime('%b %Y'),
                'revenue_cr': revenue_new / 1e7 if revenue_new else None,
                'profit_cr': profit_new / 1e7 if profit_new else None,
                'rev_change_qoq': rev_change,
                'profit_change_qoq': profit_change,
                'profit_change_yoy': yoy_profit_change,
            })

        except Exception as e:
            logger.warning(f"Quarterly fetch failed for {name}: {e}")
            continue

    # Sort by profit change (most notable first)
    results.sort(key=lambda x: abs(x.get('profit_change_qoq') or 0), reverse=True)
    return results


def fetch_earnings_calendar(yf) -> list:
    """Check upcoming earnings dates for portfolio stocks."""
    upcoming = []
    today = date.today()
    window = today + timedelta(days=30)

    for name, symbol in PORTFOLIO_STOCKS.items():
        try:
            ticker = yf.Ticker(symbol)
            cal = ticker.calendar
            if not cal:
                continue

            earnings_dates = cal.get('Earnings Date', [])
            if earnings_dates:
                for ed in earnings_dates:
                    if isinstance(ed, date) and today <= ed <= window:
                        upcoming.append({
                            'name': name,
                            'date': ed,
                            'eps_est': cal.get('Earnings Average'),
                            'rev_est': cal.get('Revenue Average'),
                        })
                        break
        except Exception as e:
            continue

    upcoming.sort(key=lambda x: x['date'])
    return upcoming


def fetch_corporate_actions_news() -> list:
    """
    Fetch corporate action news (buybacks, bonuses, splits, demergers)
    for portfolio stocks from Google News RSS.
    """
    actions = []
    keywords = ['buyback', 'bonus', 'split', 'demerger', 'rights issue', 'OFS', 'QIP']

    # Build search queries from portfolio stock names
    # Do batches to avoid timeouts
    stock_names = list(PORTFOLIO_STOCKS.keys())

    # Search for corporate action keywords mentioning portfolio stocks
    for keyword in ['buyback', 'bonus+share', 'stock+split', 'demerger', 'rights+issue']:
        try:
            url = (
                f'https://news.google.com/rss/search?'
                f'q={keyword}+NSE+India&hl=en-IN&gl=IN&ceid=IN:en'
            )
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            resp = urllib.request.urlopen(req, timeout=10, context=_SSL_CTX)
            data = resp.read().decode('utf-8', errors='replace')

            # Parse items
            items = re.findall(
                r'<item>.*?<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>',
                data, re.DOTALL
            )

            for title, link, pub_date in items[:5]:
                title_clean = html_mod.unescape(title).strip()
                # Check if this news mentions any of our portfolio stocks
                title_lower = title_clean.lower()
                for stock_name in stock_names:
                    name_parts = stock_name.lower().split()
                    if any(part in title_lower for part in name_parts if len(part) > 3):
                        actions.append({
                            'title': title_clean,
                            'url': link.strip(),
                            'stock': stock_name,
                            'keyword': keyword.replace('+', ' '),
                            'date': pub_date.strip(),
                        })
                        break

        except Exception as e:
            logger.warning(f"Corporate action news fetch failed for '{keyword}': {e}")
            continue

    # Also search for specific stocks with action keywords
    for name, symbol in list(PORTFOLIO_STOCKS.items())[:15]:  # Top 15 to avoid rate limiting
        try:
            search_name = name.replace(' ', '+')
            url = (
                f'https://news.google.com/rss/search?'
                f'q={search_name}+buyback+OR+bonus+OR+split+OR+dividend&hl=en-IN&gl=IN&ceid=IN:en'
            )
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            resp = urllib.request.urlopen(req, timeout=8, context=_SSL_CTX)
            data = resp.read().decode('utf-8', errors='replace')

            items = re.findall(
                r'<item>.*?<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>.*?<link>(.*?)</link>',
                data, re.DOTALL
            )

            for title, link in items[:2]:
                title_clean = html_mod.unescape(title).strip()
                if 'Google News' in title_clean:
                    continue
                # Only include if it mentions a corporate action keyword
                title_lower = title_clean.lower()
                if any(kw in title_lower for kw in keywords):
                    # Deduplicate
                    if not any(a['title'] == title_clean for a in actions):
                        actions.append({
                            'title': title_clean,
                            'url': link.strip(),
                            'stock': name,
                            'keyword': next((kw for kw in keywords if kw in title_lower), 'corporate action'),
                        })

        except Exception as e:
            continue

    return actions[:10]  # Limit to top 10


# ──────────────────────────────────────────────────────────────────────────────
# Message Building
# ──────────────────────────────────────────────────────────────────────────────

def build_weekly_digest() -> str:
    """Build the complete weekly digest message."""
    yf = get_yfinance()

    now = datetime.now()
    lines = [
        f"📅 *Weekly Portfolio Digest*",
        f"_Week ending {now.strftime('%d %b %Y')}_\n",
    ]

    # ── Section 1: Upcoming Dividends ──
    logger.info("Fetching dividend data...")
    upcoming_divs, recent_divs = fetch_dividend_data(yf)

    lines.append("*1️⃣ Upcoming Dividends (Next 30 Days)*")
    if upcoming_divs:
        for d in upcoming_divs:
            yield_str = f" | Yield: {d['yield']:.1f}%" if d['yield'] else ""
            lines.append(
                f"  • *{d['name']}* — ₹{d['amount']:.2f}/share\n"
                f"    Ex-Date: {d['ex_date'].strftime('%d %b')} | CMP: ₹{d['cmp']:,.0f}{yield_str}"
            )
    else:
        lines.append("  _No upcoming ex-dividend dates in next 30 days_")

    # ── Section 2: Recent Dividends Paid ──
    lines.append("\n*2️⃣ Recent Dividends (Last 14 Days)*")
    if recent_divs:
        for d in recent_divs:
            lines.append(f"  • *{d['name']}* — ₹{d['amount']:.2f}/share (Ex: {d['date'].strftime('%d %b')})")
    else:
        lines.append("  _No dividends paid in last 14 days_")

    # ── Section 3: Quarterly Results Summary ──
    logger.info("Fetching quarterly results...")
    quarterly = fetch_quarterly_summary(yf)

    lines.append("\n*3️⃣ Latest Quarterly Results*")
    if quarterly:
        # Show top movers (biggest profit changes)
        shown = 0
        for q in quarterly:
            if shown >= 8:
                break
            profit_str = ""
            if q['profit_cr'] is not None:
                profit_str = f"₹{q['profit_cr']:,.0f} Cr"
            qoq = ""
            if q['profit_change_qoq'] is not None:
                emoji = "📈" if q['profit_change_qoq'] > 0 else "📉"
                qoq = f" ({emoji} {q['profit_change_qoq']:+.0f}% QoQ)"
            yoy = ""
            if q['profit_change_yoy'] is not None:
                yoy = f" | YoY: {q['profit_change_yoy']:+.0f}%"

            if profit_str:
                lines.append(f"  • *{q['name']}* ({q['quarter']})")
                lines.append(f"    Net Profit: {profit_str}{qoq}{yoy}")
                shown += 1
    else:
        lines.append("  _No recent quarterly results (>45 days since last report)_")

    # ── Section 4: Upcoming Earnings Dates ──
    logger.info("Fetching earnings calendar...")
    earnings_cal = fetch_earnings_calendar(yf)

    lines.append("\n*4️⃣ Upcoming Earnings (Next 30 Days)*")
    if earnings_cal:
        for e in earnings_cal:
            est_str = ""
            if e['eps_est']:
                est_str = f" | EPS Est: ₹{e['eps_est']:.2f}"
            lines.append(f"  • *{e['name']}* — {e['date'].strftime('%d %b %Y')}{est_str}")
    else:
        lines.append("  _No upcoming earnings dates found_")

    # ── Section 5: Corporate Actions & Key News ──
    logger.info("Fetching corporate action news...")
    corp_actions = fetch_corporate_actions_news()

    lines.append("\n*5️⃣ Corporate Actions & Key News*")
    if corp_actions:
        for ca in corp_actions[:6]:
            headline = ca['title'][:80] + "…" if len(ca['title']) > 80 else ca['title']
            # Escape markdown chars
            headline = headline.replace('[', '(').replace(']', ')').replace('_', ' ')
            tag = ca['keyword'].upper()
            if ca.get('url'):
                lines.append(f"  • [{headline}]({ca['url']})\n    🏷️ _{tag} — {ca['stock']}_")
            else:
                lines.append(f"  • {headline}\n    🏷️ _{tag} — {ca['stock']}_")
    else:
        lines.append("  _No notable corporate actions this week_")

    # ── Footer ──
    lines.append(f"\n_Portfolio: {len(PORTFOLIO_STOCKS)} stocks tracked_")
    lines.append(f"_Next digest: {(now + timedelta(days=7)).strftime('%d %b %Y')}_")

    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    """Send message via Telegram Bot API. Splits if too long."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    # Telegram has 4096 char limit — split if needed
    messages = []
    if len(text) <= 4000:
        messages = [text]
    else:
        # Split at section boundaries
        parts = text.split("\n*")
        current = parts[0]
        for part in parts[1:]:
            if len(current) + len(part) + 2 > 3800:
                messages.append(current)
                current = "*" + part
            else:
                current += "\n*" + part
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
    logger.info("Weekly Portfolio Digest starting...")
    logger.info("=" * 50)

    try:
        digest = build_weekly_digest()
        logger.info(f"Digest built ({len(digest)} chars)")

        if send_telegram(digest):
            logger.info("Weekly digest sent successfully!")
        else:
            logger.error("Failed to send weekly digest")

    except Exception as e:
        logger.error(f"Weekly digest failed: {e}")
        # Send error notification
        try:
            send_telegram(f"⚠️ Weekly digest failed: {str(e)[:200]}")
        except:
            pass


if __name__ == "__main__":
    main()
