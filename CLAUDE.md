# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DayTrader** is an automated trading system implementing Dan Shapiro's **PS60 Process** for day trading. The project consists of two main modules:

1. **stockscanner** - Pre-market scanner that identifies high-probability breakout setups
2. **trader** (to be built) - Automated trading module that executes trades based on PS60 methodology using scanner output

## Project Structure

```
DayTrader/
├── stockscanner/              # Pre-market scanner (completed)
│   ├── scanner.py            # Main scanner script
│   ├── config/               # YAML configuration files
│   ├── output/               # Scanner results (CSV/JSON)
│   └── CLAUDE.md            # Scanner-specific documentation
│
├── trader/                   # Trading module (in progress)
│   ├── trader.py            # Main live trading engine
│   ├── position_manager.py  # Position sizing and risk management
│   ├── order_executor.py    # IBKR order execution
│   ├── backtest/            # Backtesting framework
│   │   └── backtester.py    # Historical 1-min bar backtester
│   ├── config/              # Trading configuration
│   │   └── trader_config.yaml
│   └── logs/                # Trade logs and performance
│
└── PS60ProcessComprehensiveDayTradingGuide.md  # Complete PS60 theory
```

## PS60 Trading Methodology (Scanner-Driven Implementation)

This implementation focuses on **Scenario 1: Trading Scanner-Identified Pivots**. The scanner runs pre-market and identifies resistance/support levels from historical data. The trader monitors these pre-defined pivots and enters immediately when they break.

### Core Concepts

**Scanner-Defined Pivots**: The scanner analyzes historical data and identifies:
- **Resistance** (long pivot): Key level tested multiple times, distance to breakout
- **Support** (short pivot): Key support level, downside risk
- **Targets**: T1, T2, T3 calculated using measured moves
- **Risk/Reward**: Pre-calculated ratios for each setup

**Trading Approach**:
- Scanner runs **pre-market** (8:00 AM) or previous evening
- Pivots are **already defined** before market open
- Trader monitors **tick-by-tick** from 9:30 AM onwards
- Enter **immediately** when scanner-identified pivot breaks
- No need to wait for 60-minute candles (pivots already known)

**Supply & Demand Theory**: Stocks move from resistance to resistance (supply) or support to support (demand). Only trade when there's "air" to the next technical level (scanner calculates this as `dist_to_R%` and `dist_to_S%`).

### Entry Logic (Simplified)

**Long Entry**:
```
IF current_price > scanner['resistance']
AND not already in position
AND dist_to_R% was < 3% (reasonable distance at scan time)
THEN enter_long()
```

**Short Entry**:
```
IF current_price < scanner['support']
AND not already in position
AND dist_to_S% was < 3%
THEN enter_short()
```

**No waiting for hourly candles** - pivots are pre-defined by scanner analysis of historical support/resistance levels.

### Risk Management Rules (CRITICAL)

1. **Initial Stop**: Place at or just beyond pivot price (entry level)
2. **Take Partial Profits Immediately**: Sell 1/2 or 1/3 on first move (25-75¢)
3. **Move Stop to Breakeven**: After taking partial, stop on remainder goes to entry price
4. **5-7 Minute Rule**: If trade doesn't move favorably within 5-7 min, exit (indicates "reload seller/buyer")
5. **Scale Out**: Take additional profits at next technical levels
6. **Runner Management**: Trail stop on final piece, close by EOD

### Chart Setup Requirements

**60-minute chart with**:
- SMAs: 5, 10, 20, 50, 100, 200
- EMAs: 4, 9, 10, 13, 20, 50, 100, 200
- Bollinger Bands (20, 2)
- Linear Regression (30-period)

## Scanner Module (stockscanner/)

### Running the Scanner

```bash
cd stockscanner

# Quick scan (top 8 movers)
python scanner.py --category quick

# Full scan
python scanner.py

# Specific symbols
python scanner.py --symbols TSLA NVDA AMD

# By category
python scanner.py --category mega_tech
python scanner.py --category indices
```

### Scanner Output Format

**JSON/CSV files in `output/`** containing:
- `symbol` - Stock ticker
- `close` - Last close price
- `resistance` - Key resistance level (pivot high)
- `support` - Key support level (pivot low)
- `dist_to_R%` - Distance to resistance (%)
- `dist_to_S%` - Distance to support (%)
- `breakout_reason` - Why level is significant (e.g., "Tested 7x | 5-day high")
- `target1`, `target2`, `target3` - Price targets using measured moves
- `downside1`, `downside2` - Downside targets if support breaks
- `potential_gain%` - % gain to target1
- `risk%` - % risk to support
- `risk_reward` - R/R ratio
- `rvol` - Relative volume
- `atr%` - Average True Range %
- `score` - Overall setup score
- `setup` - Human-readable setup description

### Scanner Data Example

```json
{
  "symbol": "TSLA",
  "close": 442.11,
  "resistance": 444.77,
  "support": 432.63,
  "dist_to_R%": 0.6,
  "dist_to_S%": 2.14,
  "breakout_reason": "Tested 7x | 5-day closing high",
  "target1": 450.84,
  "target2": 456.91,
  "target3": 464.41,
  "risk_reward": 1.56,
  "score": 55,
  "setup": "High volatility 4.6% | Near breakout (0.6%) | Uptrend"
}
```

## Trader Module (to be built)

### Architecture Requirements

The trader module must:

1. **Read Scanner Output**
   - Parse daily scanner results (JSON/CSV) from `stockscanner/output/`
   - Filter setups by score, R/R ratio, distance to resistance
   - Prioritize high-scoring setups with good R/R (>1.5:1)
   - Extract pre-defined pivots: `resistance` (long) and `support` (short)

