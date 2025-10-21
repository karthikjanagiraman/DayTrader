# Alert Module for PS60 Scanner

## Overview

The Alert Module automatically generates price alerts for all stocks in your scanner results, monitoring resistance and support levels. It can output alerts in multiple formats for use with TradingView, custom applications, or real-time monitoring.

## Features

✅ **Automatic Alert Generation** - Creates alerts for all resistance/support levels from scanner results
✅ **TradingView Integration** - Generates detailed instructions for setting up TradingView alerts
✅ **JSON Export** - API-friendly format for custom integrations
✅ **Real-Time Monitoring** - Monitor prices and get notified when levels are approached
✅ **Configurable Thresholds** - Set custom alert distances (default: 2% from level)

## Quick Start

### 1. Generate TradingView Alerts

```bash
python3 alerts.py --tradingview
```

This creates `output/tradingview_alerts.txt` with detailed instructions for each stock.

### 2. Generate JSON Alerts (for API integration)

```bash
python3 alerts.py --json
```

This creates `output/alerts.json` with all alert data in JSON format.

### 3. Real-Time Price Monitoring

```bash
python3 alerts.py --monitor --interval 60
```

This connects to IBKR and checks prices every 60 seconds, alerting when stocks approach key levels.

## Command-Line Options

```
--scanner-file FILE    Scanner results JSON file (default: output/scanner_results.json)
--threshold PCT        Alert threshold percentage (default: 2.0%)
--tradingview          Generate TradingView alert instructions
--json                 Generate JSON alert file
--monitor              Monitor prices in real-time
--interval SECONDS     Price check interval (default: 60)
```

## Examples

### Example 1: Quick TradingView Setup

```bash
# Use today's scanner results
python3 alerts.py --tradingview

# Use specific scanner results
python3 alerts.py --scanner-file output/scanner_results_20251015.json --tradingview
```

Output file: `output/tradingview_alerts.txt`

### Example 2: Tighter Alert Threshold

```bash
# Alert when within 1% of resistance/support (instead of 2%)
python3 alerts.py --threshold 1.0 --tradingview
```

### Example 3: Monitor Multiple Formats

```bash
# Generate both TradingView and JSON
python3 alerts.py --tradingview --json
```

### Example 4: Real-Time Monitoring

```bash
# Monitor prices every 30 seconds
python3 alerts.py --monitor --interval 30
```

Press `Ctrl+C` to stop monitoring.

## How It Works

### Alert Types

For each stock in the scanner results, the module creates **2 alerts**:

1. **RESISTANCE Alert** - Triggers when price approaches resistance (potential breakout)
2. **SUPPORT Alert** - Triggers when price approaches support (potential breakdown)

### Alert Trigger Logic

**Resistance Alert:**
- Trigger Price = Resistance × (1 - threshold%)
- Example: Resistance $100, threshold 2% → Alert at $98

**Support Alert:**
- Trigger Price = Support × (1 + threshold%)
- Example: Support $90, threshold 2% → Alert at $91.80

### TradingView Alert Setup

Each alert includes detailed TradingView setup instructions:

```
📝 TradingView Alert Setup:
   Condition: NVDA price crosses above $181.10
   Message: NVDA approaching resistance $184.80 - prepare for breakout
```

**To set up in TradingView:**

1. Open the stock chart
2. Click the **Alert** button (bell icon)
3. Set condition: "Price crosses above $181.10"
4. Set message: Copy the suggested message
5. Choose notification method (popup, email, webhook)
6. Click **Create**

## Output Formats

### TradingView Format (`tradingview_alerts.txt`)

Human-readable format with detailed instructions for each stock:

```
================================================================================
SYMBOL: NVDA
================================================================================

🔼 RESISTANCE ALERT:
   Alert Trigger: $181.10 (within 2.0% of resistance)
   Resistance Level: $184.80
   Current Price: $181.21
   Distance: 1.98%

   Breakout Targets:
      T1: $187.35
      T2: $189.90
      T3: $193.05

   📝 TradingView Alert Setup:
      Condition: NVDA price crosses above $181.10
      Message: NVDA approaching resistance $184.80 - prepare for breakout
```

### JSON Format (`alerts.json`)

Machine-readable format for API integration:

