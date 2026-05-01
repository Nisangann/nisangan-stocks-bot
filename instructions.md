# Portfolio Analysis — Steps & Instructions

## Source File
- **Input:** `My equities_Sheet1.csv` — contains stock names, total invested amount, and total units purchased.
- **Output:** `My equities.xlsx` — single Excel workbook with two sheets.

---

## Step 1: Calculate Average Holding Price
- **Formula:** `Avg. holding price = Total invested amount ÷ Total units purchased`
- Added as a new column titled **"Avg. holding price"** next to the units column in **Sheet1**.
- Total portfolio investment: **₹4,44,140.17**

---

## Step 2: Classify Stocks by Industry Vertical
Each stock was classified into an industry sector based on its primary business (referenced from NSE):

| Industry | Stocks |
|---|---|
| Auto Components | Amara Raja Batteries, Exide Ind |
| Automobile | Eicher Motors, TMCV, TMPV |
| Banking | Canara Bank, Equitas Small Fin Bank, Federal Bank, HDFC Bank, ICICI Bank, IDFC First, INDUSIND Bank, Kotak bank, KTK Bank, South Indian Bank, Tamilnadu mercantile Bank, Ujjivan Small Fin Bank |
| Chemicals | Tata Chemicals |
| Consumer Durables | Stovekraft |
| ETF | Goldbees, NIFTYBEES, Silverbees |
| FMCG | ITC |
| Financial Services | Motilal Oswald |
| Healthcare | Aster DM Healthcare |
| Hospitality | ITC HOTELS |
| IT | HCL Tech, INFY, KPIT TECH, TCS, Tech Mahindra, Wipro |
| Metals & Mining | Tata Steel |
| Mining | COALINDIA |
| NBFC | Manappuram, Muthoot Fin, Piramal fin |
| Oil & Gas | IOC, ONGC |
| Pharmaceuticals | Dr Reddy, Natco Pharma, Sunpharma, Zydus Life Sciences |
| Retail / Jewellery | Thangamayil |
| Textiles | Trident |
| Tourism / Railways | IRCTC |

---

## Step 3: Classify Stocks by Market Cap (Nifty Index)
Stocks were classified based on NSE index membership and market capitalization (verified from NSE website, 24-Apr-2026):

| Classification | Count | Stocks |
|---|---|---|
| **Nifty 50 (Largecap)** | 16 | COALINDIA, Dr Reddy, Eicher Motors, HCL Tech, HDFC Bank, ICICI Bank, INFY, ITC, Kotak bank, ONGC, Sunpharma, Tata Steel, TCS, Tech Mahindra, TMPV, Wipro |
| **Largecap** | 5 | Canara Bank, INDUSIND Bank, IOC, Muthoot Fin, Zydus Life Sciences |
| **Midcap** | 14 | Amara Raja Batteries, Aster DM Healthcare, Exide Ind, Federal Bank, IDFC First, IRCTC, ITC HOTELS, KPIT TECH, Manappuram, Motilal Oswald, Natco Pharma, Piramal fin, Tata Chemicals, TMCV |
| **Smallcap** | 8 | Equitas Small Fin Bank, KTK Bank, South Indian Bank, Stovekraft, Thangamayil, Tamilnadu mercantile Bank, Trident, Ujjivan Small Fin Bank |
| **ETF** | 3 | Goldbees, NIFTYBEES, Silverbees |

---

## Step 4: Create Summary Sheet with Investment Breakdown
All classifications were written to the **Summary** sheet in `My equities.xlsx`, including:

1. **Per-stock table** — Stock name, total invested, industry vertical, market cap classification.
2. **Industry vertical breakdown** — Industry, no. of stocks, stock names, total amount invested, % of portfolio.
3. **Market cap breakdown** — Classification, no. of stocks, stock names, total amount invested, % of portfolio.

### Portfolio Allocation by Market Cap
| Classification | Amount Invested | % of Portfolio |
|---|---|---|
| Nifty 50 (Largecap) | ₹1,90,663.93 | 42.93% |
| Largecap | ₹48,162.66 | 10.84% |
| Midcap | ₹1,34,073.78 | 30.19% |
| Smallcap | ₹60,684.85 | 13.66% |
| ETF | ₹10,554.95 | 2.38% |