2. **Monitor Real-Time Price (Tick-by-Tick)**
   - Subscribe to real-time price data for all scanner symbols
   - Monitor continuously from market open (9:30 AM)
   - Check current price against scanner-identified pivots
   - Enter immediately when pivot breaks (no waiting for candle close)

3. **Execute Trades per PS60 Rules**
   - **Entry**: Market order when scanner pivot breaks
   - **Initial Stop**: Place stop at pivot level (resistance for longs, support for shorts)
   - **Partial Exits**: Automated scaling (sell 50% on first move of 0.25-0.75)
   - **Stop Management**: Move to breakeven after partial
   - **Final Exit**: Trail stop on remainder or close by EOD

4. **Risk Management**
   - Position sizing based on account size and distance to stop
   - Max risk per trade (1-2% of account)
   - Daily loss limits
   - Max concurrent positions (5-7 max)

5. **5-7 Minute Rule Implementation**
   - Start timer upon entry
   - Monitor price movement progress
   - Auto-exit if no favorable movement within 5-7 minutes
   - Indicates "reload seller/buyer" blocking the move

### Trading Workflow (Scanner-Driven)

```
Daily Workflow:
1. 8:00 AM (or prior evening) - Scanner runs, generates watchlist
2. 8:00-9:30 AM - Trader loads watchlist, prepares monitoring
3. 9:30 AM - Market opens, begin tick-by-tick monitoring
4. 9:30 AM - 4:00 PM - Monitor scanner pivots continuously
5. 3:55 PM - Close all remaining positions (flat by EOD)

Per-Trade Workflow (Scanner Pivot):
1. Load scanner output with pre-defined pivots
   - TSLA: resistance=$444.77, support=$432.63
2. Monitor real-time price from market open
3. Price breaks resistance ($445.00) → ENTER LONG immediately
4. Set initial stop at $444.77 (the pivot)
5. Take 50% profit on first move (e.g., $445.50-$446.00)
6. Move stop to breakeven ($445.00)
7. Take 25% at target1 ($450.84 from scanner)
8. Hold 25% as runner with trailing stop
9. Exit by 3:55 PM or if stop hits

Example Timeline:
9:30 AM - Market opens, TSLA = $442.00
9:47 AM - TSLA breaks $444.77 → Enter long at $444.85
9:52 AM - TSLA hits $445.75 → Sell 50% (+$0.90)
9:52 AM - Move stop to $444.85 (breakeven)
10:15 AM - TSLA hits $447.50 → Sell 25% at target (+$2.65)
11:30 AM - TSLA pulls back to $444.85 → Stop hits, exit 25% (scratch)
Result: +$0.45 avg on 50%, +$2.65 on 25%, $0 on 25% = +$1.11/share avg
```

### IBKR Integration

**Connection**:
- Use `ib_insync` library (same as scanner)
- Port 7497 (paper) or 7496 (live)
- Separate client ID from scanner (e.g., 2000+)

**Order Types**:
- Market orders for entries (fast execution when pivot breaks)
- Stop-loss orders for risk management (at pivot level)
- Limit orders for partial profit-taking (optional)
- Bracket orders to combine entry/stop/target (optional)

**Real-time Data Requirements**:
- Subscribe to **real-time tick data** (not bar data) for watchlist symbols
- Use `reqMktData()` for continuous price updates
- Monitor bid/ask/last price
- No need for 60-minute bar subscriptions (pivots pre-defined by scanner)

### Position Management

**Sizing Algorithm**:
```python
risk_per_trade = account_value * 0.01  # 1% risk
stop_distance = abs(entry_price - pivot_price)
shares = risk_per_trade / stop_distance
shares = min(shares, max_position_size)  # Cap at max size
```

**Scaling Out**:
- Sell 50% at first favorable move (0.25-0.75 typically)
- Sell 25% at target1 (conservative target)
- Hold 25% as runner with trailing stop

### Configuration

**trader_config.yaml** should include:
```yaml
trading:
  account_size: 100000
  risk_per_trade: 0.01  # 1%
  max_positions: 5
  max_daily_loss: 0.03  # 3%

  position_sizing:
    min_shares: 10
    max_shares: 1000

  entry:
    use_market_orders: true
    slippage_tolerance: 0.02  # 2%

  exits:
    partial_1_pct: 0.50  # Sell 50% first
    partial_2_pct: 0.25  # Sell 25% second
    runner_pct: 0.25     # Hold 25%

  risk:
    five_minute_rule: true
    breakeven_after_partial: true
    close_all_by_eod: true
    eod_close_time: "15:55"

  filters:
    min_score: 50
    min_risk_reward: 1.5
    max_dist_to_pivot: 2.0  # Max 2% from pivot

backtest:
  use_1min_bars: true        # Use 1-min bars (not tick data)
  start_date: "2025-09-01"
  end_date: "2025-09-30"
  scanner_output_dir: "../stockscanner/output/"
```

## Backtesting with IBKR Historical Data

### Overview

The backtesting module uses **1-minute historical bars** from IBKR to simulate tick-by-tick trading. This provides sufficient resolution to detect pivot breaks while having years of historical data available.

### Why 1-Minute Bars (Not Tick Data)

**1-Minute Bars**:
- ✅ Years of historical data available
- ✅ Sufficient resolution for pivot break detection
- ✅ Faster processing (fewer data points)
- ✅ No pagination complexity
- ⚠️ Assumes entry at bar close (minor inaccuracy)

