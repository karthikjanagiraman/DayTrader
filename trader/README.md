# PS60 Live Trader

Automated trading system implementing the PS60 strategy with scanner-identified pivots.

## Quick Start

### Prerequisites

1. **IBKR Account** with paper trading enabled
2. **TWS or IB Gateway** running on port 7497 (paper trading)
3. **Scanner results** from `../stockscanner/output/scanner_results.json`

### Installation

```bash
# Install dependencies (if not already installed)
pip install ib_insync pyyaml
```

### Configuration

Edit `config/trader_config.yaml` to adjust settings:

- **Account size**: Default $100,000
- **Risk per trade**: Default 1%
- **Max positions**: Default 5
- **Entry window**: 9:45 AM - 3:00 PM (avoids early volatility)
- **Filters**: Min score 50, Min R/R 2.0

### Running the Trader

```bash
cd trader

# Run live paper trading
python3 trader.py

# Or with custom config
python3 trader.py --config config/trader_config.yaml
```

## Features

### Based on Backtest Results

✅ **Max 2 attempts per pivot** (optimal from backtest)
✅ **Min R/R 2.0 filter** (quality setups only)
✅ **No trading after 3:00 PM** (avoids late-day chop)
✅ **50% partial profits** on first move ($0.25+ gain)
✅ **Breakeven stops** after partial
✅ **5-7 minute rule** (exit if no movement)

### Risk Management

- **1% risk per trade** (position sized by stop distance)
- **Max 5 concurrent positions**
- **3% daily loss limit** (circuit breaker)
- **Tight stops at pivot** (PS60 discipline)
- **EOD close at 3:55 PM** (flat by close)

### Filters (From Loss Analysis)

- ✅ **Avoid index shorts** (SPY, QQQ, DIA, IWM)
- ✅ **Wait until 9:45 AM** (let opening volatility settle)
- ✅ **Min R/R 2.0** (high-quality setups only)

## Expected Performance

**Conservative (50% of backtest):**
- Daily: $720
- Monthly: $14,400 (14.4% on $100k)

**Backtest Performance:**
- Daily: $1,441 (1.44%)
- Monthly: $28,800 (28.8%)

**Target Range:** $1,000-2,000/day with discipline

## Workflow

### Daily Trading Session

1. **8:00 AM**: Run scanner (`cd ../stockscanner && python scanner.py`)
2. **9:30 AM**: Market opens
3. **9:45 AM**: Trader starts entering (15 min delay)
4. **9:45 AM - 3:00 PM**: Monitor and trade pivots
5. **3:00 PM**: No new entries
6. **3:55 PM**: Close all positions
7. **4:00 PM**: Market close, review results

### Per-Trade Workflow

1. Scanner identifies pivot (resistance/support)
2. Trader monitors price tick-by-tick
3. Price breaks pivot → Enter immediately
4. Set stop at pivot level
5. Take 50% profit on first move
6. Move stop to breakeven
7. Take 25% at target1
8. Hold 25% as runner with trailing stop
9. Exit by 3:55 PM or when stopped

## Logging

Logs are saved to `logs/` directory:
- `trader_YYYYMMDD.log` - Detailed trading log
- `trades_YYYYMMDD.json` - Trade records (JSON)

## Safety Features

1. **Paper Trading Mode**: Default enabled (requires TWS on port 7497)
2. **Daily Loss Limit**: Stops trading at 3% loss
3. **Max Positions**: Limits to 5 concurrent positions
4. **EOD Liquidation**: Closes all by 3:55 PM
5. **Error Handling**: Closes positions on errors

## Monitoring

The trader logs all activity:

```
2025-09-30 09:45:12 - PS60Trader - INFO - ✓ Loaded 18 setups from scanner
2025-09-30 09:47:23 - PS60Trader - INFO - 🟢 LONG BIDU @ $137.70
2025-09-30 09:47:23 - PS60Trader - INFO -    Shares: 1000 | Stop: $137.42
2025-09-30 09:50:15 - PS60Trader - INFO -   💰 PARTIAL 50% BIDU @ $138.20 (+$0.50, FIRST_MOVE)
2025-09-30 10:15:30 - PS60Trader - INFO -   🛑 CLOSE BIDU @ $137.10 (STOP)
2025-09-30 10:15:30 - PS60Trader - INFO -      P&L: $-350.00
```

## Configuration Reference

### Key Settings

```yaml
trading:
  account_size: 100000
  risk_per_trade: 0.01        # 1% risk
  max_positions: 5

  entry:
    min_entry_time: "09:45"   # Wait 15 min
    max_entry_time: "15:00"   # No late entries

  exits:
    partial_1_pct: 0.50       # 50% first
    partial_1_gain: 0.25      # At $0.25 gain
    eod_close_time: "15:55"

  attempts:
    max_attempts_per_pivot: 2  # Max 2 tries

filters:
  min_score: 50
  min_risk_reward: 2.0
  avoid_index_shorts: true
```

## Troubleshooting

### Connection Issues

1. **Ensure TWS/Gateway is running** on port 7497
2. **Check API settings** in TWS (File → Global Configuration → API)
3. **Verify client ID** is unique (default: 2000)

### No Scanner Results

1. **Run scanner first**: `cd ../stockscanner && python scanner.py`
2. **Check file path**: `../stockscanner/output/scanner_results.json`
3. **Verify file not empty**: Should have array of stocks

### No Trades Executing

1. **Check time window**: Trades only 9:45 AM - 3:00 PM
2. **Check filters**: Min score 50, min R/R 2.0
3. **Check pivots**: Price must break resistance/support
4. **Check max positions**: Limited to 5 concurrent

## Next Steps

1. ✅ **Paper trade 2-4 weeks** to validate performance
2. ✅ **Track results** vs backtest expectations
3. ✅ **Adjust filters** based on live performance
4. ✅ **Monitor for edge degradation**
5. ⚠️ **Only go live after consistent paper trading results**

## Files

- `trader.py` - Main live trading engine
- `config/trader_config.yaml` - Configuration
- `backtest/backtester.py` - Historical backtester
- `logs/` - Trade logs and records

## Support

See `../CLAUDE.md` for full project documentation and backtest results.

---

**⚠️ IMPORTANT**: This is for paper trading only. Always thoroughly test before risking real capital.

**Expected Performance**: $1,000-2,000/day based on September 30 backtest with $100k account.