### Top Industries by Allocation
| Industry | Amount Invested | % of Portfolio |
|---|---|---|
| Banking | ₹1,35,358.05 | 30.48% |
| IT | ₹96,710.70 | 21.77% |
| FMCG | ₹41,956.01 | 9.45% |
| Auto Components | ₹31,480.45 | 7.09% |
| Pharmaceuticals | ₹29,915.55 | 6.74% |

---

## Files in Workspace
| File | Description |
|---|---|
| `My equities_Sheet1.csv` | Original portfolio data (updated with avg. holding price column) |
| `My equities_Summary.csv` | Summary classifications (CSV version) |
| `instructions.md` | This file — documents all steps taken |
| `morning_digest.py` | **Daily morning news digest bot** — runs at 6:45 AM IST |
| `portfolio_monitor.py` | **Hourly price monitor** — runs 11 AM-3 PM on market days |
| `stock_analyst_bot.py` | **Interactive analyst bot** — responds to /STOCKNAME commands 24/7 |
| `logs/digest.log` | Log file for digest bot runs |
| `logs/portfolio_monitor.log` | Log file for portfolio monitor runs |

---

## Step 5: Telegram Stock Alert Bot Setup (1 May 2026)

### Bot Details
| Detail | Value |
|---|---|
| Bot name | Stocks alert |
| Username | @nisangan_market_bot |
| Bot Token | `8758398799:AAHeDwol7nHrElVEUKbayMsLuVdM6eXoBFk` |
| Chat ID | `927307437` |
| Link | https://t.me/nisangan_market_bot |

---

## Step 6: Morning Market Digest — `morning_digest.py`

### What it does
Every morning at 6:45 AM, the script:
1. Waits for internet (retry logic built-in)
2. Scrapes 8 news sources for latest market news
3. Categorizes articles into 9 sections
4. Matches headlines against your portfolio stocks
5. Sends a single formatted digest to Telegram

### News Sources (8 total)
| Source | URL | Tag |
|---|---|---|
| Mint Markets | livemint.com/market/stock-market-news | Mint |
| Mint Commodities | livemint.com/market/commodities | Mint |
| Moneycontrol Markets | moneycontrol.com/news/business/markets/ | MC |
| Moneycontrol Economy | moneycontrol.com/news/business/economy/ | MC |
| ET Markets | economictimes.indiatimes.com/markets/stocks/news | ET |
| Hindu BusinessLine | thehindubusinessline.com/markets/ | BL |
| Mint World News | livemint.com/news/world | Mint |
| Financial Express | financialexpress.com/market/ | FE |

### Message Structure (9 sections)
1. **Time Window** — coverage period (prev day 4 AM to today 4 AM)
2. **Nifty 50 Outlook** — Gift Nifty value, previous close, sentiment signal
3. **Gold & Silver** — 24K gold, 22K gold, silver per gram (INR, Chennai rates from GoodReturns)
4. **Market Movers** — why market may open higher/lower (FII/DII, VIX, technicals)
5. **Your Portfolio in Focus** — news about stocks you hold (matched from CSV)
6. **Stocks Worth Watching** — non-portfolio stocks with buy calls / valuation picks
7. **Geopolitical** — wars, sanctions, global tensions
8. **Earnings — Indian** — Q4 results, dividends, profits
9. **Earnings — Overseas** — Meta, Google, US markets

### Internet Retry Logic
- **Phase 1:** If no internet at 6:45 AM → retry every 10 mins for 1 hour
- **Phase 2:** If still no internet → retry every 20 mins indefinitely until connected
- Digest is sent the moment internet becomes available

### Scheduling (launchd)
- **Plist file:** `~/Library/LaunchAgents/com.nisangan.morningdigest.plist`
- **Schedule:** Daily at 6:45 AM
- **Advantage over cron:** If Mac is asleep, launchd fires the job when Mac wakes up
- **Commands:**
  - Stop: `launchctl unload ~/Library/LaunchAgents/com.nisangan.morningdigest.plist`
  - Start: `launchctl load ~/Library/LaunchAgents/com.nisangan.morningdigest.plist`
  - Check: `launchctl list | grep nisangan`