**Tick-by-Tick Data**:
- ✅ Most accurate simulation
- ❌ Only 30-60 days history available
- ❌ Limited to 1000 ticks per request (requires pagination)
- ❌ Much slower processing
- ❌ Rate limited (60 requests per 10 minutes)

### Backtest Architecture

```python
# backtest/backtester.py

from ib_insync import IB, Stock
from datetime import datetime, timedelta
import json
import pandas as pd

class PS60Backtester:
    """
    Backtest PS60 strategy using 1-minute historical bars from IBKR
    Simulates tick-by-tick monitoring of scanner-identified pivots
    """

    def __init__(self, scanner_file, start_date, end_date):
        self.ib = IB()
        self.ib.connect('127.0.0.1', 7497, clientId=3000)

        # Load scanner results
        with open(scanner_file) as f:
            self.scanner_results = json.load(f)

        self.start_date = start_date
        self.end_date = end_date
        self.trades = []

    def run(self):
        """Run backtest over date range"""
        current_date = self.start_date
        while current_date <= self.end_date:
            print(f"\n=== Backtesting {current_date} ===")
            self.backtest_day(current_date)
            current_date += timedelta(days=1)

        self.print_results()

    def backtest_day(self, date):
        """Backtest single trading day"""
        # Filter scanner for tradeable setups
        watchlist = [s for s in self.scanner_results
                     if s['score'] >= 50 and s['risk_reward'] >= 1.5]

        for stock in watchlist:
            self.backtest_stock(stock, date)

    def backtest_stock(self, stock, date):
        """Backtest single stock for the day"""
        symbol = stock['symbol']
        resistance = stock['resistance']
        support = stock['support']

        # Get 1-minute historical bars from IBKR
        bars = self.get_bars(symbol, date)

        if not bars:
            return

        position = None

        # Simulate tick-by-tick monitoring
        for bar in bars:
            timestamp = bar.date
            price = bar.close

            # Entry logic - check for pivot breaks
            if position is None:
                if price > resistance:
                    position = self.enter_long(stock, price, timestamp)
                elif price < support:
                    position = self.enter_short(stock, price, timestamp)

            # Exit logic - manage open position
            else:
                position, closed_trade = self.manage_position(
                    position, price, timestamp
                )
                if closed_trade:
                    self.trades.append(closed_trade)
                    position = None

    def get_bars(self, symbol, date):
        """Fetch 1-minute bars from IBKR"""
        contract = Stock(symbol, 'SMART', 'USD')

        try:
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=f'{date.strftime("%Y%m%d")} 16:00:00',
                durationStr='1 D',
                barSizeSetting='1 min',  # 1-minute bars
                whatToShow='TRADES',
                useRTH=True,  # Regular trading hours only
                formatDate=1
            )
            return bars
        except Exception as e:
            print(f"    Error fetching {symbol}: {e}")
            return []

    def enter_long(self, stock, price, timestamp):
        """Enter long position"""
        shares = self.calculate_position_size(price, stock['resistance'])

        position = {
            'symbol': stock['symbol'],
            'side': 'LONG',
            'entry_price': price,
            'entry_time': timestamp,
            'stop': stock['resistance'],  # Initial stop at pivot
            'target1': stock['target1'],
            'shares': shares,
            'remaining': 1.0  # 100% of position
        }

        print(f"  {stock['symbol']}: LONG @ ${price:.2f} "
              f"(pivot ${stock['resistance']:.2f})")
        return position

    def manage_position(self, pos, price, timestamp):
        """
        Manage open position per PS60 rules:
        - Take 50% profit on first move
        - Move stop to breakeven
        - Exit at target or stop
        - 5-7 minute rule
        """
        time_in_trade = (timestamp - pos['entry_time']).total_seconds() / 60

        if pos['side'] == 'LONG':
            gain = price - pos['entry_price']

            # Take 50% profit on first favorable move (0.25-0.75)
            if pos['remaining'] == 1.0 and gain >= 0.25:
                print(f"    Partial: 50% @ ${price:.2f} (+${gain:.2f})")
                pos['remaining'] = 0.5
                pos['stop'] = pos['entry_price']  # Move to breakeven
                pos['partial1_price'] = price

            # Hit target1 - take another 25%
            elif pos['remaining'] > 0.25 and price >= pos['target1']:
                print(f"    Target1: 25% @ ${price:.2f}")
                pos['remaining'] = 0.25

            # Stop hit - exit remaining
            elif price <= pos['stop']:
                print(f"    Stop: Exit remaining @ ${price:.2f}")
                return None, self.close_position(pos, price, timestamp, 'STOP')

            # 5-7 minute rule - no movement
            elif time_in_trade >= 7 and gain < 0.10:
                print(f"    5-min rule: Exit @ ${price:.2f}")
                return None, self.close_position(
                    pos, price, timestamp, '5MIN_RULE'
                )

        # Similar logic for shorts...

        return pos, None

    def calculate_position_size(self, entry, stop):
        """Calculate shares based on 1% risk"""
        account_value = 100000
        risk_per_trade = account_value * 0.01
        stop_distance = abs(entry - stop)
        shares = int(risk_per_trade / stop_distance)
        return min(shares, 1000)  # Cap at max

    def close_position(self, pos, exit_price, timestamp, reason):
        """Close position and record trade"""
        if pos['side'] == 'LONG':
            pnl_per_share = exit_price - pos['entry_price']
        else:
            pnl_per_share = pos['entry_price'] - exit_price

        total_pnl = pnl_per_share * pos['shares'] * pos['remaining']

        trade = {
            'symbol': pos['symbol'],
            'side': pos['side'],
            'entry': pos['entry_price'],
            'exit': exit_price,
            'pnl': total_pnl,
            'reason': reason
        }
        return trade

    def print_results(self):
        """Print backtest performance metrics"""
        if not self.trades:
            print("\nNo trades executed")
            return

        df = pd.DataFrame(self.trades)

        print("\n=== BACKTEST RESULTS ===")
        print(f"Total trades: {len(df)}")
        print(f"Winners: {len(df[df['pnl'] > 0])}")
        print(f"Win rate: {len(df[df['pnl'] > 0]) / len(df) * 100:.1f}%")
        print(f"Total P&L: ${df['pnl'].sum():.2f}")
        print(f"Avg winner: ${df[df['pnl'] > 0]['pnl'].mean():.2f}")
        print(f"Avg loser: ${df[df['pnl'] < 0]['pnl'].mean():.2f}")
```

