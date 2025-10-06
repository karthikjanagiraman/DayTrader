# Live Trader Logging Guide

**Created**: October 6, 2025
**Purpose**: Comprehensive logging for analysis, learning, and debugging

---

## Overview

The live trader now logs **extensive information** at every stage of the trading session to help you:
- ✅ Understand what filters are blocking trades
- ✅ Analyze entry timing and decision paths
- ✅ Track position performance minute-by-minute
- ✅ Compare live results to backtest expectations
- ✅ Identify gaps and improvement opportunities

---

## Log Levels

### INFO (Default)
**What it shows**: Key events and decisions
- Session start/end
- Gap analysis
- Entry/exit signals
- Partial profits
- Position updates
- Daily summary

**Use when**: Normal trading sessions

### DEBUG
**What it shows**: Everything above PLUS:
- All filter decisions
- Pivot check attempts
- Distance to resistance/support
- Why trades were blocked
- Position state every minute
- Detailed filter reasoning

**Use when**:
- Learning how filters work
- Debugging unexpected behavior
- Analyzing why trades weren't taken

**To enable**:
```yaml
# trader/config/trader_config.yaml
logging:
  log_level: "DEBUG"  # Change from INFO to DEBUG
```

---

## What Gets Logged

### 1. Session Start (INFO)
```
================================================================================
PS60 LIVE TRADER - PAPER TRADING SESSION
Date: 2025-10-06 Monday
Time: 09:30:15 AM ET
================================================================================
✓ Connected to IBKR (Paper: Port 7497, Client ID: 2001)
✓ Loaded 8 setups from scanner_results_20251006.json
✓ Subscribed to 8 symbols
```

**Purpose**: Confirm session initialization

### 2. Gap Analysis (INFO)
```
================================================================================
GAP ANALYSIS AT MARKET OPEN (9:30 AM)
================================================================================
❌ SKIPPED (2 stocks):
  CLOV: Gap 1.9% through pivot, only 3.1% to target
  AMC: Gap 2.5% through pivot, only 1.8% to target

⚠️  ADJUSTED (1 stocks):
  TSLA: Gap 2.1%, but 5.2% to target remains

📊 NOTED (1 stocks):
  PLTR: Gap +2.3%, now 0.8% from pivot

FINAL WATCHLIST: 6 setups (2 removed by gap filter)
================================================================================
```

**Purpose**: Understand overnight gap impact
**Learn**: How many setups invalidated by gaps

### 3. Filter Status (INFO)
```
================================================================================
MONITORING STARTED - ALL FILTERS ACTIVE
================================================================================
Active Filters:
  ✓ Choppy Market Filter: True
  ✓ Room-to-Run Filter: True
  ✓ Sustained Break Logic: True
  ✓ 8-Minute Rule: Active
  ✓ Max Attempts: 2
  ✓ Entry Window: 09:45 - 15:00
================================================================================

💡 TIP: Set log level to DEBUG to see all filter decisions
    Edit config: logging.log_level = 'DEBUG'
================================================================================
```

**Purpose**: Confirm which filters are enabled
**Learn**: What configuration is active

### 4. Pivot Checks (DEBUG)
```
  COIN: $345.20 is +0.05% from resistance $345.03 (attempt 1)
  PLTR: $182.50 is +0.14% from resistance $182.24 (attempt 1)
```

**Purpose**: Track when stocks approach pivot levels
**Learn**: How many times each pivot was tested

### 5. Filter Blocks (DEBUG)
```
  COIN: LONG blocked - Choppy filter: 5-min range $0.80 < 0.5× ATR $1.05
  PLTR: LONG blocked - Room-to-run: 0.61% < 1.5% minimum
  AMD: LONG blocked - Max attempts (2) reached for pivot $161.26
```

**Purpose**: Understand why trades weren't taken
**Learn**: Which filter is most active

### 6. Entry Signals (INFO)
```
🎯 COIN: LONG SIGNAL @ $345.92
   Distance from resistance: +0.26%
   Attempt: 1/2

🟢 LONG COIN @ $345.92 (10:05:23 AM ET)
   Shares: 906 | Risk: $1.11 | Room: 2.3%
   Stop: $344.81 | Target1: $354.00
```

**Purpose**: Document exact entry conditions
**Learn**: Entry timing, position size, risk/reward