### Gold/Silver Price Source
- **Primary:** BankBazaar Chennai pages (`bankbazaar.com/gold-rate-chennai.html` + `silver-rate-chennai.html`)
- Embedded JSON `pricesHistory` with daily prices per city (Chennai = cityId 62)
- Gold JSON keys: `22K_1G`, `24K_1G`; Silver key: `1G`
- Shows **retail rates** matching jewellery stores like Lalitha
- **Previous source (deprecated):** GoodReturns Chennai — now returns HTTP 403
- **SSL:** All HTTPS requests use `ssl.CERT_NONE` context to bypass macOS certificate issues

### Known Issues / TODO
- [ ] Gift Nifty signal depends on what data MC/Mint pages have at scrape time — may not always have a clear signal
- [ ] Sources that block scraping: Business Standard, MarketWatch, Yahoo Finance, NDTV Profit, Reuters, Investing.com, Zee Business, GoodReturns (403 since Apr 2026)
- [x] Amara Raja Batteries — renamed to ARE&M (`ARE&M.NS`), now working

---

## Step 7: Portfolio Price Monitor — `portfolio_monitor.py`

### What it does
On every market day (Mon-Fri, excluding NSE holidays), checks live stock prices hourly from 11 AM to 3 PM. Compares current market price against your avg holding price and sends:
1. A full portfolio table (stock, avg price, CMP, % change)
2. A prioritized alert for stocks trading ≥5% below your avg holding

### Schedule
- **Runs at:** 11:00 AM, 12:00 PM, 1:00 PM, 2:00 PM, 3:00 PM
- **Days:** Weekdays only (skips weekends + NSE holidays)
- **Plist:** `~/Library/LaunchAgents/com.nisangan.portfoliomonitor.plist`
- **Commands:**
  - Stop: `launchctl unload ~/Library/LaunchAgents/com.nisangan.portfoliomonitor.plist`
  - Start: `launchctl load ~/Library/LaunchAgents/com.nisangan.portfoliomonitor.plist`

### Price Source
- **yfinance** (Yahoo Finance API with session management)
- Fetches all 43 stocks in batch via `yf.Tickers()`
- Returns real-time/delayed NSE prices

### Alert Priority Sections (in order)
| Priority | Section | Logic |
|---|---|---|
| 1 | 🟢 Midcap Opportunities | Midcaps (non-banking) — you want to build here |
| 2 | 🛡️ Defensive (FMCG/Pharma) | ITC, Sun Pharma, Dr Reddy, Natco, Zydus, Aster |
| 3 | 📈 Largecap & Nifty 50 Dips | Quality largecaps at discount (non-banking) |
| 4 | 🏦 Banking (Overweight) | Already heavy — add only with high conviction |
| 5 | 📋 Others | Everything else |

### Message Format
```
Good day Nisangan, here's an update on your portfolio at {timestamp}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Stock           | Avg   | CMP   | %Chg
----------------|-------|-------|------
ITC             |   350 |   315 | -9.9% 🔴
TCS             |  2859 |  2475 |-13.4% 🔴
...
━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Total Invested: ₹4,44,140
📊 Current Value: ₹X,XX,XXX (+X.X%)

⚠️ STOCKS TRADING ≥5% BELOW YOUR AVG
[prioritized sections...]
```

### Symbol Mapping (NSE → Yahoo)
- 43/43 stocks mapped successfully
- ETFs skipped (Goldbees, Niftybees, Silverbees)
- Amara Raja: `ARE&M.NS` (renamed to Amara Raja Energy & Mobility)
- TMCV → `TMCV.NS`, TMPV → `TMPV.NS` (post-Tata Motors demerger)
- Piramal fin → `PPLPHARMA.NS` (successor entity)

### Dependencies
- `yfinance` (installed in .venv) — handles Yahoo Finance sessions/cookies
- Also pulls in: pandas, numpy, requests, beautifulsoup4, curl_cffi

