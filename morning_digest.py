#!/usr/bin/env python3
"""
Morning Market Digest Bot
Runs daily at 6:45 AM IST, fetches top market news from multiple sources,
compiles a digest and sends it to Telegram.

Sources: LiveMint, Moneycontrol, Economic Times Markets
"""

import urllib.request
import json
import re
import html
import logging
import time
import socket
import ssl
import csv
from datetime import date, datetime, timedelta

# ── Configuration ──────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8758398799:AAHeDwol7nHrElVEUKbayMsLuVdM6eXoBFk")
CHAT_ID = os.environ.get("CHAT_ID", "927307437")

NEWS_SOURCES = [
    {
        "name": "Mint Markets",
        "url": "https://www.livemint.com/market/stock-market-news",
        "tag": "Mint",
    },
    {
        "name": "Mint Commodities",
        "url": "https://www.livemint.com/market/commodities",
        "tag": "Mint",
    },
    {
        "name": "Moneycontrol Markets",
        "url": "https://www.moneycontrol.com/news/business/markets/",
        "tag": "MC",
    },
    {
        "name": "Moneycontrol Economy",
        "url": "https://www.moneycontrol.com/news/business/economy/",
        "tag": "MC",
    },
    {
        "name": "ET Markets",
        "url": "https://economictimes.indiatimes.com/markets/stocks/news",
        "tag": "ET",
    },
    {
        "name": "Hindu BusinessLine",
        "url": "https://www.thehindubusinessline.com/markets/",
        "tag": "BL",
    },
    {
        "name": "Mint World News",
        "url": "https://www.livemint.com/news/world",
        "tag": "Mint",
    },
    {
        "name": "Financial Express Markets",
        "url": "https://www.financialexpress.com/market/",
        "tag": "FE",
    },
]

MAX_NEWS_ITEMS_PER_SECTION = 3
LOG_FILE = "/Users/nisan-12643/Documents/Stocks/logs/digest.log"
PORTFOLIO_CSV = "/Users/nisan-12643/Documents/Stocks/My equities_Sheet1.csv"
SUMMARY_CSV = "/Users/nisan-12643/Documents/Stocks/My equities_Summary.csv"

# Gift Nifty source (for pre-market outlook)
GIFT_NIFTY_URL = "https://www.moneycontrol.com/indian-indices/gift-nifty-24.html"

# Retry config
# Phase 1: Check every 10 mins for 1 hour
PHASE1_INTERVAL_SECS = 10 * 60   # 10 minutes
PHASE1_DURATION_SECS = 60 * 60   # 1 hour
# Phase 2: Check every 20 mins until connected (no time limit)
PHASE2_INTERVAL_SECS = 20 * 60

# ── Logging ────────────────────────────────────────────────────────────────
import os
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def has_internet(timeout: int = 5) -> bool:
    """Check if internet is reachable by connecting to a reliable host."""
    targets = [("8.8.8.8", 53), ("1.1.1.1", 53), ("www.google.com", 80)]
    for host, port in targets:
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            return True
        except OSError:
            continue
    return False


def wait_for_internet() -> bool:
    """
    Wait for internet connectivity in two phases:
      Phase 1: Check every 10 mins for up to 1 hour.
      Phase 2: If still no internet, check every 30 secs indefinitely
               until connected.
    Always returns True (never gives up).
    """
    if has_internet():
        return True

    # ── Phase 1: every 10 mins for 1 hour ──
    logger.info("No internet. Phase 1: checking every 10 mins for up to 1 hour...")
    start = time.time()
    attempt = 0
    while time.time() - start < PHASE1_DURATION_SECS:
        time.sleep(PHASE1_INTERVAL_SECS)
        attempt += 1
        elapsed = int(time.time() - start)
        if has_internet():
            logger.info(f"Internet available after {elapsed}s (Phase 1, attempt {attempt}).")
            return True
        logger.info(f"Phase 1 attempt {attempt}: still no internet ({elapsed}s elapsed)")

    # ── Phase 2: every 30 secs until connected ──
    logger.info("Phase 1 exhausted. Phase 2: checking every 30s until connected...")
    while True:
        time.sleep(PHASE2_INTERVAL_SECS)
        elapsed = int(time.time() - start)
        if has_internet():
            logger.info(f"Internet available after {elapsed}s (Phase 2).")
            return True
        logger.info(f"Phase 2: still waiting... ({elapsed}s elapsed)")


