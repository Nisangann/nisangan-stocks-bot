#!/usr/bin/env python3
"""
MF Shadow Tracker – Weekly Mutual Fund Portfolio Changes Digest
Sends a weekly summary on Saturday at 12:00 PM tracking portfolio changes
across shadowed mutual funds using Groww API data.

Tracks: new entries, exits, position increases/decreases vs previous month.
"""

import os
import sys
import json
import ssl
import logging
import urllib.request
import warnings
from datetime import datetime, timedelta
from typing import Optional

# Suppress SSL & urllib3 warnings
warnings.filterwarnings('ignore')

# ── Configuration ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
DATA_DIR = os.path.join(SCRIPT_DIR, "mf_data")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "mf_shadow.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8758398799:AAHeDwol7nHrElVEUKbayMsLuVdM6eXoBFk")
CHAT_ID = os.environ.get("CHAT_ID", "927307437")

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# ── Target Mutual Funds ──
# Format: {display_name: groww_slug}
TARGET_FUNDS = {
    "Parag Parikh Flexi Cap": "parag-parikh-long-term-value-fund-direct-growth",
    "HDFC Flexi Cap": "hdfc-equity-fund-direct-growth",
    "Nippon India Multi Cap": "nippon-india-multi-cap-fund-direct-growth",
    "HDFC Multi Cap": "hdfc-multi-cap-fund-direct-growth",
    "HDFC Nifty500 Multicap": "hdfc-nifty500-multicap-50:25:25-index-fund-direct-growth",
    "ICICI Pru Multi Asset": "icici-prudential-dynamic-plan-direct-growth",
    "HDFC Mid Cap": "hdfc-mid-cap-fund-direct-growth",
    "Kotak Midcap": "kotak-emerging-equity-scheme-direct-growth",
    "ICICI Pru Silver ETF FoF": "icici-prudential-silver-etf-fof-direct-growth",
    "Nippon Smallcap 250": "nippon-india-nifty-smallcap-250-index-fund-direct-growth",
    "UTI Nifty 50 Index": "uti-nifty-fund-direct-growth",
}

# ──────────────────────────────────────────────────────────────────────────────
# Groww API
# ──────────────────────────────────────────────────────────────────────────────

def get_groww_session():
    """Create a requests session with Groww cookies."""
    import requests
    session = requests.Session()
    session.verify = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-IN,en;q=0.9',
    })
    try:
        session.get("https://groww.in/mutual-funds", timeout=10)
    except Exception:
        pass
    return session


def fetch_fund_holdings(session, slug: str) -> dict:
    """
    Fetch holdings for a fund from Groww v4 API.
    Returns dict with portfolio_date and list of holdings.
    """
    url = f"https://groww.in/v1/api/data/mf/web/v4/scheme/search/{slug}"
    try:
        r = session.get(url, timeout=15)
        if r.status_code != 200:
            logger.warning(f"Groww API returned {r.status_code} for {slug}")
            return {}

        data = r.json()
        holdings = data.get('holdings', [])
        if not holdings:
            return {}

        portfolio_date = holdings[0].get('portfolio_date', '')[:10]  # YYYY-MM-DD

        # Process only equity holdings with meaningful weight
        processed = []
        for h in holdings:
            if h.get('corpus_per', 0) >= 0.1:  # At least 0.1% of corpus
                processed.append({
                    'name': h['company_name'],
                    'pct': round(h['corpus_per'], 2),
                    'value_cr': round(h.get('market_value', 0), 1),
                    'sector': h.get('sector_name', ''),
                    'type': h.get('instrument_name', ''),
                })

        return {
            'date': portfolio_date,
            'holdings': processed,
            'total_count': len(holdings),
            'aum': data.get('aum', 0),
        }

    except Exception as e:
        logger.error(f"Failed to fetch {slug}: {e}")
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# Portfolio Comparison
# ──────────────────────────────────────────────────────────────────────────────

def load_previous_portfolio(fund_name: str) -> dict:
    """Load the previously saved portfolio for a fund."""
    safe_name = fund_name.replace(' ', '_').replace('/', '_')
    path = os.path.join(DATA_DIR, f"{safe_name}.json")
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}