### 7. Position Tracking (DEBUG - Every Minute)
```
  [COIN] LONG @ $345.92 | Current: $347.50 (+0.46%) | Time: 3m | Remaining: 100% | P&L: +$1,430.48
  [COIN] LONG @ $345.92 | Current: $348.25 (+0.67%) | Time: 4m | Remaining: 100% | P&L: +$2,109.98
```

**Purpose**: Track position progress minute-by-minute
**Learn**: How quickly positions move to profit

### 8. Partial Profits (INFO)
```
  💰 PARTIAL 50% COIN @ $348.45 (10:10:15 AM ET)
      (+$2.53, 1R gain)

  🛡️  COIN: Stop moved $344.81 → $345.92 (breakeven)
      Now protected: $1,289.43 locked in
```

**Purpose**: Document profit-taking decisions
**Learn**: When partials trigger, how much locked in

### 9. 8-Minute Rule (INFO)
```
⏱️  8-MINUTE RULE: AMD (No progress after 8 minutes)
   Entry: $161.50 @ 10:15:23 AM ET
   Current: $161.45 (-0.03%) after 8 minutes
   Reason: No progress, exiting to prevent larger loss

  🛑 CLOSE AMD @ $161.45 (8MIN_RULE)
     P&L: -$127.50
```

**Purpose**: Document early exits
**Learn**: How often 8-minute rule triggers

### 10. Market Activity Check (INFO - Every 5 Minutes)
```
⏰ 10:35 AM ET - Market Activity Check:
   Open Positions: 2
   Monitoring: 6 symbols
   COIN: LONG @ $345.92 (+1.2%)
   PLTR: LONG @ $183.10 (+0.8%)
```

**Purpose**: Periodic status update
**Learn**: Session activity level

### 11. EOD Close (INFO)
```
⏰ EOD close triggered at 03:55:00 PM ET
Closing all positions (EOD)...

  🛑 CLOSE COIN @ $346.20 (EOD)
     P&L: +$253.68
```

**Purpose**: Confirm flat by EOD
**Learn**: How many positions held to EOD

### 12. Daily Summary (INFO)
```
================================================================================
DAILY SUMMARY
================================================================================

Session Duration: 375 minutes
  Start: 09:45:00 AM ET
  End:   03:55:00 PM ET

📊 TRADING RESULTS:
  Total Trades: 3
  Daily P&L: $1,416.17 (1.42% of account)
  Winners: 2 (66.7%)
  Losers: 1
  Avg Trade: $472.06
  Avg Winner: $1,056.84
  Avg Loser: -$127.50
  Profit Factor: 3.31

🎯 FILTER ANALYTICS:
  Total Filter Blocks: 47
    Choppy filter: 23 times
    Room-to-run: 15 times
    Max attempts: 9 times

📈 ENTRY PATH BREAKDOWN:
  Momentum: 1 trades
  Pullback/Retest: 2 trades

🔍 MONITORING ACTIVITY:
  Total Price Updates: 22,500
  Total Pivot Checks: 1,250
  Most Active Symbols:
    COIN: 450 checks
    PLTR: 380 checks
    TSLA: 275 checks
    AMD: 145 checks

📋 TRADE-BY-TRADE BREAKDOWN:

  Trade #1: COIN LONG
    Entry: $345.92 @ 10:05:23 AM ET
    Exit:  $346.20 @ 03:55:00 PM ET (EOD)
    Duration: 350 minutes
    P&L: +$253.68 (+0.08%)
    Partials: 2 taken

  Trade #2: PLTR LONG
    Entry: $183.10 @ 10:15:45 AM ET
    Exit:  $185.26 @ 11:28:30 AM ET (TARGET1)
    Duration: 73 minutes
    P&L: +$1,290.00 (+1.18%)
    Partials: 1 taken

  Trade #3: AMD LONG
    Entry: $161.50 @ 10:22:15 AM ET
    Exit:  $161.45 @ 10:30:15 AM ET (8MIN_RULE)
    Duration: 8 minutes
    P&L: -$127.50 (-0.03%)
    Partials: 0 taken

💾 Full session data saved to: ./logs/trades_20251006.json

📊 BACKTEST COMPARISON:
  Expected Win Rate: 35-45%
  Actual Win Rate:   66.7%
  ✅ Within expected range (above average!)

================================================================================
```

**Purpose**: Complete session analytics
**Learn**: Everything - performance, filters, activity

---

## Structured JSON Output

**File**: `logs/trades_YYYYMMDD.json`