### Log File
- `logs/portfolio_monitor.log`

---

## Step 8: Interactive Stock Analyst Bot — `stock_analyst_bot.py`

### What it does
A persistent Telegram bot that listens 24/7. When you send `/STOCKNAME`, it replies with deep analysis:
1. **Price & 52-week position** — CMP, 52W high/low, distance from high, 50/200 DMA
2. **Support levels** — Pivot, S1, S2, recent swing lows (local minima)
3. **Valuation** — P/E vs sector P/E, Forward P/E, P/B, ROE, Debt/Equity
4. **Last 4 quarters** — Revenue, Operating Profit, Net Profit, EPS (in Cr)
5. **Recent news** — Why the stock is moving (Google News RSS)

### How to use
Send any of these formats on Telegram:
- `/KPIT` or `/kpit` or `/kpit tech`
- `/Tata Chemicals` or `/tatachem` or `/tata chem`
- `/ITC`, `/Dr Reddy`, `/Wipro`
- `/help` — shows usage guide

**No special formatting needed.** Case-insensitive, partial matches work. The bot matches against both portfolio stock names and NSE symbols.

### Data Sources
| Data Point | Source |
|---|---|
| Live price, 52W high/low, DMA | yfinance (`fast_info`) |
| P/E, P/B, ROE, Debt/Equity | yfinance (`info`) |
| Quarterly financials | yfinance (`quarterly_income_stmt`) |
| Support levels | Calculated from 6-month OHLC history |
| News/sentiment | Google News RSS (India) |

### Scheduling (launchd — always-on)
- **Plist:** `~/Library/LaunchAgents/com.nisangan.stockanalyst.plist`
- **KeepAlive:** true (auto-restarts if it crashes)
- **RunAtLoad:** true (starts on login)
- **Commands:**
  - Stop: `launchctl unload ~/Library/LaunchAgents/com.nisangan.stockanalyst.plist`
  - Start: `launchctl load ~/Library/LaunchAgents/com.nisangan.stockanalyst.plist`
  - Check: `launchctl list | grep nisangan`

### Log File
- `logs/stock_analyst.log`

---

## Step 9: Weekly Portfolio Digest — `weekly_digest.py`

### What it does
Sends a comprehensive weekly portfolio digest to Telegram covering:
1. **Upcoming Dividends** — ex-dates in next 30 days for portfolio stocks
2. **Recent Dividends** — dividends paid in last 30 days
3. **Quarterly Results** — latest revenue, operating profit, net profit for each stock
4. **Earnings Calendar** — upcoming earnings dates
5. **Corporate Action News** — Google News RSS for splits, bonuses, buybacks

### Data Sources
| Data Point | Source |
|---|---|
| Dividends | yfinance (`dividends`) |
| Quarterly financials | yfinance (`quarterly_income_stmt`) |
| Earnings calendar | yfinance (`calendar`) |
| Corporate actions | Google News RSS |

### Scheduling (launchd)
- **Plist:** `~/Library/LaunchAgents/com.nisangan.weeklydigest.plist`
- **Schedule:** Every Sunday at 12:00 PM (noon)
- **Commands:**
  - Stop: `launchctl unload ~/Library/LaunchAgents/com.nisangan.weeklydigest.plist`
  - Start: `launchctl load ~/Library/LaunchAgents/com.nisangan.weeklydigest.plist`

### Log File
- `logs/weekly_digest_stdout.log`

---

## Step 10: MF Shadow Tracker — `mf_shadow.py`

### What it does
Tracks portfolio changes across 11 mutual funds weekly. Compares month-over-month MF disclosures to detect:
- **New entries** — stocks added to fund portfolio
- **Exits** — stocks removed from fund portfolio
- **Increased positions** — allocation increased by ≥0.3%
- **Decreased positions** — allocation decreased by ≥0.3%

On first run, saves baseline snapshots and shows top 10 holdings per fund.