def save_current_portfolio(fund_name: str, portfolio: dict):
    """Save current portfolio for future comparison."""
    safe_name = fund_name.replace(' ', '_').replace('/', '_')
    path = os.path.join(DATA_DIR, f"{safe_name}.json")
    with open(path, 'w') as f:
        json.dump(portfolio, f, indent=2)


def compare_portfolios(prev: dict, curr: dict) -> dict:
    """
    Compare two portfolio snapshots and detect changes.
    Returns dict with: new_entries, exits, increased, decreased
    """
    if not prev or not curr:
        return {'new_entries': [], 'exits': [], 'increased': [], 'decreased': []}

    prev_holdings = {h['name']: h for h in prev.get('holdings', [])}
    curr_holdings = {h['name']: h for h in curr.get('holdings', [])}

    prev_names = set(prev_holdings.keys())
    curr_names = set(curr_holdings.keys())

    # New entries (not in previous portfolio)
    new_entries = []
    for name in curr_names - prev_names:
        h = curr_holdings[name]
        new_entries.append({
            'name': name,
            'pct': h['pct'],
            'sector': h.get('sector', ''),
        })
    new_entries.sort(key=lambda x: x['pct'], reverse=True)

    # Exits (was in previous, not in current)
    exits = []
    for name in prev_names - curr_names:
        h = prev_holdings[name]
        exits.append({
            'name': name,
            'prev_pct': h['pct'],
            'sector': h.get('sector', ''),
        })
    exits.sort(key=lambda x: x['prev_pct'], reverse=True)

    # Changed positions (present in both)
    increased = []
    decreased = []
    for name in prev_names & curr_names:
        prev_pct = prev_holdings[name]['pct']
        curr_pct = curr_holdings[name]['pct']
        change = curr_pct - prev_pct

        # Only report significant changes (>= 0.3% change)
        if abs(change) >= 0.3:
            entry = {
                'name': name,
                'prev_pct': prev_pct,
                'curr_pct': curr_pct,
                'change': round(change, 2),
            }
            if change > 0:
                increased.append(entry)
            else:
                decreased.append(entry)

    increased.sort(key=lambda x: x['change'], reverse=True)
    decreased.sort(key=lambda x: x['change'])

    return {
        'new_entries': new_entries,
        'exits': exits,
        'increased': increased,
        'decreased': decreased,
        'prev_date': prev.get('date', 'N/A'),
        'curr_date': curr.get('date', 'N/A'),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Message Building
# ──────────────────────────────────────────────────────────────────────────────

def format_fund_changes(fund_name: str, changes: dict, curr: dict) -> list:
    """Format changes for one fund into message lines."""
    lines = []
    has_changes = (changes['new_entries'] or changes['exits']
                   or changes['increased'] or changes['decreased'])

    lines.append(f"\n📊 *{fund_name}*")
    lines.append(f"_Portfolio: {changes.get('curr_date', 'N/A')} | {curr.get('total_count', '?')} stocks_")

    if not has_changes:
        lines.append("  _No significant changes from previous disclosure_")
        return lines

    # New entries
    if changes['new_entries']:
        lines.append("  🆕 *New Entries:*")
        for e in changes['new_entries'][:5]:
            lines.append(f"    • {e['name']} ({e['pct']:.1f}%) — {e['sector']}")

    # Exits
    if changes['exits']:
        lines.append("  🚪 *Exits:*")
        for e in changes['exits'][:5]:
            lines.append(f"    • {e['name']} (was {e['prev_pct']:.1f}%)")

    # Increased positions
    if changes['increased']:
        lines.append("  📈 *Increased:*")
        for e in changes['increased'][:5]:
            lines.append(f"    • {e['name']}: {e['prev_pct']:.1f}% → {e['curr_pct']:.1f}% (+{e['change']:.1f}%)")

    # Decreased positions
    if changes['decreased']:
        lines.append("  📉 *Decreased:*")
        for e in changes['decreased'][:5]:
            lines.append(f"    • {e['name']}: {e['prev_pct']:.1f}% → {e['curr_pct']:.1f}% ({e['change']:.1f}%)")

    return lines


def format_first_snapshot(fund_name: str, curr: dict) -> list:
    """Format first-time snapshot (no previous data to compare)."""
    lines = []
    lines.append(f"\n📊 *{fund_name}*")
    lines.append(f"_Portfolio: {curr.get('date', 'N/A')} | {curr.get('total_count', '?')} stocks | AUM: ₹{curr.get('aum', 0):,.0f} Cr_")
    lines.append("  🔍 *Top 10 Holdings:*")

    for h in curr.get('holdings', [])[:10]:
        lines.append(f"    • {h['name']} — {h['pct']:.1f}% (₹{h['value_cr']:,.0f} Cr)")

    lines.append("  _First snapshot saved. Changes will be tracked from next week._")
    return lines


def build_mf_shadow_digest() -> str:
    """Build the complete MF shadow digest."""
    now = datetime.now()
    lines = [
        "🔍 *MF Shadow Tracker*",
        f"_Week ending {now.strftime('%d %b %Y')}_\n",
        "_Tracking portfolio changes across 11 mutual funds_",
    ]

    session = get_groww_session()
    total_changes = 0
    funds_with_changes = 0

    for fund_name, slug in TARGET_FUNDS.items():
        logger.info(f"Fetching: {fund_name}...")

        curr = fetch_fund_holdings(session, slug)
        if not curr:
            lines.append(f"\n⚠️ *{fund_name}*: _Data unavailable_")
            continue

        prev = load_previous_portfolio(fund_name)

        if prev and prev.get('date') != curr.get('date'):
            # New disclosure available — compare
            changes = compare_portfolios(prev, curr)
            fund_lines = format_fund_changes(fund_name, changes, curr)
            lines.extend(fund_lines)

            n_changes = (len(changes['new_entries']) + len(changes['exits'])
                         + len(changes['increased']) + len(changes['decreased']))
            total_changes += n_changes
            if n_changes > 0:
                funds_with_changes += 1

        elif prev and prev.get('date') == curr.get('date'):
            # Same disclosure, no new data
            lines.append(f"\n📊 *{fund_name}*")
            lines.append(f"_Portfolio: {curr.get('date', 'N/A')} (unchanged since last check)_")
            # Still show top 5 for reference
            top5 = curr.get('holdings', [])[:5]
            top_str = ", ".join(f"{h['name'].split(' ')[0]} ({h['pct']:.1f}%)" for h in top5)
            lines.append(f"  Top 5: {top_str}")

        else:
            # First time — show top holdings and save
            fund_lines = format_first_snapshot(fund_name, curr)
            lines.extend(fund_lines)

        # Save current portfolio for future comparison
        save_current_portfolio(fund_name, curr)

    # Summary footer
    lines.append(f"\n{'─' * 30}")
    if total_changes > 0:
        lines.append(f"_Summary: {total_changes} changes across {funds_with_changes} funds_")
    else:
        lines.append("_No new portfolio disclosures since last check._")
    lines.append(f"_Next update: {(now + timedelta(days=7)).strftime('%d %b %Y')}_")

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
        # Split at fund boundaries (double newline before emoji)
        parts = text.split("\n📊 ")
        current = parts[0]
        for part in parts[1:]:
            chunk = "\n📊 " + part
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
    logger.info("MF Shadow Tracker starting...")
    logger.info("=" * 50)

    try:
        digest = build_mf_shadow_digest()
        logger.info(f"Digest built ({len(digest)} chars)")

        if send_telegram(digest):
            logger.info("MF Shadow digest sent successfully!")
        else:
            logger.error("Failed to send MF Shadow digest")

    except Exception as e:
        logger.error(f"MF Shadow Tracker failed: {e}")
        import traceback
        traceback.print_exc()
        try:
            send_telegram(f"⚠️ MF Shadow Tracker failed: {str(e)[:200]}")
        except:
            pass


if __name__ == "__main__":
    main()