### Running Backtests

```bash
cd trader

# Backtest single day
python backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results_20250930.json \
  --date 2025-09-30

# Backtest date range
python backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results.json \
  --start-date 2025-09-01 \
  --end-date 2025-09-30

# Generate performance report
python backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results.json \
  --date 2025-09-30 \
  --report backtest_report.html
```

### Backtest Validation Strategy

1. **Historical Scanner Results**: Run scanner on historical dates to get past pivots
2. **Fetch Historical Bars**: Use IBKR API to get 1-min bars for those dates
3. **Simulate Trading**: Process bars sequentially, enter/exit per PS60 rules
4. **Compare with Actual**: Validate backtest results match expected behavior
5. **Iterate**: Refine entry/exit logic based on backtest findings

### Key Backtest Metrics

```python
# Performance metrics to track
metrics = {
    'total_trades': len(trades),
    'win_rate': winners / total_trades,
    'profit_factor': gross_profit / abs(gross_loss),
    'avg_winner': avg_winning_trade,
    'avg_loser': avg_losing_trade,
    'avg_trade': total_pnl / total_trades,
    'max_drawdown': calculate_max_drawdown(trades),
    'sharpe_ratio': calculate_sharpe(returns),
    '5min_rule_exits': count_by_reason('5MIN_RULE'),
    'stop_exits': count_by_reason('STOP'),
    'target_exits': count_by_reason('TARGET')
}
```

### IBKR Historical Data Limits

- **Bar data**: Available for several years back
- **Rate limits**: ~60 historical data requests per 10 minutes
- **Concurrent requests**: Max 50 simultaneous
- **Pacing**: Add 0.5-1 second delay between requests

### Project Structure with Backtest

```
trader/
├── backtest/
│   ├── backtester.py           # Main backtest engine
│   ├── historical_data.py      # IBKR data fetcher
│   ├── performance_metrics.py  # Calculate metrics
│   └── reports.py             # Generate HTML reports
├── trader.py                   # Live trader
├── position_manager.py
├── order_executor.py
└── config/
    ├── trader_config.yaml
    └── backtest_config.yaml
```

## Key Commands (Once Built)

### Scanner Commands
```bash
cd stockscanner
python scanner.py --category quick  # Generate daily watchlist
```

### Trader Commands

```bash
cd trader

# Backtest single day
python3 backtest/backtester.py --date 2025-09-30 \
  --scanner ../stockscanner/output/scanner_results_20250930.json \
  --account-size 100000

# Live paper trading (RECOMMENDED - start here)
python3 trader.py

# With custom config
python3 trader.py --config config/trader_config.yaml
```

### Daily Trading Workflow

**Morning (8:00-9:30 AM):**
1. Run scanner: `cd stockscanner && python3 scanner.py --category quick`
2. Review scanner results in `stockscanner/output/scanner_results.json`
3. Start TWS/Gateway on port 7497 (paper trading)

**Trading Hours (9:30 AM - 4:00 PM):**
4. Start trader: `cd trader && python3 trader.py`
5. Trader monitors pivots and executes trades automatically
6. Entry window: 9:45 AM - 3:00 PM
7. EOD close: 3:55 PM (all positions closed)

**After Market (4:00+ PM):**
8. Review logs in `trader/logs/trader_YYYYMMDD.log`
9. Review trades in `trader/logs/trades_YYYYMMDD.json`
10. Compare performance vs backtest expectations

## Backtest Results (September 30, 2025)

### Backtest Configuration Evolution

**Final Optimal Settings:**
- ✅ **Max 2 attempts per pivot** (not 1, not unlimited)
- ✅ **Min R:R 2.0** (quality over quantity)
- ✅ **No trading after 3:00 PM** (last hour excluded)
- ✅ **Tight stops at pivot** (PS60 discipline)
- ✅ **50% partial profits** on first move

### Performance Summary

| Version | Trades | Win% | P&L | Avg/Trade | Profit Factor |
|---------|--------|------|-----|-----------|---------------|
| Original (buggy) | 126 | 47% | +$1,289 | +$10 | 1.13 |
| 1 Attempt | 16 | 38% | +$616 | +$39 | 1.44 |
| **2 Attempts (Final)** | **27** | **37%** | **+$1,441** | **+$53** | **1.55** |

**Key Findings:**
- **Max 2 attempts is optimal** (134% more P&L than 1 attempt)
- **Second chances pay off**: JPM 2nd attempt = +$1,000, BA 2nd = +$968
- **Let winners run**: Trades lasting >30 min = 100% win rate
- **Partial profits work**: Even losers reduced via partials

### Loss Analysis

**Total Losses**: $2,627 across 17 losing trades

