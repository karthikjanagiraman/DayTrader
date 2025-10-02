# PS60 Breakout Scanner - Unified Trading System

## Project Overview

This project is a **PS60 Breakout Scanner** designed for identifying high-probability trading setups. The scanner analyzes stocks for breakout opportunities, providing detailed reasoning for resistance/support levels and calculating price targets using measured moves. It's optimized for day trading with real-time IBKR data integration.

**Latest Update**: September 29, 2025
- Single unified scanner implementation (scanner.py)
- Enhanced breakout analysis with reasoning
- Room-to-run calculations with 3 target levels
- Risk/reward ratio analysis
- Smart support/resistance detection filtering outliers

## Core Requirements

### 1. Functional Requirements

#### Scan Timing
- **Primary scan**: 8:00-9:30 AM ET (pre-market hours)
- **Optional intraday update**: 10:00 AM ET to catch new movers
- **Automatic scheduling** or manual trigger via UI
- **Pre-scan validation**: Verify IBKR connection and market data subscriptions

#### Stock Universe
- **Default**: Major index components (NASDAQ-100, S&P 500)
- **Configurable filters**:
  - Minimum price: $5
  - Minimum average daily volume: 200,000 shares
  - Custom watchlist support
  - Sector/industry filtering

#### Data Collection (Per Stock)
- **Pre-market data**: Last price, volume, bid/ask spreads
- **Gap percentage**: (Current Price - Previous Close) / Previous Close × 100
- **Previous day levels**: Close, high, low
- **Technical indicators**:
  - Moving averages: 5, 10, 20, 50, 100, 200-day SMA
  - Bollinger Bands (20-period, 2σ)
  - 30-period linear regression (60-min chart)
- **Relative Volume (RVOL)**: Current volume / Average volume
- **News and events**: Earnings, upgrades, FDA approvals, M&A

#### Filtering Criteria
1. **Gap Filter**: Stocks with ≥2% pre-market gap
2. **Volume Filter**: RVOL ≥ 2.0 (twice normal volume)
3. **Chart Patterns**:
   - Multi-week bases approaching breakout
   - Previous day consolidations
   - Double/triple tops or bottoms
4. **Room to Run Check**: No major resistance within 1% (for longs)
5. **News Catalysts**: Flag stocks with significant overnight news
6. **Market Context**: Consider index futures direction