# SSL context for sites with certificate issues
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def fetch_page(url: str, timeout: int = 15) -> str:
    """Fetch a web page and return its HTML content."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        resp = urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX)
        return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return ""


def extract_articles(page_html: str, source_tag: str) -> list[dict]:
    """
    Extract article headlines and URLs from HTML.
    Returns list of {"title": ..., "url": ..., "tag": ...}
    """
    articles = []
    # Match common patterns: <a href="URL">TITLE</a> within headline tags
    patterns = [
        # Mint / ET style: headline inside <a> inside <h2>/<h3>
        r'<h[23][^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>',
        # Moneycontrol style: <a> with title attr or plain text
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*headline[^"\']*["\'][^>]*>([^<]+)</a>',
        # Generic: <a href="...article/news...">Title</a>
        r'<a[^>]+href=["\']((?:https?://[^"\']*)?/(?:news|market|markets|business)[^"\']*)["\'][^>]*>\s*([^<]{20,150}?)\s*</a>',
    ]
    seen_urls = set()
    for pattern in patterns:
        for match in re.finditer(pattern, page_html, re.IGNORECASE):
            url = match.group(1)
            title = html.unescape(match.group(2)).strip()
            # Filter out navigation links, too-short titles, etc.
            if len(title) < 20 or len(title) > 200:
                continue
            if any(skip in title.lower() for skip in ["more from", "click here", "view all", "advertisement", "subscribe"]):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            articles.append({"title": title, "url": url, "tag": source_tag})

    return articles


def deduplicate_articles(articles: list[dict]) -> list[dict]:
    """Remove duplicate articles based on similar titles."""
    seen = set()
    unique = []
    for a in articles:
        # Normalize title for dedup
        key = re.sub(r"[^a-z0-9]", "", a["title"].lower())[:60]
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


def load_portfolio_stocks() -> list[str]:
    """Load stock names from the portfolio CSV for matching in headlines."""
    stocks = []
    try:
        with open(PORTFOLIO_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row["Stock"].strip()
                if name and name != "Total Amount Invested":
                    stocks.append(name)
    except Exception as e:
        logger.warning(f"Could not load portfolio: {e}")
    return stocks


def get_portfolio_keywords() -> list[str]:
    """Build a list of keywords to match portfolio stocks in headlines."""
    stocks = load_portfolio_stocks()
    keywords = []
    for s in stocks:
        keywords.append(s.lower())
        # Add common short forms
        parts = s.lower().split()
        if len(parts) > 1:
            keywords.append(parts[0])
    # Add some well-known mappings
    extra = {
        "tcs": "tcs", "infy": "infosys", "hcl tech": "hcl", "hdfc bank": "hdfc",
        "icici bank": "icici", "itc": "itc", "coalindia": "coal india",
        "sunpharma": "sun pharma", "kotak bank": "kotak", "wipro": "wipro",
        "indusind bank": "indusind", "idfc first": "idfc", "dr reddy": "dr reddy",
        "eicher motors": "eicher", "federal bank": "federal bank",
        "tech mahindra": "tech mahindra", "tata steel": "tata steel",
        "tata chemicals": "tata chemicals", "ongc": "ongc", "ioc": "indian oil",
        "irctc": "irctc", "kpit tech": "kpit", "muthoot fin": "muthoot",
        "manappuram": "manappuram", "natco pharma": "natco",
        "zydus life": "zydus", "exide ind": "exide", "trident": "trident",
        "stovekraft": "stovekraft", "piramal": "piramal",
    }
    for k, v in extra.items():
        keywords.extend([k, v])
    return list(set(keywords))


def fetch_gift_nifty_signal() -> str:
    """
    Fetch Gift Nifty / pre-market data to estimate market opening direction.
    Scrapes multiple sources for Gift Nifty value and previous Nifty close,
    then computes the expected gap.
    """
    try:
        lines = []

        # ── Try to get Gift Nifty from MC ──
        mc_page = fetch_page("https://www.moneycontrol.com/indian-indices/gift-nifty-24.html")
        if mc_page:
            # Look for Gift Nifty price value
            price_match = re.search(
                r'class=["\'][^"\']*pricupdn[^"\']*["\'][^>]*>\s*([\d,]+\.?\d*)',
                mc_page, re.IGNORECASE
            )
            if not price_match:
                price_match = re.search(
                    r'gift.?nifty[^<]{0,200}?([\d]{2}[,\s]?\d{3}(?:\.\d+)?)',
                    mc_page, re.IGNORECASE
                )
            change_match = re.search(
                r'([\+\-]?\s?\d+\.?\d*)\s*\(\s*([\+\-]?\s?\d+\.?\d*)\s*%\s*\)',
                mc_page
            )

            if price_match:
                gift_val = price_match.group(1).replace(",", "").replace(" ", "")
                lines.append(f"\u2022 Gift Nifty: *{gift_val}*")
                if change_match:
                    chg = change_match.group(1).strip()
                    pct = change_match.group(2).strip()
                    lines.append(f"\u2022 Change: {chg} ({pct}%)")

        # ── Get previous Nifty close from Mint page ──
        mint_page = fetch_page("https://www.livemint.com/market/stock-market-news")
        if mint_page:
            nifty_match = re.search(
                r'nifty.{0,5}50[^<]{0,100}?([\d]{2}[,\s]?\d{3}(?:\.\d+)?)[^<]{0,50}?\(\s*([\-\+]?\d+\.?\d*)\s*%?\s*\)',
                mint_page, re.IGNORECASE
            )
            if nifty_match:
                nifty_val = nifty_match.group(1).replace(",", "").replace(" ", "")
                nifty_pct = nifty_match.group(2)
                lines.append(f"\u2022 Previous Nifty 50 close: *{nifty_val}* ({nifty_pct}%)")

        # ── Scan headlines for direction signals ──
        all_text = (mc_page or "") + (mint_page or "")
        up_signals = len(re.findall(r'open.?higher|gap.?up|positive.?open|bullish.?open', all_text, re.I))
        down_signals = len(re.findall(r'open.?lower|gap.?down|negative.?open|bearish.?open', all_text, re.I))

        if up_signals > down_signals:
            lines.append("\U0001f7e2 Sentiment: *Likely POSITIVE opening*")
        elif down_signals > up_signals:
            lines.append("\U0001f534 Sentiment: *Likely NEGATIVE opening*")
        elif up_signals == 0 and down_signals == 0:
            lines.append("\u26aa Sentiment: No clear pre-market signal yet")
        else:
            lines.append("\U0001f7e1 Sentiment: *Mixed \u2014 may open FLAT*")

        if lines:
            return "\n".join(lines)

        return "\u26a0\ufe0f Gift Nifty data not available \u2014 check manually before 9:15 AM"
    except Exception as e:
        logger.warning(f"Gift Nifty fetch error: {e}")
        return "\u26a0\ufe0f Could not fetch pre-market data"


def fetch_gold_silver_prices() -> str:
    """
    Fetch today's gold (22K, 24K per gram) and silver (per gram) prices in INR.
    Primary source: BankBazaar Chennai pages — they embed structured JSON
    with daily prices per city. Chennai = cityId 62.
    """
    try:
        gold_24k = None
        gold_22k = None
        silver_per_gram = None

        # ── Gold from BankBazaar Chennai ──
        gold_page = fetch_page("https://www.bankbazaar.com/gold-rate-chennai.html")
        if gold_page:
            # JSON embedded: "pricesHistory":[{"date":"...","cityId":62,"prices":{"22K_1G":13900,"24K_1G":14595}}, ...]
            history = re.search(r'"pricesHistory":\[(.+?)\]', gold_page)
            if history:
                try:
                    entries = json.loads('[' + history.group(1) + ']')
                    # Find latest entry for Chennai (cityId 62)
                    for entry in entries:
                        if entry.get('cityId') == 62:
                            prices = entry.get('prices', {})
                            gold_22k = prices.get('22K_1G')
                            gold_24k = prices.get('24K_1G')
                            break
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Gold JSON parse error: {e}")

        # ── Silver from BankBazaar Chennai ──
        silver_page = fetch_page("https://www.bankbazaar.com/silver-rate-chennai.html")
        if silver_page:
            # JSON embedded: "pricesHistory":[{"date":"...","cityId":62,"prices":{"1G":260}}, ...]
            history = re.search(r'"pricesHistory":\[(.+?)\]', silver_page)
            if history:
                try:
                    entries = json.loads('[' + history.group(1) + ']')
                    for entry in entries:
                        if entry.get('cityId') == 62:
                            silver_per_gram = entry.get('prices', {}).get('1G')
                            break
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Silver JSON parse error: {e}")

        # ── Build output ──
        lines = []
        if gold_24k and 8000 <= gold_24k <= 25000:
            lines.append(f"\u2022 Gold (24K): *Rs {gold_24k:,}/gram*")
        if gold_22k and 8000 <= gold_22k <= 25000:
            lines.append(f"\u2022 Gold (22K): *Rs {gold_22k:,}/gram*")
        if not lines:
            lines.append("\u2022 Gold: _Price not available_")

        if silver_per_gram and 100 <= silver_per_gram <= 1000:
            lines.append(f"\u2022 Silver: *Rs {silver_per_gram:,}/gram*")
        else:
            lines.append("\u2022 Silver: _Price not available_")

        lines.append("_Source: BankBazaar (Chennai retail rates)_")
        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"Gold/Silver fetch error: {e}")
        return "\u26a0\ufe0f Could not fetch gold/silver prices"


def categorize_article(title: str) -> str:
    """Categorize an article into the new 8-section structure."""
    title_lower = title.lower()

    # Geopolitical
    geo_keywords = ["iran", "war ", "trump", "geopolit", "sanction", "tariff",
                     "china trade", "russia", "us-", "strait", "hormuz", "nato",
                     "ceasefire", "military", "missile", "nuclear", "invasion",
                     "peace talk", "escalat"]
    for kw in geo_keywords:
        if kw in title_lower:
            return "GEO"

    # Overseas earnings (US/global companies)
    overseas_cos = ["apple", "google", "meta", "amazon", "microsoft", "nvidia",
                    "tesla", "netflix", "goldman", "jpmorgan", "morgan stanley",
                    "wall street", "s&p 500", "nasdaq", "dow jones", "alphabet",
                    "us market", "us stock", "european market", "asian market",
                    "qualcomm", "intel"]
    for kw in overseas_cos:
        if kw in title_lower:
            return "OVERSEAS_EARNINGS"

    # Indian earnings
    earnings_keywords = ["q4", "q1", "q2", "q3", "earnings", "net profit",
                         "revenue", "result", "net loss", "net income", "fy2",
                         "quarterly", "dividend", "buyback"]
    for kw in earnings_keywords:
        if kw in title_lower:
            return "INDIAN_EARNINGS"

    # Market movement reasons (nifty/sensex direction, FII/DII, technical)
    market_keywords = ["nifty", "sensex", "fii", "dii", "rally", "crash",
                       "correction", "bull", "bear", "support", "resistance",
                       "technical", "vix", "market crash", "market rally",
                       "buy the dip", "sell off", "sell in may"]
    for kw in market_keywords:
        if kw in title_lower:
            return "MARKET_MOVERS"

    return "OTHER"


def is_portfolio_stock(title: str, portfolio_keywords: list[str]) -> bool:
    """Check if an article title mentions any portfolio stock."""
    title_lower = title.lower()
    for kw in portfolio_keywords:
        if len(kw) >= 3 and kw in title_lower:
            return True
    return False


def is_valuation_opportunity(title: str) -> bool:
    """Check if an article hints at a valuation opportunity for a non-portfolio stock."""
    title_lower = title.lower()
    opp_keywords = ["undervalued", "buy ", "accumulate", "target price",
                    "upgrade", "outperform", "stock to buy", "stocks to buy",
                    "shares to buy", "add to", "watchlist", "value pick",
                    "multibagger", "breakout", "strong buy", "top pick",
                    "recommend", "bullish"]
    return any(kw in title_lower for kw in opp_keywords)


def build_digest(articles: list[dict]) -> str:
    """Build the formatted Telegram message with the 8-section structure."""
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    date_str = today.strftime("%a, %-d %b %Y")
    cover_from = yesterday.strftime("%-d %b") + " 4:00 AM"
    cover_to = today.strftime("%-d %b") + " 4:00 AM"

    portfolio_kws = get_portfolio_keywords()
    sep = "\u2501" * 22

    # ── Categorize articles ──
    market_movers = []
    portfolio_focus = []
    outside_opportunities = []
    geo_news = []
    indian_earnings = []
    overseas_earnings = []
    other_news = []

    for a in articles:
        cat = categorize_article(a["title"])

        # Check portfolio match regardless of category
        in_portfolio = is_portfolio_stock(a["title"], portfolio_kws)

        if in_portfolio:
            portfolio_focus.append(a)
        elif cat == "GEO":
            geo_news.append(a)
        elif cat == "OVERSEAS_EARNINGS":
            overseas_earnings.append(a)
        elif cat == "INDIAN_EARNINGS":
            indian_earnings.append(a)
        elif cat == "MARKET_MOVERS":
            market_movers.append(a)
        elif is_valuation_opportunity(a["title"]):
            outside_opportunities.append(a)
        else:
            other_news.append(a)

    # ── Fetch Nifty50 outlook ──
    nifty_signal = fetch_gift_nifty_signal()

    # ── Fetch gold/silver prices ──
    gold_silver = fetch_gold_silver_prices()

    # ── Build message ──
    n = MAX_NEWS_ITEMS_PER_SECTION

    def format_articles(art_list, limit):
        lines = []
        for a in art_list[:limit]:
            url = a["url"]
            if not url.startswith("http"):
                url = "https://www.livemint.com" + url
            lines.append(f"\u2022 [{a['title']}]({url}) _{a['tag']}_")
        return lines

    lines = [
        f"Good morning Nisangan! \u2615",
        f"Here's your daily market digest for *{date_str}*",
        f"_Coverage: {cover_from} \u2013 {cover_to}_",
        "",
        sep,
        "",
        # ── Section 1: Time Duration ──
        "\U0001f552 *1. TIME WINDOW*",
        f"News collected from *{cover_from}* to *{cover_to}*",
        "",
        sep,
        "",
        # ── Section 2: Nifty50 Expectations ──
        "\U0001f4c8 *2. NIFTY 50 OUTLOOK*",
        f"{nifty_signal}",
        "",
        sep,
        "",
        # ── Section 3: Gold & Silver Prices ──
        "\U0001f4b0 *3. GOLD & SILVER*",
        f"{gold_silver}",
        "",
        sep,
        "",
        # ── Section 4: Market Movement Reasons ──
        "\U0001f4ca *4. MARKET MOVERS \u2014 Why Higher/Lower?*",
    ]
    if market_movers:
        lines.extend(format_articles(market_movers, n))
    else:
        lines.append("_No major market movement news found._")

    lines.extend(["", sep, ""])

    # ── Section 5: Portfolio Stocks in Focus ──
    lines.append("\U0001f3af *5. YOUR PORTFOLIO IN FOCUS*")
    if portfolio_focus:
        lines.extend(format_articles(portfolio_focus, n))
    else:
        lines.append("_No news about your holdings today._")

    lines.extend(["", sep, ""])

    # ── Section 6: Outside Portfolio Opportunities ──
    lines.append("\U0001f50d *6. STOCKS WORTH WATCHING (Outside Portfolio)*")
    if outside_opportunities:
        lines.extend(format_articles(outside_opportunities, n))
    else:
        lines.append("_No standout valuation opportunities spotted today._")

    lines.extend(["", sep, ""])

    # ── Section 7: Geopolitical ──
    lines.append("\U0001f30d *7. GEOPOLITICAL*")
    if geo_news:
        lines.extend(format_articles(geo_news, n))
    else:
        lines.append("_No major geopolitical developments._")

    lines.extend(["", sep, ""])

    # ── Section 8: Indian Earnings ──
    lines.append("\U0001f4b5 *8. EARNINGS \u2014 Indian Stocks*")
    if indian_earnings:
        lines.extend(format_articles(indian_earnings, n))
    else:
        lines.append("_No earnings news today._")

    lines.extend(["", sep, ""])

    # ── Section 9: Overseas Earnings ──
    lines.append("\U0001f310 *9. EARNINGS \u2014 Overseas*")
    if overseas_earnings:
        lines.extend(format_articles(overseas_earnings, n))
    else:
        lines.append("_No overseas earnings news today._")

    lines.extend(["", sep])
    lines.append("\U0001f916 _Powered by Stock Alert Bot_")

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
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=15, context=_SSL_CTX)
        result = json.loads(resp.read())
        if result.get("ok"):
            logger.info("Digest sent successfully")
            return True
        else:
            logger.error(f"Telegram API error: {result}")
            return False
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


# ── Market Holidays (India 2026-2027) ────────────────────────────────────
# NSE holidays — skip digest on these days
MARKET_HOLIDAYS = {
    # 2026
    date(2026, 1, 26), date(2026, 3, 10), date(2026, 3, 30),
    date(2026, 3, 31), date(2026, 4, 14), date(2026, 4, 18),
    date(2026, 5, 1), date(2026, 6, 17), date(2026, 7, 17),
    date(2026, 8, 15), date(2026, 8, 16), date(2026, 10, 2),
    date(2026, 10, 20), date(2026, 10, 21), date(2026, 11, 5),
    date(2026, 11, 24), date(2026, 12, 25),
    # 2027
    date(2027, 1, 26), date(2027, 3, 11), date(2027, 3, 18),
    date(2027, 3, 30), date(2027, 4, 14), date(2027, 4, 10),
    date(2027, 5, 1), date(2027, 7, 7), date(2027, 8, 15),
    date(2027, 8, 17), date(2027, 10, 2), date(2027, 10, 9),
    date(2027, 10, 10), date(2027, 10, 25), date(2027, 11, 15),
    date(2027, 12, 25),
}


def is_market_day() -> bool:
    """Check if today is a trading day (Mon-Fri, not a holiday)."""
    today = date.today()
    if today.weekday() >= 5:
        logger.info(f"Weekend ({today.strftime('%A')}). Skipping digest.")
        return False
    if today in MARKET_HOLIDAYS:
        logger.info(f"Market holiday ({today}). Skipping digest.")
        return False
    return True


def main():
    logger.info("Starting morning digest...")

    if not is_market_day():
        logger.info("Not a market day. Exiting.")
        return

    # Wait for internet before proceeding
    wait_for_internet()

    all_articles = []
    for source in NEWS_SOURCES:
        logger.info(f"Fetching {source['name']}...")
        page = fetch_page(source["url"])
        if page:
            articles = extract_articles(page, source["tag"])
            logger.info(f"  Found {len(articles)} articles from {source['name']}")
            all_articles.extend(articles)

    if not all_articles:
        logger.warning("No articles found from any source. Sending fallback message.")
        send_telegram(
            "\U0001f4f0 *MORNING MARKET DIGEST*\n\n"
            "\u26a0\ufe0f Could not fetch news from any source today. "
            "Please check manually:\n"
            "\u2022 [Mint Markets](https://www.livemint.com/market)\n"
            "\u2022 [Moneycontrol](https://www.moneycontrol.com/news/business/markets/)\n"
            "\u2022 [ET Markets](https://economictimes.indiatimes.com/markets)"
        )
        return

    # Deduplicate
    unique_articles = deduplicate_articles(all_articles)
    logger.info(f"Total unique articles: {len(unique_articles)}")

    # Build and send
    digest = build_digest(unique_articles)
    send_telegram(digest)
    logger.info("Done.")


if __name__ == "__main__":
    main()