**Top 3 Loss Categories:**
1. **Index Shorts** (26.6%, -$700): SPY/QQQ whipsawed near support
2. **Early Morning** (40%, -$1,060): 9:30-9:45 AM volatility
3. **Quick Stops** (68%, -$1,787): <3 min exits on tight stops

**Top 5 Individual Losses:**
1. BIDU LONG: -$600 (early failed breakout)
2. AVGO SHORT: -$560 (2nd attempt whipsaw)
3. SPY SHORT: -$390 (index whipsaw)
4. ROKU LONG: -$250 (resistance held)
5. QQQ SHORT: -$200 (index whipsaw)

### Recommended Filters (From Backtest)

**Additional Filters to Implement:**
1. ✅ **Avoid index shorts** → Save ~$700/day (SPY, QQQ, DIA)
2. ✅ **Wait until 9:45 AM** → Save ~$600/day (let opening volatility settle)
3. ✅ **Skip choppy 2nd attempts** → Save ~$400/day (if 1st failed badly)

**Expected Performance with Filters:**
- Trades: ~18-20 per day (vs 27)
- Win Rate: ~50% (vs 37%)
- P&L: ~$2,500-3,000/day (vs $1,441)

### Live Trading Expectations

**Conservative Estimate (50% of backtest):**
- Daily: $720
- Monthly (20 days): $14,400 (14.4% on $100k)
- Annual: ~170%

**Backtest Performance (100%):**
- Daily: $1,441 (1.44%)
- Monthly: $28,800 (28.8%)
- Annual: ~350%

**Target Range**: $1,000-2,000/day with discipline

## Live Trader Implementation (October 2025)

### Status: ✅ LIVE - In Paper Trading

The live trader has been implemented, tested in paper trading, and the critical timezone bug has been fixed.

### Architecture

```python
trader.py                    # Main trading engine
├── Load scanner results     # Filter by score ≥50, R/R ≥2.0
├── Connect to IBKR          # Port 7497 (paper trading)
├── Subscribe market data    # Real-time ticks for watchlist
├── Monitor pivot breaks     # Tick-by-tick price monitoring
├── Execute trades           # Market orders on pivot breaks
├── Manage positions         # Partials, stops, targets
└── Close at EOD            # 3:55 PM liquidation
```

### Key Features Implemented

**Entry Logic:**
- ✅ Max 2 attempts per pivot (per backtest optimal)
- ✅ No trading before 9:45 AM (avoid early volatility)
- ✅ No trading after 3:00 PM (avoid late chop)
- ✅ Skip index shorts (SPY, QQQ, DIA, IWM)
- ✅ Filter by min score 50, min R/R 2.0
- ✅ Max 5 concurrent positions

**Exit Logic:**
- ✅ 50% partial on first move ($0.25+ gain)
- ✅ Move stop to breakeven after partial
- ✅ 25% partial at target1
- ✅ 25% runner with trailing stop
- ✅ 5-7 minute rule (exit if no movement)
- ✅ Close all positions at 3:55 PM

**Risk Management:**
- ✅ Position sizing: 1% risk per trade
- ✅ Stop at pivot (tight discipline)
- ✅ Max daily loss: 3% (circuit breaker)
- ✅ Min/max shares: 10-1000

**Logging:**
- ✅ Detailed trade logs with timestamps
- ✅ JSON trade records for analysis
- ✅ Daily P&L summary
- ✅ Win rate and avg winner/loser tracking

### Configuration (trader_config.yaml)

```yaml
trading:
  account_size: 100000
  risk_per_trade: 0.01  # 1%
  max_positions: 5

  entry:
    min_entry_time: "09:45"   # Backtest finding
    max_entry_time: "15:00"   # Backtest finding

  exits:
    partial_1_pct: 0.50       # 50% first
    partial_1_gain: 0.25      # At $0.25 gain
    eod_close_time: "15:55"

  attempts:
    max_attempts_per_pivot: 2  # Backtest optimal

filters:
  min_score: 50
  min_risk_reward: 2.0        # Backtest finding
  avoid_index_shorts: true    # Backtest finding (saved $700/day)
```

### Example Trading Session

```
09:30:00 - Market opens
09:45:00 - Trader starts monitoring
09:47:23 - 🟢 LONG BIDU @ $137.70 (pivot $137.42 broken)
          Shares: 1000 | Stop: $137.42 | Target: $140.50
09:48:15 - 💰 PARTIAL 50% BIDU @ $138.20 (+$0.50)
          Stop moved to $137.70 (breakeven)
10:15:30 - 🎯 PARTIAL 25% BIDU @ $140.50 (TARGET1)
11:45:00 - 🛑 CLOSE 25% BIDU @ $139.00 (TRAIL_STOP)
          P&L: +$785 (50% @ +$0.50, 25% @ +$2.80, 25% @ +$1.30)
```

### Expected vs Actual (To Be Tracked)

| Metric | Backtest | Live (Target) | Actual |
|--------|----------|---------------|--------|
| Daily P&L | $1,441 | $720-1,400 | TBD |
| Win Rate | 37% | 35-45% | TBD |
| Avg Trade | $53 | $40-60 | TBD |
| Trades/Day | 27 | 20-30 | TBD |

### Paper Trading Validation Plan

**Week 1-2:**
- Track all trades vs backtest expectations
- Monitor slippage and execution quality
- Validate entry/exit logic
- Check 5-7 minute rule effectiveness

**Week 3-4:**
- Compare results to backtest
- Adjust filters if needed
- Fine-tune parameters
- Verify risk management