#### Output Requirements
- **Pivot Watchlist** (CSV/JSON):
  - Symbol
  - Pivot High (long entry trigger - usually yesterday's high)
  - Pivot Low (short entry trigger - usually yesterday's low)
  - Gap percentage
  - RVOL
  - News flags
  - Next resistance/support levels
  - Rationale (human-readable explanation)
- **Market Summary**: Index futures status, overall bias (bullish/bearish/neutral)
- **Research Log**: Detailed Markdown audit trail of scan reasoning

### 2. PS60 Strategy Rules

#### Entry Conditions
- **Long trades**: Price breaks above pivot high with 60-min candle confirmation
- **Short trades**: Price breaks below pivot low with 60-min candle confirmation
- **Critical decision time**: 10:00 AM (next 60-min candle)

#### Pivot Calculation
- **Default pivot high**: Yesterday's high
- **Default pivot low**: Yesterday's low
- **Exception**: If pre-market already exceeded pivot, use first hour (9:30-10:30 AM) high/low

#### Risk Management
- 5-7 minute time stops at resistance
- Don't chase pivots moved >$0.16 from entry
- Consider overall market environment
- Minimum 1:1 risk/reward ratio

## Current Implementation Status

### ✅ Completed Features
1. **Unified Scanner (scanner.py)**
   - Single consolidated implementation
   - Command-line interface with arguments
   - Category-based scanning (indices, tech, meme stocks, etc.)
   - Configurable client ID

2. **Smart Support/Resistance Calculation**
   - Filters outliers using quantiles (10th/90th percentile)
   - Uses 5-day levels for near-term trading
   - Considers moving averages as dynamic support
   - Avoids flash crash/outlier contamination

3. **Breakout Analysis with Reasoning**
   - Explains WHY a level is significant:
     - Number of times tested (e.g., "Tested 3x")
     - Historical significance (5/10/20-day high)
     - Psychological levels (round numbers)
     - Pattern detection (consolidation, flat-top)

4. **Room to Run Calculations**
   - Three target levels using measured moves:
     - T1: Resistance + 50% of range (Conservative)
     - T2: Resistance + 100% of range (Standard)
     - T3: Resistance + 161.8% of range (Fibonacci)
   - Downside targets if support breaks

5. **Risk/Reward Analysis**
   - Calculates potential gain % to target
   - Calculates risk % to support
   - Provides R/R ratio for each setup
   - Bonus scoring for high R/R ratios

### 🔧 Technical Architecture

```
┌─────────────────┐
│   scanner.py    │ ──> Main unified scanner
└────────┬────────┘
         │
┌────────▼────────┐
│ PS60Scanner     │ ──> Core scanner class
└────────┬────────┘
         │
    ┌────┴────┬──────────┬───────────┐
    │         │          │           │
┌───▼──┐ ┌───▼────┐ ┌───▼────┐ ┌────▼────┐
│ IBKR │ │Analysis│ │Targets │ │ Output  │
│ API  │ │Engine  │ │Calc    │ │CSV/JSON │
└──────┘ └────────┘ └────────┘ └─────────┘
```

### Technology Stack

#### Core Libraries
- **ib_async** (successor to ib_insync): IBKR API integration
- **pandas**: Data manipulation and analysis
- **pandas-ta**: Technical indicators (130+ indicators)
- **numpy**: Numerical computations
- **yfinance**: Backup data source for market data
- **schedule/APScheduler**: Job scheduling

#### Data Sources
- **Primary**: Interactive Brokers TWS/Gateway API
- **Backup**: Yahoo Finance (yfinance)
- **News**: IBKR news feed, Finnhub, or IEX Cloud

### Implementation Details

#### IBKR Connection
- Paper trading: Port 7497
- Live trading: Port 7496
- API limits:
  - Max 100 concurrent market data lines
  - Max 50 historical data requests
  - Respect pacing limits

#### Data Processing Pipeline
1. Fetch pre-market quotes (Level I data)
2. Retrieve historical bars (daily + 60-min)
3. Calculate technical indicators
4. Identify chart patterns
5. Compute gap% and RVOL
6. Check news feeds
7. Apply filters
8. Generate output files

## Usage Instructions

### Basic Usage
```bash
# Run full scan (all symbols)
python scanner.py

# Quick scan (top movers only)
python scanner.py --category quick

# Scan specific symbols
python scanner.py --symbols TSLA NVDA AMD GME

# Scan by category
python scanner.py --category mega_tech
python scanner.py --category meme
python scanner.py --category high_vol

# Custom client ID
python scanner.py --client-id 2000
```

### Output Files
- `output/scanner_results.csv` - Full results in CSV format
- `output/scanner_results.json` - JSON format for API integration

### Categories Available
- `all` - All symbols (~70 stocks)
- `quick` - Top 8 movers for quick analysis
- `indices` - SPY, QQQ, IWM, DIA
- `mega_tech` - AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA
- `semis` - AMD, INTC, MU, QCOM, AVGO, AMAT, LRCX, ARM
- `high_vol` - COIN, PLTR, SOFI, HOOD, ROKU, SNAP, PINS, RBLX
- `meme` - GME, AMC, BB, BBBY, CLOV
- `finance` - JPM, BAC, GS, MS, C, WFC
- `energy` - XOM, CVX, OXY
- `china` - BABA, JD, BIDU, NIO, LI, XPEV

## Configuration Parameters

```yaml
# Example configuration structure
scan_config:
  schedule:
    pre_market: "08:00"
    intraday: "10:00"
    enabled: true

  universe:
    indexes: ["NASDAQ100", "SP500"]
    min_price: 5.0
    min_volume: 200000
    custom_symbols: []

  filters:
    gap_threshold: 2.0  # percent
    rvol_threshold: 2.0
    room_to_run_pct: 1.0

  ibkr:
    host: "127.0.0.1"
    port: 7497  # paper trading
    client_id: 1

  output:
    watchlist_path: "./output/watchlist.csv"
    research_log: "./output/research.md"
    format: ["csv", "json", "markdown"]
```

## Critical Implementation Notes

### Data Quality
- Always validate pre-market data availability
- Handle missing data gracefully
- Use multiple data sources for redundancy
- Implement data sanity checks

### Performance Optimization
- Batch API requests when possible
- Implement caching for historical data
- Use async/await for concurrent operations
- Complete scan before 9:30 AM market open

### Error Handling
- Retry failed API calls with exponential backoff
- Log all errors with context
- Fallback to backup data sources
- Alert on critical failures

### Testing Strategy
- Unit test each module independently
- Integration test with paper trading account
- Backtest filter effectiveness
- Validate pivot calculations
- Compare results with manual analysis

## Research Tasks Before Implementation

Before starting development, research these topics if unfamiliar:

1. **PS60 Trading Strategy**: Deep dive into Dan Shapiro's methodology
2. **IBKR API Documentation**: Study connection, data retrieval, and limits
3. **Technical Indicators**: Understand calculation methods for each indicator
4. **Chart Pattern Recognition**: Algorithm design for base/breakout detection
5. **Pre-market Trading Dynamics**: Liquidity, spreads, and data availability
6. **News API Integration**: Real-time news feed processing

## Success Metrics

- Scanner completes within 5 minutes
- Identifies 5-15 high-quality candidates daily
- Pivot accuracy >90% (validated against actual breakouts)
- Zero missed major movers (gap >5% with volume)
- System uptime >99% during market hours

## Next Steps

1. **Environment Setup**: Install Python 3.11+, required libraries
2. **IBKR Account**: Ensure API access, market data subscriptions
3. **Project Structure**: Create modular codebase following architecture
4. **Incremental Development**: Start with basic scanner, add features progressively
5. **Testing**: Paper trade for minimum 2 weeks before live deployment

## Important Trading Concepts

### Gap Trading
- **Common Gap**: <2%, often fills during session
- **Breakaway Gap**: >2% with volume, trend continuation signal
- **Exhaustion Gap**: End of trend reversal signal

### Relative Volume (RVOL)
- RVOL = Current Volume / Average Volume
- RVOL >2.0 indicates "stock in play"
- RVOL >3.5 suggests institutional interest

### Support/Resistance Levels
- **Pivot Points**: (High + Low + Close) / 3
- **Moving Averages**: Dynamic support/resistance
- **Previous highs/lows**: Static levels

### Risk Management
- Position size: Risk 1-2% per trade
- Stop loss: Below support for longs, above resistance for shorts
- Profit target: Minimum 2:1 reward/risk ratio

## Compliance & Best Practices

- Never log sensitive credentials
- Implement rate limiting for API calls
- Respect market data redistribution rules
- Maintain audit trail for all trades
- Follow IBKR terms of service
- Implement circuit breakers for unusual market conditions

## STRICT IMPLEMENTATION INSTRUCTIONS

### DO NOT:
1. **Use shortcuts or simplifications** not specified in requirements
2. **Substitute data sources** (e.g., DO NOT use yfinance when IBKR is specified)
3. **Make architectural decisions** not explicitly stated in requirements
4. **Add features or optimizations** not requested
5. **Skip implementation details** mentioned in requirements
6. **NEVER use simulated, fake, or generated data** - all data must come from real sources
7. **NEVER create demo versions with fake data** - only use actual market data from IBKR
8. **NEVER create multiple versions of the scanner** - always update existing files in place
   - DO NOT create scanner_v2.py, scanner_improved.py, scanner_optimized.py, etc.
   - ONLY create a new version if explicitly asked to "fork" or "create a new version"
   - Keep the project clean with a single scanner implementation

9. **NEVER take shortcuts or create simplified versions when there are issues**
   - DO NOT create "simple", "quick", "test", or "demo" versions to avoid problems
   - DO NOT bypass the main scanner when it has issues
   - ALWAYS fix the root cause of problems in the main scanner
   - If the main scanner has timeout issues, fix the timeout issues - don't create a simpler version
   - If there are performance problems, optimize the existing code - don't create a stripped-down alternative
   - The user expects the FULL functionality to work properly, not simplified workarounds
   - When asked to "run the scanner", use the MAIN scanner (src/scanner.py), not a simplified version

### ALWAYS:
1. **Follow the exact requirements** as documented
2. **Use IBKR API as primary data source** - no substitutions
3. **Implement all specified components** even if complex
4. **Maintain the specified architecture** without modifications
5. **Request clarification** if requirements are ambiguous
6. **Build exactly what is specified** - no more, no less

### Historical Data Testing Mode:
- For initial development, the scanner should accept a date parameter
- Fetch REAL historical data for that specific date from IBKR only
- Use actual historical pre-market data from IBKR (no simulation)
- Output results based on real historical data
- This allows testing without waiting for live pre-market hours
- If IBKR connection is not available, clearly state this and DO NOT proceed with fake data

---

## Project Structure

```
stockscanner/
├── scanner.py              # Main unified scanner (ONLY scanner file)
├── CLAUDE.md              # This documentation file
├── IBKR_API_SETUP.md      # TWS configuration guide
├── requirements.txt       # Python dependencies
├── output/               # Scanner results directory
│   ├── scanner_results.csv
│   └── scanner_results.json
├── archive/              # Old scanner versions (archived)
└── src/                  # Module structure (if needed)
    └── modules/
```

## Recent Fixes & Improvements (Sept 29, 2025)

### 1. Fixed TSLA Support Level Issue
- **Problem**: Support was showing $325 (26% below price) due to Sept 2 outlier
- **Solution**: Implemented smart filtering using quantiles and moving averages
- **Result**: Support now correctly shows $415-427 range (5-6% below)

### 2. Added Breakout Reasoning
- **Problem**: No explanation for why resistance levels matter
- **Solution**: Added analysis showing:
  - How many times level was tested
  - Historical significance (5/10/20-day highs)
  - Psychological round numbers
  - Pattern detection

### 3. Room to Run Calculations
- **Problem**: No price targets after breakout
- **Solution**: Added measured move targets:
  - T1: Conservative (+50% of range)
  - T2: Standard (+100% of range)
  - T3: Extended (+161.8% Fibonacci)

### 4. Project Cleanup
- **Problem**: Multiple scanner versions causing confusion
- **Solution**: Consolidated to single scanner.py file
- **Archived**: All old versions moved to archive/ folder

## TWS Configuration Requirements

For the scanner to work, TWS must be configured properly:

1. **File → Global Configuration → API → Settings**
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Socket port: 7497 (paper) or 7496 (live)
   - ✅ Trusted IP Addresses: Add 127.0.0.1
   - ❌ Read-Only API (must be unchecked)

2. **If Connection Issues**
   - Restart TWS after configuration changes
   - Check IBKR_API_SETUP.md for detailed troubleshooting

## Key Algorithms

### Support/Resistance Calculation
```python
# Smart support selection (avoids outliers)
if current_price > sma_10 and within_10_percent:
    support = sma_10  # Use moving average
elif support_5d_within_10_percent:
    support = support_5d  # Use 5-day low
else:
    support = quantile_10  # Use 10th percentile (filters outliers)
```

### Breakout Scoring System
- Momentum: +30 pts for >3% move
- Volume: +30 pts for RVOL >2.0
- Volatility: +20 pts for ATR >4%
- Proximity: +25 pts if <2% from breakout
- Risk/Reward: +20 pts for R/R >3:1
- Maximum Score: 100+ points

*This document serves as the central reference for the PS60 Scanner project. Last updated: September 29, 2025*