```json
{
  "generated_at": "2025-10-20T22:34:34",
  "total_alerts": 18,
  "alerts": [
    {
      "symbol": "NVDA",
      "type": "RESISTANCE",
      "trigger_price": 181.10,
      "target_price": 184.80,
      "current_price": 181.21,
      "threshold_pct": 2.0,
      "targets": {
        "T1": 187.35,
        "T2": 189.90,
        "T3": 193.05
      }
    }
  ]
}
```

## Real-Time Monitoring

When you run with `--monitor`, the module:

1. Connects to IBKR TWS/Gateway
2. Loads all alerts from scanner results
3. Checks current prices every N seconds
4. Triggers alerts when price crosses threshold
5. Displays alert notification with targets

**Example Output:**

```
================================================================================
🚨 ALERT TRIGGERED: NVDA
================================================================================
Type: RESISTANCE
Triggered Price: $181.50
Target Level: $184.80
Triggered At: 2025-10-20T14:30:15

🔼 Price approaching RESISTANCE at $184.80
   Watch for breakout above $184.80
   Breakout targets: T1=$187.35, T2=$189.90
================================================================================
```

## Integration Examples

### Python API Integration

```python
from alerts import AlertManager

# Load alerts
manager = AlertManager('output/scanner_results.json')
manager.create_alerts(threshold_pct=2.0)

# Get all alerts
alerts = manager.alerts

# Filter by symbol
nvda_alerts = [a for a in alerts if a['symbol'] == 'NVDA']

# Filter by type
resistance_alerts = [a for a in alerts if a['type'] == 'RESISTANCE']
```

### Webhook Integration

Use the JSON output to send alerts to external systems:

```python
import json
import requests

# Load alerts
with open('output/alerts.json') as f:
    data = json.load(f)

# Send to webhook
for alert in data['alerts']:
    requests.post('https://your-webhook.com/alerts', json=alert)
```

### Email/SMS Integration

Extend the `AlertManager` class to send notifications:

```python
def send_email_alert(self, alert):
    import smtplib
    message = f"ALERT: {alert['symbol']} approaching {alert['type']} at ${alert['target_price']}"
    # Send email...
```

## Tips & Best Practices

### TradingView Setup

1. **Use Alert Groups** - Organize alerts by setup type (breakout, breakdown)
2. **Set Expiration** - Remove stale alerts after market close
3. **Use Webhooks** - Send alerts to Telegram, Discord, or custom apps
4. **Sound Notifications** - Enable for critical levels only

### Alert Threshold Selection

- **2% (default)**: Good for day trading, early warning
- **1%**: Aggressive, more alerts but earlier warning
- **3%**: Conservative, fewer false alarms
- **0.5%**: Very tight, only for highly liquid stocks

### Real-Time Monitoring

- **Check interval**: 60 seconds is good balance (avoid API rate limits)
- **Peak hours**: Monitor during market open (9:30-10:30 AM) and power hour (3-4 PM)
- **Use with trader**: Run alongside automated trader for confirmation

## Workflow Example

### Daily Trading Workflow

**8:00 AM - Pre-Market:**
```bash
# Run scanner
python3 scanner.py --category quick

# Generate alerts
python3 alerts.py --tradingview --json

# Review output/tradingview_alerts.txt
# Set up top 3-5 setups in TradingView
```

**9:30 AM - Market Open:**
```bash
# Start real-time monitoring
python3 alerts.py --monitor --interval 60

# Or use TradingView alerts if already set up
```

**4:00 PM - After Market:**
- Review which alerts triggered
- Analyze successful setups
- Prepare for next day

## Troubleshooting

### "Connection failed" error
- Ensure TWS/Gateway is running
- Check port 7497 (paper) or 7496 (live)
- Try different `--client-id` if conflict

### No alerts generated
- Check scanner results file exists
- Verify JSON format is valid
- Ensure stocks have resistance/support levels

### Alerts not triggering in monitoring mode
- Increase threshold percentage
- Check current price vs trigger price
- Verify TWS market data subscriptions

## Future Enhancements

Planned features:
- [ ] Email notifications
- [ ] SMS/Telegram integration
- [ ] Webhook support for custom integrations
- [ ] Alert history and analytics
- [ ] Auto-update TradingView alerts via API
- [ ] Multi-timeframe alerts (hourly, daily)

## Support

For issues or questions:
1. Check scanner results are valid
2. Verify IBKR connection
3. Review command-line options with `--help`

## License

Part of DayTrader PS60 Scanner project.