**Criteria for Going Live:**
- ✅ Win rate ≥35%
- ✅ Profit factor ≥1.4
- ✅ Daily P&L positive 75%+ of days
- ✅ Max drawdown <5%
- ✅ No system errors or crashes
- ✅ Consistent with backtest (±30%)

### Known Limitations

1. **Slippage**: Backtest assumes perfect fills, live will have slippage
2. **Market Impact**: 1000 share orders may move price
3. **Data Latency**: Real-time vs backtest 1-min bars
4. **Psychological**: Backtest is emotionless, live trading is not

### Critical Bugs Fixed

#### Bug #1: Timezone Bug in EOD Close Logic (October 1, 2025)

**Issue**: EOD close logic was using local PST time instead of Eastern Time
- **Impact**: Positions remained open overnight at 4:00 PM market close
- **Date**: October 1, 2025 - 3 runner positions (PLTR, COIN, TSLA) left open
- **Fix**: Updated EOD close check to use Eastern Time (lines 532-543 in trader.py)
- **Status**: ✅ FIXED

```python
# BEFORE (buggy):
now = datetime.now().time()  # Local PST time

# AFTER (fixed):
import pytz
eastern = pytz.timezone('US/Eastern')
now_et = datetime.now(pytz.UTC).astimezone(eastern)
now = now_et.time()  # Eastern Time
```

#### Bug #2: Embedded Scanner in Backtest (October 3, 2025)

**Issue**: `run_monthly_backtest.py` was using an embedded/simplified scanner instead of production scanner
- **Impact**: Catastrophic - September backtest showed -$56k P&L vs +$8.9k with production scanner
- **Root Cause**: Created `HistoricalScanner` class inside backtest script instead of using `stockscanner/scanner.py`
- **Performance Difference**:
  - Embedded scanner: -$56,362 P&L, 26.8% win rate (WRONG)
  - Production scanner: +$8,895 P&L, 39.9% win rate (CORRECT)
  - **$65k difference** due to using wrong scanner!

#### Bug #3: 5-Minute Rule Firing After Partials (October 3, 2025) ⚠️ CRITICAL

**Issue**: Strategy module extraction lost critical condition in 5-minute rule logic
- **Date Discovered**: October 3, 2025
- **Impact**: Would have broken live trading - winners exited prematurely after taking partials
- **Severity**: CRITICAL - Live trading would have failed tomorrow

**Root Cause**:
When the `strategy/` module was extracted from `trader.py`, the 5-minute rule lost a critical check:

**Original working logic in trader.py:**
```python
# 5-7 minute rule
elif time_in_trade >= 7 and position['remaining'] == 1.0 and gain < 0.10:
    self.close_position(position, current_price, '5MIN_RULE')
```
**Key**: `position['remaining'] == 1.0` - only applies BEFORE taking partials

**Broken logic in extracted strategy module:**
```python
# Missing the remaining == 1.0 check!
if gain < self.five_minute_min_gain:
    return True, "5MIN_RULE"
```

**Impact on Results:**
- Oct 2 backtest WITHOUT fix: -$11,285 (88% losers)
- Oct 2 backtest WITH fix: -$3,401 (70% improvement)
- Oct 2 live trading (used original embedded logic): +$1,692 ✅

**Why This Matters:**
- After taking 50% partial profit, the original logic STOPS checking the 5-minute rule
- This allows profitable positions to run until EOD or target
- Examples from Oct 2 live trading:
  - AMAT: Took 1 partial, then held until EOD → +$2,420
  - LRCX: Took 1 partial, then held until EOD → +$1,425
  - INTC: Took 2 partials, then held until EOD → +$863

**The Fix:**
```python
# CRITICAL: Only apply 5-minute rule if NO partials taken yet
# If we've taken partials (remaining < 1.0), let the runner work
if position.get('remaining', 1.0) < 1.0:
    return False, None

# ... rest of 5-min rule logic
```

**Status**: ✅ **FIXED** (Line 244-247 in `trader/strategy/ps60_strategy.py`)

**Verification**: Full audit documented in `trader/STRATEGY_MODULE_AUDIT.md`

#### Bug #4: Backtester Not Respecting Entry Time Window (October 3, 2025)

**Issue**: Backtester was ignoring `min_entry_time` configuration
- **Location**: `trader/backtest/backtester.py` lines 202-206
- **Impact**: Backtest entering trades at 9:30 AM even when config said 10:13 AM
- **Root Cause**: Hardcoded check for `hour >= 15` (3 PM cutoff) instead of using strategy module's `is_within_entry_window()`

**The Bug:**
```python
# WRONG - only checks if NOT after 3 PM
time_cutoff = (hour >= 15)
if position is None and not time_cutoff:
    # Enter trade...
```

**The Fix:**
```python
# CORRECT - uses strategy module to check min AND max entry time
within_entry_window = self.strategy.is_within_entry_window(timestamp)
if position is None and within_entry_window:
    # Enter trade...
```

**Status**: ✅ **FIXED** (Line 203 in `trader/backtest/backtester.py`)

#### Bug #5: Exit Time Display Corruption (October 3, 2025) - Cosmetic

**Issue**: Position manager shows exit times as current wall clock time instead of actual bar timestamp
- **Location**: `trader/strategy/position_manager.py` in `close_position()`
- **Impact**: All backtest exit times show as 11:45 PM instead of actual market time
- **Root Cause**: Uses `datetime.now()` for exit_time instead of accepting timestamp parameter

**Example of Bug:**
- Trade actually exits at 10:28 AM
- Display shows: "Exit: $219.49 @ 23:44" (11:44 PM - completely wrong!)

