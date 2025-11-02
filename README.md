# DayTrader - Automated PS60 Trading System

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Live Paper Trading](https://img.shields.io/badge/status-paper%20trading-green.svg)](https://github.com)

> A comprehensive automated day trading system implementing Dan Shapiro's **PS60 Process** with pre-market scanning, real-time execution, and sophisticated risk management.

## 🎯 Overview

DayTrader is a production-ready algorithmic trading system designed for breakout day trading. The system identifies high-probability setups pre-market, monitors real-time price action, and executes trades with strict risk management rules. Built on the PS60 methodology (Pivot-Sixty Process), it emphasizes quick partial profits, tight stop discipline, and systematic trade execution.

### Key Achievements

- ✅ **Live Paper Trading** - Actively trading since October 2025
- 📊 **Proven Backtests** - Sept 2025: 183 trades, 39.9% win rate, +$8,895 (+8.9% monthly)
- 🎯 **Risk Management** - 1% risk per trade, automatic position sizing
- 📈 **Historical Data** - 1.5GB dataset covering October 2025 (9 stocks, 22 days)
- 🔄 **Full Integration** - IBKR TWS/Gateway connectivity with resilient error handling
- 📝 **Complete Logging** - Comprehensive trade analysis and session reporting

## ✨ Features

### Pre-Market Scanner
- **Pivot Identification** - Automatically detects key resistance/support levels
- **Technical Analysis** - 250-day historical indicators (SMAs, EMAs, RSI, ATR, BB)
- **Target Calculation** - Measured moves with R/R ratios
- **Enhanced Scoring** - ML-informed setup ranking (70% accuracy in top 10)
- **Quick Scan Mode** - Focus on 9 high-liquidity stocks

### Live Trader
- **Real-Time Monitoring** - Tick-by-tick price tracking from 9:30 AM ET
- **Smart Entry System** - Hybrid momentum/pullback confirmation
- **11-Filter System** - Choppy market, room-to-run, gap filter, CVD monitoring
- **Partial Profit-Taking** - 50% at 1R, 25% at target, 25% runner
- **8-Minute Rule** - Auto-exit stalled trades (saves $2,300+/month)
- **Dynamic Stops** - Resistance-based exits and stall detection
- **EOD Management** - All positions closed by 3:55 PM ET

### Backtesting Engine
- **Historical Replay** - 1-minute bar simulation with IBKR data
- **Accurate Modeling** - Slippage (0.1%), commissions ($0.005/share)
- **Filter Testing** - Complete decision logging for validation
- **Performance Metrics** - Win rate, profit factor, Sharpe ratio, drawdown
- **Trade Analysis** - Detailed entry/exit reasoning per trade

### Risk Management
- **Position Sizing** - 1% account risk per trade
- **Stop Discipline** - Stops at pivot levels (no exceptions)
- **Max Positions** - 5 concurrent trades
- **Daily Loss Limit** - 3% account drawdown protection
- **Trade Window** - 9:45 AM - 3:00 PM ET entry, EOD exit

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.8 or higher
python3 --version

# IBKR TWS or Gateway
# Download from: https://www.interactivebrokers.com/en/trading/tws.php
```

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/DayTrader.git
cd DayTrader

# Install dependencies
pip install -r requirements.txt

# Configure IBKR connection
# Edit stockscanner/config/ibkr_config.yaml
# Edit trader/config/trader_config.yaml
```

### Run Pre-Market Scanner

```bash
cd stockscanner

# Quick scan (top 8 movers + QQQ)
python3 scanner.py --category quick

# Full scan (all categories)
python3 scanner.py

# Specific symbols
python3 scanner.py --symbols TSLA NVDA AMD PLTR
```

**Output**: `stockscanner/output/scanner_results_YYYYMMDD.json`

### Run Backtest

```bash
cd trader

# Backtest single day
python3 backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results_20251015.json \
  --date 2025-10-15 \
  --account-size 50000

# Results saved to: trader/backtest/results/
```

### Run Live Paper Trading

```bash
cd trader

# 1. Start TWS/Gateway on port 7497 (paper trading)
# 2. Run trader
python3 trader.py

# Monitor session (in another terminal)
tail -f logs/live_session_$(date +%Y%m%d).log
```

**Important**: Trader automatically:
- Loads today's scanner results
- Performs gap analysis
- Subscribes to market data
- Closes all positions by 3:55 PM ET
- Generates end-of-day P&L report

## 📊 Performance Results

### September 2025 Backtest
```
Account Size: $100,000
Total Trades: 183
Win Rate: 39.9%
Total P&L: +$8,895 (+8.9% monthly)
Avg Winner: $220.50
Avg Loser: -$156.40
Profit Factor: 1.71
Max Drawdown: -$2,340 (2.34%)
```

### October 1-4, 2025 Backtest
```
Account Size: $100,000
Total Trades: 42
Win Rate: 23.8%
Total P&L: +$5,461 (+5.46% monthly extrapolated)
Configuration: 8-min rule, risk-based sizing, hybrid entry
```

### Filter System Impact
- **Choppy Filter**: Saved $15k/month, win rate 6.7% → 40%+
- **Room-to-Run Filter**: 19x P&L improvement
- **8-Minute Rule**: +$2,334/month net benefit
- **Index Shorts Avoided**: +$700/day saved

## 🏗️ Project Structure

```
DayTrader/
├── stockscanner/              # Pre-market scanning module
│   ├── scanner.py            # Main scanner engine
│   ├── pivot_detection.py    # Resistance/support identification
│   ├── target_calculator.py  # Measured move targets
│   ├── enhanced_scoring.py   # ML-based setup ranking
│   ├── config/
│   │   └── ibkr_config.yaml # IBKR connection settings
│   └── output/              # Scanner results (JSON/CSV)
│
├── trader/                   # Trading module
│   ├── trader.py            # Live trading engine
│   ├── strategy/
│   │   ├── ps60_strategy.py        # PS60 trading logic
│   │   ├── ps60_entry_state_machine.py  # Entry confirmation
│   │   └── breakout_state_tracker.py    # Breakout monitoring
│   ├── backtest/
│   │   ├── backtester.py           # Historical backtester
│   │   ├── data/                   # 1-min bars + context (1.5GB)
│   │   │   ├── *_1min.json        # OHLCV 1-min bars
│   │   │   └── context/*.json     # Technical indicators
│   │   └── results/               # Backtest output
│   ├── validation/
│   │   └── validate_market_outcomes.py  # Filter validation
│   ├── data-downloader/
│   │   ├── download_october_data.py     # Historical bar downloader
│   │   └── process_context_indicators.py # Context generator
│   ├── config/
│   │   └── trader_config.yaml     # Strategy configuration
│   ├── logs/                      # Trade logs and session data
│   ├── analysis/                  # Daily session analysis
│   └── explained/                 # Detailed concept explanations
│
├── CLAUDE.md                 # AI assistant project guide
├── PS60ProcessComprehensiveDayTradingGuide.md  # PS60 theory
└── README.md                 # This file
```

## ⚙️ Configuration

### Scanner Configuration (`stockscanner/config/ibkr_config.yaml`)

```yaml
ibkr:
  host: "127.0.0.1"
  port: 7497  # 7497 = paper, 7496 = live
  client_id: 1

scanner:
  lookback_days: 250      # For SMA-200 calculation
  min_pivot_tests: 3      # Minimum resistance/support tests
  min_score: 50          # Minimum setup score
```

### Trader Configuration (`trader/config/trader_config.yaml`)

```yaml
trading:
  account_size: 50000
  risk_per_trade: 0.01    # 1%
  max_positions: 5
  max_daily_loss: 0.03    # 3%

filters:
  enable_choppy_filter: true         # Block low-volatility setups
  enable_room_to_run_filter: true    # Require min target distance
  enable_gap_filter: false           # Check overnight gaps
  enable_index_shorts: false         # Avoid shorting SPY/QQQ/DIA/IWM
  enable_8min_rule: true             # Exit stalled trades

exits:
  partial_1_pct: 0.50               # 50% at 1R
  partial_2_pct: 0.25               # 25% at target
  runner_pct: 0.25                  # 25% runner
  enable_dynamic_resistance_exits: true
  enable_target_hit_stall_detection: true
```

## 📚 Documentation

### Essential Reading
- **[CLAUDE.md](CLAUDE.md)** - Complete project documentation and implementation guide
- **[PROGRESS_LOG.md](trader/PROGRESS_LOG.md)** - Detailed implementation history (Oct 2025)
- **[PS60ProcessComprehensiveDayTradingGuide.md](PS60ProcessComprehensiveDayTradingGuide.md)** - PS60 methodology
- **[FILTER_DOCUMENTATION.md](trader/FILTER_DOCUMENTATION.md)** - Complete filter system reference

### Implementation Guides
- **[IBKR_RESILIENCE_COMPLETE.md](trader/IBKR_RESILIENCE_COMPLETE.md)** - Error handling system
- **[STATE_RECOVERY_COMPLETE.md](trader/STATE_RECOVERY_COMPLETE.md)** - Crash recovery
- **[BARBUFFER_INTEGRATION.md](trader/BARBUFFER_INTEGRATION.md)** - Tick-to-bar conversion
- **[LOGGING_GUIDE.md](trader/LOGGING_GUIDE.md)** - Logging system
- **[TRADING_SESSION_REPORT_REQUIREMENTS.md](trader/TRADING_SESSION_REPORT_REQUIREMENTS.md)** - Session analysis

### Quick References
- **[stockscanner/README.md](stockscanner/README.md)** - Scanner module guide
- **[trader/README.md](trader/README.md)** - Trader module guide
- **[trader/explained/](trader/explained/)** - Concept deep dives

## 🎓 PS60 Methodology

The **PS60 Process** (Pivot-Sixty) is a systematic breakout trading approach:

### Core Principles
1. **Pre-Defined Pivots** - Scanner identifies resistance/support from historical analysis
2. **Wait for Breakout** - Enter only when pivot breaks (no prediction)
3. **Confirm with Volume** - Require volume surge and momentum candle
4. **Quick Partials** - Take 50% profit at 1R (profit = risk distance)
5. **Breakeven Stops** - Move stop to entry after partial taken
6. **Scale Out** - Additional exits at targets (2R, 3R)
7. **Runner Management** - Trail stop on final 25%, close by EOD

### Entry Strategies

**Momentum Breakout** (Immediate Entry):
- Volume ≥ 2.0x average
- Candle ≥ 1.5% OR range ≥ 2x ATR
- Enter after candle close

**Pullback/Retest** (Patient Entry):
- Initial break with weak volume
- Wait for pullback within 0.3% of pivot
- Re-enter on re-break with 1.2x volume

### Risk Management
- **Position Sizing**: `shares = (account × 1%) / stop_distance`
- **Stop Placement**: At pivot level (resistance for longs, support for shorts)
- **8-Minute Rule**: Exit if no progress ($0.10/share) after 8 minutes
- **EOD Rule**: Close all positions by 3:55 PM ET

## 📈 Usage Examples

### Complete Daily Workflow

```bash
# Morning (8:00-9:30 AM ET)
cd stockscanner
python3 scanner.py --category quick  # Generate watchlist

# Review scanner results
cat output/scanner_results_$(date +%Y%m%d).json | python3 -m json.tool

# Start TWS/Gateway on port 7497

# Trading Hours (9:30 AM - 4:00 PM ET)
cd ../trader
python3 trader.py  # Auto-loads today's scanner results

# Monitor session (another terminal)
tail -f logs/live_session_$(date +%Y%m%d).log

# After Market (4:00+ PM ET)
# Review performance
cat logs/trades_$(date +%Y%m%d).json | python3 -m json.tool

# Generate session analysis (ask AI assistant)
# "analyze today's session"
```

### Validation Workflow

```bash
cd trader

# Step 1: Run backtest
python3 backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results_20251015.json \
  --date 2025-10-15 \
  --account-size 50000

# Step 2: Validate against market outcomes
python3 validation/validate_market_outcomes.py \
  --scanner ../stockscanner/output/scanner_results_20251015.json \
  --entry-log backtest/results/backtest_entry_decisions_20251015.json \
  --date 2025-10-15 \
  --account-size 50000

# Review missed winners and filter performance
cat validation/reports/validation_results_20251015.json
```

### Data Download

```bash
cd trader/data-downloader

# Download complete dataset (1-min bars + tick data + CVD bars)
python3 download_october_data.py

# Download specific date range
python3 download_october_data.py \
  --start-date 2025-10-15 \
  --end-date 2025-10-31

# Download without CVD (faster, bars + ticks only)
python3 download_october_data.py --no-cvd

# Process context indicators (SMAs, EMAs, RSI, etc.)
python3 process_context_indicators.py
```

**Enhanced 3-Stage Pipeline** (November 1, 2025):
- Stage 1: Downloads 1-minute OHLCV bars (~10 minutes)
- Stage 2: Downloads tick data for CVD calculation (~10-16 hours)
- Stage 3: Builds CVD-enriched bars from ticks (~10 minutes)
- Resilient: Resume capability, auto-reconnect, progress tracking

## 🔧 Advanced Configuration

### Filter Fine-Tuning

**Choppy Market Filter** (Block consolidation):
```yaml
filters:
  enable_choppy_filter: true
  choppy_range_multiplier: 0.5  # 5-min range < 0.5× ATR
```

**Room-to-Run Filter** (Require target distance):
```yaml
filters:
  enable_room_to_run_filter: true
  min_room_to_run_pct: 1.5  # Min 1.5% to target
```

**Gap Filter** (Overnight gap handling):
```yaml
filters:
  enable_gap_filter: true
  max_gap_through_pivot: 1.0    # 1% threshold
  min_room_to_target: 3.0       # 3% min after gap
```

### Entry Confirmation Thresholds

```yaml
entry:
  momentum:
    min_volume_multiplier: 2.0   # Strong breakout
    min_candle_size_pct: 1.5

  pullback_retest:
    max_pullback_pct: 0.3        # Retest proximity
    min_retest_volume: 1.2       # Confirmation volume

  delayed_momentum:
    weak_breakout_timeout_min: 15  # Wait time for volume
```

### Exit Rules

```yaml
exits:
  partial_1_pct: 0.50              # First partial
  partial_2_pct: 0.25              # Second partial
  runner_pct: 0.25                 # Final runner

  dynamic_resistance_exits: true   # Exit near resistance
  resistance_proximity_pct: 0.5    # 0.5% from resistance

  target_hit_stall_detection: true # Tighten stop if stall
  stall_range_pct: 0.2            # 0.2% consolidation
  stall_duration_min: 5           # 5 min stall
  stall_trailing_stop_pct: 0.1    # Tighten to 0.1%
```

## 🛠️ Development

### Running Unit Tests

```bash
cd trader/unit_tests
python3 -m pytest test_position_manager.py -v
python3 -m pytest test_barbuffer.py -v
python3 -m pytest test_ps60_strategy.py -v
```

### Logging Levels

```yaml
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  console: true
  file: true
```

### IBKR Connection

**Paper Trading** (recommended for testing):
```yaml
ibkr:
  port: 7497
  client_id: 2000
```

**Live Trading**:
```yaml
ibkr:
  port: 7496
  client_id: 2001
```

## 🐛 Troubleshooting

### Common Issues

**Scanner fails to connect to IBKR**:
```bash
# Check TWS/Gateway is running
# Check port configuration (7497 paper, 7496 live)
# Verify client ID is unique
```

**Trader can't load scanner results**:
```bash
# Scanner results naming: scanner_results_YYYYMMDD.json
# Check file exists in stockscanner/output/
# Verify JSON format with: cat file.json | python3 -m json.tool
```

**Backtest data missing**:
```bash
cd trader/data-downloader
python3 download_october_data.py  # Download 1-min bars
python3 process_context_indicators.py  # Generate context
```

**Position sizing errors**:
```yaml
# Check configuration
trading:
  account_size: 50000  # Must match IBKR account
  risk_per_trade: 0.01  # 1%

position_sizing:
  min_shares: 10       # Minimum position
  max_shares: 1000     # Maximum position
```

### Log Files

- **Live Trading**: `trader/logs/live_session_YYYYMMDD.log`
- **Trades**: `trader/logs/trades_YYYYMMDD.json`
- **Entry Decisions**: `trader/logs/live_entry_decisions_YYYYMMDD.json`
- **Backtest**: `trader/backtest/logs/backtest_YYYYMMDD_HHMMSS.log`

## 📋 Requirements

### Python Packages

```
ib_insync>=0.9.86
pandas>=1.3.0
numpy>=1.21.0
pyyaml>=5.4.0
python-dateutil>=2.8.0
pytz>=2021.1
```

### IBKR Requirements

- **TWS** or **IB Gateway** installed
- **Paper Trading Account** (recommended for testing)
- **Market Data Subscriptions** (for real-time data)
- **API Enabled** in TWS settings

### System Requirements

- **OS**: macOS, Linux, Windows
- **Python**: 3.8+
- **RAM**: 4GB+ (8GB+ recommended with historical data)
- **Storage**: 2GB+ for historical data

## 🤝 Contributing

Contributions welcome! Please follow these guidelines:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Test** thoroughly with backtests
4. **Document** changes in PROGRESS_LOG.md
5. **Commit** (`git commit -m 'Add amazing feature'`)
6. **Push** (`git push origin feature/amazing-feature`)
7. **Open** a Pull Request

### Code Standards

- Follow PS60 methodology strictly
- Add unit tests for new features
- Update documentation (CLAUDE.md, PROGRESS_LOG.md)
- Test with backtests before live trading
- Maintain filter independence (enable/disable via config)

## ⚠️ Disclaimer

**This software is for educational purposes only.**

- **No Financial Advice**: This system does not provide investment advice
- **Use at Your Own Risk**: Trading involves substantial risk of loss
- **Paper Trading First**: Always test thoroughly in paper trading
- **Not Guaranteed**: Past performance does not guarantee future results
- **Verify Everything**: Review all trades and logic before live trading

The authors assume no liability for any financial losses incurred.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Dan Shapiro** - PS60 Process methodology
- **Interactive Brokers** - IBKR API and TWS platform
- **ib_insync** - Python IBKR API wrapper
- **Claude Code** - AI-assisted development

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/DayTrader/issues)
- **Documentation**: [CLAUDE.md](CLAUDE.md)
- **Email**: your.email@example.com

## 🗺️ Roadmap

### Completed (October 2025)
- ✅ Pre-market scanner with pivot detection
- ✅ Live trader with IBKR integration
- ✅ 11-filter system with configuration
- ✅ Backtesting engine with 1-min bars
- ✅ Historical data infrastructure (Oct 2025)
- ✅ State recovery and error handling
- ✅ Session analysis and reporting
- ✅ Dynamic resistance exits
- ✅ Target-hit stall detection

### Future Enhancements
- 🔜 Multi-timeframe analysis
- 🔜 ML-based entry timing optimization
- 🔜 Real-time scanner (intraday pivot formation)
- 🔜 Options integration
- 🔜 Portfolio-level risk management
- 🔜 Web dashboard for monitoring
- 🔜 Telegram/Discord notifications
- 🔜 Advanced analytics and reporting

---

**Built with Python 🐍 | Powered by IBKR 📊 | Guided by PS60 📈**

*Last Updated: November 1, 2025*
