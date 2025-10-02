# PS60 Breakout Scanner

A professional-grade stock scanner for identifying high-probability breakout setups using the PS60 trading strategy. Features smart support/resistance detection, breakout reasoning analysis, and room-to-run calculations.

## Key Features

- 🎯 **Smart Support/Resistance Detection** - Filters outliers using quantiles and moving averages
- 📊 **Breakout Analysis with Reasoning** - Explains WHY levels are significant (tested 3x, historical high, etc.)
- 🚀 **Room to Run Calculations** - Three price targets using measured moves (T1, T2, T3)
- ⚖️ **Risk/Reward Analysis** - Calculates R/R ratios for each setup
- 📈 **Real-time IBKR Integration** - Uses live market data from Interactive Brokers
- 🏆 **Advanced Scoring System** - Multi-factor scoring (momentum, volume, volatility, proximity)

## Prerequisites

1. **Interactive Brokers Account** with:
   - TWS or IB Gateway installed
   - API access enabled
   - Market data subscriptions

2. **Python 3.11+**

3. **TWS/Gateway Configuration**:
   - Enable API connections in TWS/Gateway
   - Set socket port (7497 for paper, 7496 for live)
   - Check "Download open orders on connection"

## Installation

1. Clone the repository:
```bash
cd /Users/karthik/projects/DayTrader/stockscanner
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure TWS/Gateway:
   - Open TWS or IB Gateway
   - Go to File → Global Configuration → API → Settings
   - Enable "Enable ActiveX and Socket Clients"
   - Set Socket port to 7497 (paper) or 7496 (live)
   - Add trusted IP: 127.0.0.1

## Configuration

Edit `config/scanner_config.yaml` to customize:

- Stock universe (indexes, custom symbols)
- Filter thresholds (gap %, RVOL, etc.)
- IBKR connection settings
- Output paths and formats

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run quick scan (8 top movers)
python scanner.py --category quick

# Run full scan (all symbols)
python scanner.py

# Scan specific symbols
python scanner.py --symbols TSLA NVDA AMD GME

# Scan by category
python scanner.py --category mega_tech
python scanner.py --category meme
python scanner.py --category high_vol
```

## Scanner Categories

- `quick` - Top 8 movers for quick analysis
- `mega_tech` - AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA
- `meme` - GME, AMC, BB, BBBY, CLOV
- `high_vol` - COIN, PLTR, SOFI, HOOD, ROKU, SNAP
- `semis` - AMD, INTC, MU, QCOM, AVGO, AMAT
- `indices` - SPY, QQQ, IWM, DIA
- `all` - Full universe (~70 stocks)

## Output Files

The scanner generates output files in the `output/` directory:

1. **scanner_results.csv**: Full results with all metrics
2. **scanner_results.json**: JSON format for API integration

## Project Structure

```
stockscanner/
├── scanner.py              # Main unified scanner (ONLY scanner file)
├── CLAUDE.md              # Complete documentation
├── IBKR_API_SETUP.md      # TWS configuration guide
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── output/               # Scanner results
│   ├── scanner_results.csv
│   └── scanner_results.json
└── archive/              # Old scanner versions (archived)
```

## PS60 Strategy Overview

The scanner implements the PS60 trading methodology:

- **Entry**: Price breaks above/below pivot with 60-min confirmation
- **Pivots**: Yesterday's high (long) or low (short)
- **Filters**:
  - Minimum 2% gap
  - RVOL ≥ 2.0
  - Chart patterns (bases, consolidations)
  - Room to run (no immediate resistance/support)
- **Risk Management**: 1:1 minimum risk/reward ratio

## Troubleshooting

### IBKR Connection Issues

1. Ensure TWS/Gateway is running
2. Check API is enabled in settings
3. Verify port number matches config (7497/7496)
4. Check firewall isn't blocking connection

### Data Issues

1. Verify market data subscriptions are active
2. Check symbol is valid and tradeable
3. Ensure sufficient historical data exists

### Rate Limits

- IBKR limits concurrent market data lines (100 max)
- Historical data requests limited to 50 concurrent
- Scanner implements automatic rate limiting

## Development

To extend the scanner:

1. Follow the modular architecture in `src/modules/`
2. Update configuration schema in `scanner_config.yaml`
3. Add new filters in `filter_engine.py`
4. Implement new indicators in `data_processor.py`

## Important Notes

- This scanner uses IBKR API exclusively (no shortcuts or alternative data sources)
- All components follow the exact PS60 requirements specification
- Historical mode simulates pre-market conditions for testing
- Live mode requires active market data subscriptions

## License

Private use only. See CLAUDE.md for detailed requirements and implementation notes.