**Status**: ⚠️ **NOT FIXED** - Cosmetic issue, doesn't affect P&L calculations

### October 1, 2025 Trading Session

**Paper Trading Results (R/R 1.5:1 filter)**:
- **Realized P&L**: +$756.19
- **Win Rate**: 66.7% (2 winners, 1 loser)
- **Trades**: 3 total (COIN, PLTR, TSLA)

| Symbol | Entry | Exit | P&L | Result |
|--------|-------|------|-----|--------|
| COIN | $346.55 | $346.35 | -$29 | Quick stop |
| PLTR | $183.10 | $185.26 | +$378 | Winner (partial + target) |
| TSLA | $447.13 | $450.25 | +$423 | Winner (partial + target) |

**Overnight Positions** (due to timezone bug):
- PLTR: 250 shares @ $183.10 (runner position)
- COIN: 171 shares @ $346.55 (runner position)
- TSLA: 105 shares @ $447.13 (runner position)

**Key Observations**:
1. ✅ Lower R/R filter (1.5 vs 2.0) allowed PLTR (1.65) and TSLA (1.56) to qualify - both were winners
2. ✅ Entry logic working well - caught pivot breaks
3. ✅ Partial profit-taking working - locked in gains early
4. ❌ EOD close bug prevented closing runners at 3:55 PM EST
5. ✅ Trader performed well during live market conditions

### September 2025 Monthly Backtest - FINAL RESULTS

**Status**: ✅ COMPLETE (October 1, 2025)

**Configuration**:
- **Scanner**: Production scanner (`stockscanner/scanner.py`)
- **Filters**: Score ≥75, R/R ≥1.5
- **No Look-Ahead Bias**: Scanner uses previous day's data only

**Performance Results**:
- **Total Trading Days**: 22
- **Total Trades**: 183
- **Total P&L**: **+$8,895.23** (8.9% return on $100k account)
- **Win Rate**: 39.9%
- **Avg P&L per Day**: +$404.33
- **Avg Trades per Day**: 8.3

**Best Trading Days**:
1. Sept 23: +$4,882.50 (3 trades, 100% win rate)
2. Sept 12: +$2,069.80 (9 trades)
3. Sept 30: +$1,607.50 (10 trades)
4. Sept 17: +$1,395.00 (4 trades)
5. Sept 10: +$1,125.00 (7 trades)

**Worst Trading Days**:
1. Sept 22: -$2,185.00 (25 trades - overtrading)
2. Sept 5: -$1,015.00 (15 trades)
3. Sept 2: -$607.06 (11 trades)

**Critical Finding - Scanner Quality Matters**:
The type of scanner used made a MASSIVE difference:

| Scanner | P&L | Win Rate | Difference |
|---------|-----|----------|------------|
| **Production Scanner** | **+$8,895** | 39.9% | Baseline |
| Embedded Scanner | -$7,986 | 33.6% | -$16,881 worse! |

**Key Insights**:
1. ✅ Strategy IS profitable with proper scanner (+8.9% monthly)
2. ✅ Production scanner's sophisticated scoring works
3. ⚠️ Lower trade volume (8.3/day) but higher quality
4. ⚠️ Need to avoid overtrading (Sept 22: 25 trades = biggest loss)
5. ✅ Win rate of 40% is sufficient with proper R/R management

**Critical Finding - Look-Ahead Bias**:
- **Discovery Date**: September 30, 2025
- **Impact**: Scanner was using same-day data, creating unrealistic backtest results
- **Sept 30 Comparison**:
  - WITH bias: +$1,441 (unrealistic)
  - WITHOUT bias: -$1,528 (realistic)
  - **Difference**: ±$2,969 swing!

**Fix Applied**:
- Scanner now uses data from day BEFORE trading day
- Proper walk-forward testing methodology
- All September scanner files regenerated without bias
- Final backtest uses production scanner with proper historical dates

### Next Steps

1. ✅ **Paper trade 2-4 weeks** minimum
2. ✅ **Track performance daily** vs backtest
3. ✅ **Adjust filters** based on live results (tested 1.5 R/R)
4. ✅ **Document edge cases** and anomalies
5. ✅ **Fix timezone bug** in EOD close logic
6. ⏳ **Complete September backtest** and analyze results
7. ⚠️ **Only go live** after consistent results

## Critical Implementation Rules

### DO NOT:
1. **NEVER create simplified/embedded versions without asking** - Always use the actual production code
2. **NEVER make architectural decisions independently** - Always ask the user first
3. **NEVER create duplicate/alternative implementations** - Update existing code in place
4. Use fake data - only real IBKR market data
5. Skip the 5-7 minute rule - it prevents large losses
6. Skip partial profit-taking - critical for cash flow

### 🚨 CRITICAL LESSON LEARNED - SCANNER DUPLICATION BUG 🚨

**THIS MISTAKE HAS BEEN MADE TWICE - IT MUST NEVER HAPPEN AGAIN**

#### Incident #1 (October 1, 2025):
**Problem**: Created an "embedded scanner" inside `run_monthly_backtest.py` instead of using the production scanner from `stockscanner/scanner.py`

**Impact**:
- Embedded scanner: -$7,986 P&L (33.6% win rate)
- Production scanner: **+$8,895 P&L (39.9% win rate)**
- **Difference**: $16,881 swing due to using simplified code!

#### Incident #2 (October 3, 2025):
**Problem**: SAME MISTAKE - `run_monthly_backtest.py` still using embedded `HistoricalScanner` class