**Contents**:
```json
{
  "summary": {
    "total_trades": 3,
    "winners": 2,
    "losers": 1,
    "win_rate": 66.7,
    "daily_pnl": 1416.17,
    "avg_winner": 1056.84,
    "avg_loser": -127.50,
    "trades": [
      {
        "symbol": "COIN",
        "side": "LONG",
        "entry_price": 345.92,
        "exit_price": 346.20,
        "entry_time": "2025-10-06T10:05:23-04:00",
        "exit_time": "2025-10-06T15:55:00-04:00",
        "shares": 906,
        "pnl": 253.68,
        "reason": "EOD",
        "partials": [
          {
            "time": "2025-10-06T10:10:15-04:00",
            "price": 348.45,
            "pct": 0.5,
            "reason": "1R",
            "gain": 1289.43
          }
        ]
      }
    ]
  },
  "analytics": {
    "session_start": "2025-10-06T09:45:00-04:00",
    "session_end": "2025-10-06T15:55:00-04:00",
    "filter_blocks": {
      "Choppy filter": 23,
      "Room-to-run": 15,
      "Max attempts": 9
    },
    "entry_paths": {
      "Momentum": 1,
      "Pullback/Retest": 2
    },
    "pivot_checks": {
      "COIN": 450,
      "PLTR": 380,
      "TSLA": 275,
      "AMD": 145
    },
    "price_updates": 22500
  },
  "config": {
    "choppy_filter": true,
    "room_to_run_filter": true,
    "sustained_break": true,
    "max_attempts": 2,
    "entry_window": "09:45 - 15:00"
  }
}
```

**Purpose**: Machine-readable data for analysis
**Use**: Import into Excel, Python, or analysis tools

---

## Analysis Workflows

### 1. Identify Why Trades Were Blocked

**Question**: "Why didn't I take more trades today?"

**Steps**:
1. Check daily summary → Filter Analytics section
2. See which filter blocked the most trades
3. If choppy filter dominated: Market was consolidating
4. If room-to-run dominated: Entries too late (price already moved)
5. If max attempts dominated: Same pivots re-tested multiple times

**Action**:
- Choppy days: Accept fewer trades, this is correct behavior
- Room-to-run blocks: Check scanner timing (may need intraday scan)
- Max attempts: Review pivot quality (weak levels get re-tested)

### 2. Compare Live vs Backtest

**Question**: "Are my live results matching backtest expectations?"

**Steps**:
1. Check daily summary → Backtest Comparison section
2. Win rate should be 35-45%
3. Avg trade should be $40-60
4. Trades/day should be 3-8

**Red Flags**:
- Win rate <30%: Investigate losing trades
- Win rate >60%: Small sample size or lucky day
- Avg trade <$20: Risk/reward not being achieved
- Trades/day >10: Overtrading (filters may be too loose)

### 3. Analyze Filter Effectiveness

**Question**: "Are filters helping or hurting?"

**Steps**:
1. Check filter_blocks in JSON file
2. Calculate: Blocks per filter / Total trades attempted
3. Review trade-by-trade: Did blocked trades go on to profit?

**Example Analysis**:
```python
import json

with open('logs/trades_20251006.json') as f:
    data = json.load(f)

total_trades = data['summary']['total_trades']
total_blocks = sum(data['analytics']['filter_blocks'].values())

print(f"Trades Taken: {total_trades}")
print(f"Trades Blocked: {total_blocks}")
print(f"Filter Rate: {total_blocks/(total_trades+total_blocks)*100:.1f}%")

for filter_name, count in data['analytics']['filter_blocks'].items():
    pct = count/total_blocks*100
    print(f"  {filter_name}: {count} ({pct:.1f}%)")
```

### 4. Find Best Entry Timing

**Question**: "What time of day has best results?"

**Steps**:
1. Extract entry_time from each trade in JSON
2. Group by hour (10 AM, 11 AM, etc.)
3. Calculate win rate and avg P&L per hour

**Example Analysis**:
```python
from datetime import datetime
from collections import defaultdict

trades_by_hour = defaultdict(list)

for trade in data['summary']['trades']:
    entry_time = datetime.fromisoformat(trade['entry_time'])
    hour = entry_time.hour
    trades_by_hour[hour].append(trade)

for hour in sorted(trades_by_hour.keys()):
    trades = trades_by_hour[hour]
    winners = sum(1 for t in trades if t['pnl'] > 0)
    avg_pnl = sum(t['pnl'] for t in trades) / len(trades)

    print(f"{hour}:00 - {len(trades)} trades, "
          f"{winners/len(trades)*100:.0f}% WR, "
          f"${avg_pnl:.2f} avg")
```

