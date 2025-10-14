# Nifty 50 Scanner - PS60 Strategy for Indian Market

## Overview

The **Nifty 50 Scanner** (`nifty_scanner.py`) is a specialized version of the PS60 breakout scanner adapted for Indian stocks trading on the NSE (National Stock Exchange). It scans Nifty 50 stocks for high-probability breakout setups using the same PS60 methodology.

## ⚠️ IMPORTANT: IBKR Requirements

**Before using this scanner**, you MUST have:

1. **IBKR Account with Indian Market Access**
   - Active Interactive Brokers account
   - NSE (National Stock Exchange) market access enabled
   - Indian market data subscription active

2. **Market Data Subscription**
   - Log in to IBKR Account Management
   - Go to **Settings → Market Data Subscriptions**
   - Add **"Indian Stock Exchange (NSE)"** subscription
   - Verify subscription is active

3. **TWS/Gateway Running**
   - Trader Workstation (TWS) or IB Gateway must be running
   - Port 7497 (paper trading) or 7496 (live trading)
   - API access enabled in TWS settings

## Testing IBKR Support

Before running the scanner, test if your IBKR account supports Indian stocks:

```bash
cd /Users/karthik/projects/DayTrader/stockscanner
python3 test_nifty_connection.py
```

This will test 10 sample Nifty stocks and verify:
- ✓ NSE exchange connectivity
- ✓ Market data availability
- ✓ Contract qualification

## Usage

### Basic Scans

```bash
# Scan all Nifty 50 stocks (50 symbols)
python3 nifty_scanner.py

# Quick scan (top 10 movers)
python3 nifty_scanner.py --category quick

# Scan specific symbols
python3 nifty_scanner.py --symbols RELIANCE TCS HDFCBANK INFY
```

### Sector-Specific Scans

```bash
# IT sector (TCS, INFY, WIPRO, HCLTECH, TECHM)
python3 nifty_scanner.py --category it

# Banking sector (HDFCBANK, ICICIBANK, SBIN, AXISBANK, KOTAKBANK)
python3 nifty_scanner.py --category banking

# Auto sector (MARUTI, TATAMOTORS, M&M, BAJAJ-AUTO, HEROMOTOCO)
python3 nifty_scanner.py --category auto

# Pharma sector (SUNPHARMA, DRREDDY, DIVISLAB, CIPLA)
python3 nifty_scanner.py --category pharma

# FMCG sector (HINDUNILVR, ITC, NESTLEIND, BRITANNIA)
python3 nifty_scanner.py --category fmcg

# Metals sector (TATASTEEL, JSWSTEEL, HINDALCO, COALINDIA)
python3 nifty_scanner.py --category metals

# Energy sector (RELIANCE, ONGC, BPCL, NTPC, POWERGRID)
python3 nifty_scanner.py --category energy

# Finance sector (BAJFINANCE, BAJAJFINSV, SBILIFE)
python3 nifty_scanner.py --category finance
```

### Advanced Options

```bash
# Use custom TWS client ID
python3 nifty_scanner.py --client-id 2000

# Combine options
python3 nifty_scanner.py --category banking --client-id 2000
```

## Output Files

The scanner creates separate output files from the US scanner:

```
output/
├── nifty_scanner_results_YYYYMMDD.csv    # Dated CSV file
├── nifty_scanner_results_YYYYMMDD.json   # Dated JSON file
├── nifty_scanner_results.csv             # Latest CSV
└── nifty_scanner_results.json            # Latest JSON
```

## Key Differences from US Scanner

| Feature | US Scanner | Nifty Scanner |
|---------|-----------|---------------|
| **Exchange** | SMART routing | NSE (National Stock Exchange) |
| **Currency** | USD ($) | INR (₹) |
| **Symbols** | SPY, TSLA, NVDA, etc. | RELIANCE, TCS, INFY, etc. |
| **Output Files** | `scanner_results_*.csv` | `nifty_scanner_results_*.csv` |
| **Client ID** | 1001 (default) | 1002 (default) |
| **Market Hours** | 9:30 AM - 4:00 PM ET | 9:15 AM - 3:30 PM IST |