**Impact**:
- Embedded scanner: -$56,362 P&L (26.8% win rate)
- Production scanner: **+$8,895 P&L (39.9% win rate)**
- **Difference**: $65,257 swing - CATASTROPHIC!

**Root Cause**: Took initiative to "simplify" without asking, creating inferior duplicate logic

**Lesson**: **ALWAYS ask before creating ANY alternative/simplified versions**. The production code exists for a reason - use it. If there's a problem (like IBKR connection issues), ask the user rather than creating workarounds.

### 🛑 MANDATORY RULE - NO EXCEPTIONS:

When implementing features that need existing functionality (scanner, strategy, position manager, etc.), **ALWAYS**:

1. ✅ **Import and use the actual production module** from its original location
2. ✅ **Ask the user** if modifications are needed
3. ✅ **Verify the code you're using** matches the production version
4. ❌ **NEVER create embedded/simplified versions** - this is BANNED
5. ❌ **NEVER assume simplification is acceptable** - always ask first
6. ❌ **NEVER duplicate logic** that already exists in production code

**If you find yourself copying code or creating a "simpler version":**
- **STOP IMMEDIATELY**
- **Ask the user** if this is the right approach
- **Explain why** you think duplication is needed
- **Wait for approval** before proceeding
5. Allow stops to be moved wider - discipline is key
6. Hold positions overnight - PS60 is day trading only
7. Chase trades - only enter when scanner pivot breaks
8. Wait for 60-minute candles - scanner pivots are pre-defined, enter on tick break
9. Recalculate resistance/support - use scanner values exactly
10. Trade stocks not in scanner output - scanner did the pre-qualification

### ALWAYS:
1. Use IBKR API exclusively for market data and execution
2. Implement strict stop discipline (no exceptions)
3. Take partial profits on first favorable move (50% on 0.25-0.75 gain)
4. Move stops to breakeven after partial
5. Close all positions by 15:55 ET (5 min before close)
6. Validate scanner data before trading (check file exists, parse correctly)
7. Log all trades with entry/exit reasoning
8. Implement the 5-7 minute rule for all trades
9. Calculate position size based on stop distance (risk = entry - pivot)
10. Use scanner pre-defined pivots (resistance/support) - no manual calculations
11. Enter immediately when pivot breaks - monitor tick-by-tick
12. Respect scanner filters (only trade stocks with score > 50, R/R > 1.5)

### Testing Strategy
1. **Unit tests**: Test each component (position manager, order executor, risk rules)
2. **Paper trading**: Minimum 2-4 weeks before live
3. **Backtest validation**: Compare against historical scanner results
4. **Manual verification**: Watch first trades execute and verify PS60 compliance

## PS60 Principles Summary

**The Core Philosophy**:
- Wait patiently for clear pivot breaks (don't predict)
- Enter only with confirmation and room to run
- Take quick partial profits (cash flow first)
- Keep losses small with tight stops at pivot
- Let runners capture trend moves
- Stay disciplined - no exceptions to rules

**Psychological Edge**:
- Pre-defined levels eliminate guesswork
- Partial profits reduce fear of giving back gains
- Breakeven stops remove stress on runners
- 5-minute rule prevents hope-based holding
- Structure removes emotional decision-making

## Documentation Files

- **PS60ProcessComprehensiveDayTradingGuide.md** - Complete PS60 theory and examples
- **stockscanner/CLAUDE.md** - Scanner implementation details
- **stockscanner/README.md** - Scanner user guide
- **stockscanner/IBKR_API_SETUP.md** - TWS configuration

## Success Metrics

**Scanner Performance**:
- Complete scan in <5 minutes
- Identify 5-15 quality candidates daily
- Score accuracy >80%

**Trader Performance** (targets):
- Win rate >50% (with proper execution)
- Average winner > average loser (by 2-3x)
- Max drawdown <5% monthly
- Consistency over home runs
- Respect all PS60 rules (audit compliance)

## Development Priority (Scanner-Driven Approach)

**Phase 1: Core Infrastructure**
1. Scanner output parser (read JSON/CSV from `stockscanner/output/`)
2. Watchlist filter (by score, R/R, distance to pivot)
3. Position manager (calculate position sizes based on risk)
4. IBKR connection manager (separate client ID from scanner)

**Phase 2: Real-Time Monitoring**
5. Real-time tick data subscription for watchlist symbols
6. Pivot break detection (monitor price vs. scanner resistance/support)
7. Entry signal generation (when pivot breaks)

**Phase 3: Order Execution**
8. Market order execution (enter on pivot break)
9. Stop-loss order placement (at pivot level)
10. Order status tracking and confirmations

**Phase 4: Exit Management**
11. Partial profit-taking logic (sell 50% on first move)
12. Breakeven stop adjustment (after partial)
13. Target-based exits (at scanner target1, target2)
14. Trailing stop for runners

**Phase 5: Risk Management**
15. 5-7 minute rule implementation (timer-based exit)
16. Position size calculator (based on stop distance)
17. Daily loss limits and position count limits
18. End-of-day liquidation (close all by 3:55 PM)

**Phase 6: Testing & Validation**
19. Paper trading mode (real market, simulated orders)
20. Trade logging and performance tracking
21. Backtest framework (replay historical scanner results)
22. Live paper trading validation (2-4 weeks minimum)

**Phase 7: Production**
23. Live trading mode (after validation)
24. Monitoring dashboard
25. Alert system for critical events

**Note**: Phases 3-7 from original plan (intraday pivots, gap plays) are **deferred** since we're focusing on scanner-identified pivots only.

Each phase must be tested thoroughly before proceeding to the next.