### 5. Track Position Duration

**Question**: "How long should I hold positions?"

**Steps**:
1. Calculate duration for each trade from JSON
2. Compare winners vs losers
3. Find optimal duration range

**Example Analysis**:
```python
from datetime import datetime

winners = []
losers = []

for trade in data['summary']['trades']:
    entry = datetime.fromisoformat(trade['entry_time'])
    exit = datetime.fromisoformat(trade['exit_time'])
    duration = (exit - entry).total_seconds() / 60

    if trade['pnl'] > 0:
        winners.append(duration)
    else:
        losers.append(duration)

print(f"Winner Duration: {sum(winners)/len(winners):.0f} min (avg)")
print(f"Loser Duration: {sum(losers)/len(losers):.0f} min (avg)")
```

---

## Log Files Generated

| File | Purpose | Format | Retention |
|------|---------|--------|-----------|
| `logs/trader_YYYYMMDD.log` | Full session log | Text | Keep all |
| `logs/trades_YYYYMMDD.json` | Structured data | JSON | Keep all |

**Backup**: Keep all log files for analysis. Total size is minimal (~1-5 MB per day).

---

## Troubleshooting

### Problem: Too Much Logging (Log File Too Large)

**Solution**: Use INFO level instead of DEBUG
```yaml
logging:
  log_level: "INFO"  # Less verbose
```

### Problem: Can't See Filter Decisions

**Solution**: Enable DEBUG level
```yaml
logging:
  log_level: "DEBUG"  # More verbose
```

### Problem: Want Real-Time Updates

**Solution**: Use `tail -f` to watch log in real-time
```bash
tail -f logs/trader_20251006.log
```

### Problem: Want to Analyze Past Sessions

**Solution**: All data is in JSON files
```python
import json
import glob

# Load all sessions
sessions = []
for file in glob.glob('logs/trades_*.json'):
    with open(file) as f:
        sessions.append(json.load(f))

# Analyze across all sessions
total_trades = sum(s['summary']['total_trades'] for s in sessions)
total_pnl = sum(s['summary']['daily_pnl'] for s in sessions)
print(f"Total: {total_trades} trades, ${total_pnl:.2f} P&L")
```

---

## Key Metrics to Track

### Daily
- [ ] Win rate (target: 35-45%)
- [ ] Daily P&L (target: $500-1500)
- [ ] Trades taken (target: 3-8)
- [ ] Filter effectiveness

### Weekly
- [ ] Avg daily P&L
- [ ] Profit factor (target: >1.5)
- [ ] Most blocked filter
- [ ] Best entry time

### Monthly
- [ ] Total P&L
- [ ] Consistency (% winning days)
- [ ] Compare to backtest
- [ ] Identify improvement areas

---

## Example Learning Session

**Day 1 Results**: 2 trades, 50% WR, +$300

**Analysis**:
1. Check logs → Choppy filter blocked 15 trades
2. Conclusion: Market was consolidating, filter worked correctly
3. Action: None needed, this is expected behavior

**Day 2 Results**: 8 trades, 25% WR, -$400

**Analysis**:
1. Check logs → Room-to-run filter blocked only 2 trades
2. Check trades → Most losers entered with <1% room
3. Conclusion: Room-to-run filter threshold too low (1.5%)
4. Action: Test increasing to 2.0% in backtest

**Day 3 Results**: 4 trades, 75% WR, +$1200

**Analysis**:
1. Check logs → Entry path breakdown: All pullback/retest
2. Check trades → All entries had >2% room to target
3. Conclusion: Patient entries with room work best
4. Action: Keep current settings, working as expected

---

## Next Steps

1. ✅ Run live trader with INFO logging (default)
2. ✅ Review daily summary after each session
3. ✅ Export JSON to Excel for trend analysis
4. ⏳ After 1 week: Analyze filter effectiveness
5. ⏳ After 2 weeks: Compare to backtest results
6. ⏳ After 4 weeks: Optimize filter thresholds if needed

---

**Remember**: Logs are for learning, not just recording. Review them daily to understand what's working and what needs adjustment.

**Last Updated**: October 6, 2025