## Nifty 50 Stock Categories

### Quick Scan (Top 10)
- RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK
- BHARTIARTL, ITC, SBIN, LT, BAJFINANCE

### All Sectors (50 stocks total)
- **IT**: 5 stocks (TCS, INFY, WIPRO, HCLTECH, TECHM)
- **Banking**: 6 stocks (HDFCBANK, ICICIBANK, SBIN, AXISBANK, KOTAKBANK, INDUSINDBK)
- **Auto**: 6 stocks (MARUTI, TATAMOTORS, M&M, BAJAJ-AUTO, HEROMOTOCO, EICHERMOT)
- **Pharma**: 4 stocks (SUNPHARMA, DRREDDY, DIVISLAB, CIPLA)
- **FMCG**: 5 stocks (HINDUNILVR, ITC, NESTLEIND, BRITANNIA, TATACONSUM)
- **Metals**: 5 stocks (TATASTEEL, JSWSTEEL, HINDALCO, COALINDIA, HINDZINC)
- **Energy**: 5 stocks (RELIANCE, ONGC, BPCL, NTPC, POWERGRID)
- **Finance**: 3 stocks (BAJFINANCE, BAJAJFINSV, SBILIFE)
- **Other**: 11 stocks (See `nifty_symbols.py`)

## Troubleshooting

### "Connection failed" Error
**Cause**: TWS/Gateway not running or API not enabled
**Solution**:
1. Start TWS or IB Gateway
2. Go to File → Global Configuration → API → Settings
3. Enable "ActiveX and Socket Clients"
4. Verify port is 7497 (paper) or 7496 (live)

### "Contract not found" Errors
**Cause**: NSE market data subscription not active
**Solution**:
1. Log in to IBKR Account Management
2. Go to Settings → Market Data Subscriptions
3. Add "Indian Stock Exchange (NSE)" subscription
4. Wait 24 hours for activation

### "No data available" Warnings
**Cause**: Stock suspended or delisted
**Solution**: This is normal for inactive stocks. Scanner will skip them.

### Symbol Format Issues
**Cause**: Wrong symbol format (e.g., using Bloomberg or Yahoo format)
**Solution**: Use NSE format as in `nifty_symbols.py`:
- ✓ Correct: `RELIANCE`, `TCS`, `HDFCBANK`
- ✗ Wrong: `RELIANCE.NS`, `TCS.BO`, `HDFCBANK.NSE`

## Market Timing

**NSE Trading Hours**: 9:15 AM - 3:30 PM IST (Indian Standard Time)

**Best Scan Times**:
- **Pre-market**: 8:00-9:00 AM IST (scan for today's setups)
- **After close**: 4:00-6:00 PM IST (scan for next day)

**Note**: The scanner auto-detects market hours based on US Eastern Time. For Indian market, you may need to adjust scan timing manually.

## Expected Results

A typical scan will find:
- **High-score setups (≥40)**: 5-10 stocks
- **Near breakout (<3% from resistance)**: 8-15 stocks
- **High volatility (≥3% ATR)**: 15-25 stocks

The scanner calculates:
- ✓ Support/resistance levels
- ✓ Breakout targets (T1, T2, T3)
- ✓ Risk/reward ratios
- ✓ Relative volume (RVOL)
- ✓ Setup scores (0-100)

## Next Steps

After running the scanner:
1. Review top-scored setups (≥40 score)
2. Verify resistance/support levels make sense
3. Check for news/events affecting the stocks
4. Plan entry/exit points for breakout trades
5. Use the trader module (future) for automated execution

## Support

For issues specific to:
- **IBKR connectivity**: Contact IBKR support
- **Market data subscriptions**: IBKR Account Management
- **Scanner bugs**: Check project documentation

## See Also

- `nifty_symbols.py` - Complete list of Nifty 50 stocks
- `scanner.py` - Original US market scanner
- `test_nifty_connection.py` - IBKR connection tester
- `CLAUDE.md` - Project overview