### Funds Tracked
| Fund | Category |
|---|---|
| Parag Parikh Flexi Cap | Flexi Cap |
| HDFC Flexi Cap | Flexi Cap |
| Nippon India Multi Cap | Multi Cap |
| HDFC Multi Cap | Multi Cap |
| HDFC Nifty500 Multicap 50:25:25 | Multi Cap Index |
| ICICI Prudential Multi Asset | Multi Asset |
| HDFC Mid Cap | Mid Cap |
| Kotak Midcap | Mid Cap |
| ICICI Prudential Silver ETF FoF | Commodity |
| Nippon India Nifty Smallcap 250 | Small Cap Index |
| UTI Nifty 50 Index | Large Cap Index |

### Data Source
- **Groww v4 API:** `https://groww.in/v1/api/data/mf/web/v4/scheme/search/{slug}`
- Returns full holdings with: company name, allocation %, market value (Cr), sector, portfolio date
- Requires `requests` session (cookies from main page)

### Data Storage
- Snapshots saved in `mf_data/{Fund_Name}.json`
- Each snapshot contains: holdings list, portfolio date, fetch timestamp

### Scheduling (launchd)
- **Plist:** `~/Library/LaunchAgents/com.nisangan.mfshadow.plist`
- **Schedule:** Every Saturday at 12:00 PM (noon)
- **Commands:**
  - Stop: `launchctl unload ~/Library/LaunchAgents/com.nisangan.mfshadow.plist`
  - Start: `launchctl load ~/Library/LaunchAgents/com.nisangan.mfshadow.plist`

### Log File
- `logs/mfshadow.log`

---

## Step 11: FII/DII Activity Tracker — `fii_dii_tracker.py`

### What it does
Weekly digest showing FII (Foreign Institutional Investors) and DII (Domestic Institutional Investors) shareholding changes at the stock level. Two categories:

1. **Your Portfolio** — FII/DII quarter-over-quarter changes for all 43 portfolio stocks
2. **Outside Portfolio** — Biggest FII/DII moves among top Nifty 50 stocks

Also includes latest aggregate FII/DII cash market flows from NSE.

### Sections
1. **Aggregate Cash Market Flows** — Latest day net buy/sell (NSE)
2. **Portfolio FII/DII Changes** — FII buying/selling, DII buying/selling (sorted by magnitude)
3. **Non-Portfolio Big Moves** — Top FII/DII moves in Nifty 50 stocks you don't own

### Data Sources
| Data Point | Source |
|---|---|
| Stock-level FII/DII % | Screener.in (quarterly shareholding) |
| Aggregate FII/DII flows | NSE `fiidiiTradeReact` API |

### Notes
- Shareholding data is quarterly (updates 4x/year with SEBI disclosures)
- When new quarterly data appears, the digest highlights the changes
- Threshold: >0.1% change for portfolio, >0.2% for non-portfolio
- ~58 stocks scraped per run (~45 seconds)

### Scheduling (launchd)
- **Plist:** `~/Library/LaunchAgents/com.nisangan.fiidii.plist`
- **Schedule:** Every Sunday at 3:00 PM
- **Commands:**
  - Stop: `launchctl unload ~/Library/LaunchAgents/com.nisangan.fiidii.plist`
  - Start: `launchctl load ~/Library/LaunchAgents/com.nisangan.fiidii.plist`

### Log File
- `logs/fii_dii_tracker.log`

---

## Portfolio Analysis Summary (from earlier conversation)

### Vertical Split Rating: 6.5/10
- Banking too heavy at 30.5% (target <20-25%)
- Banking + IT = 52.3% of portfolio (over half in 2 sectors)
- 10 verticals below 2% each (add noise without impact)

### Size/Cap Split Rating: 7.5/10
- Combined Largecap (Nifty 50 + other) = 53.7% — healthy
- Midcap at 30.2% — upper end of range
- Smallcap at 13.7% — within acceptable range
- ETF at 2.4% — too small to matter

### Recommendations
1. Reduce Banking from 30% to ~20%
2. Consolidate tiny positions (<1%) — either size up to 3-5% or exit
3. Bump Nifty 50 allocation to ~50%
4. Consider adding: Renewables/Green Energy, Real Estate, Defence/Capital Goods
