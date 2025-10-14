# Analysis System - Quick Reference

## Daily Routine (5 minutes after market close)

```bash
cd /Users/karthik/projects/DayTrader/trader

# Run complete analysis
./analyze.py all 20251007
```

## Individual Commands

```bash
./analyze.py daily 20251007     # P&L summary
./analyze.py trades 20251007    # Trade patterns
./analyze.py filters 20251007   # Filter effectiveness
./analyze.py scanner 20251007   # Scanner quality
```

## What to Look For

### ✅ Healthy Session
- P&L: $1,000 - $2,000
- Win Rate: 35-50%
- Profit Factor: ≥1.4
- Filters blocking 10-30% of checks
- TIER 1 win rate ≥60%

### ⚠️ Warning Signs
- Win rate <30% (filters too loose)
- Win rate >70% (filters too tight)
- "Position too large" >20% of blocks → Need adaptive sizing
- "5-min rule" losses >$500 → Review confirmation
- TIER 1 win rate <60% → Scanner needs tuning

## Common Adjustments

### Position Sizing Issue
**Symptom**: Many "Position too large" blocks
**Fix**: `trader_config.yaml`
```yaml
position_sizing:
  max_position_value: 20000
```

### Over-Filtering
**Symptom**: <10 trades despite good market
**Fix**: `trader_config.yaml`
```yaml
confirmation:
  choppy_atr_multiplier: 0.4  # Lower from 0.5
  min_room_to_target_pct: 1.0  # Lower from 1.5
```

### 5-Min Rule Losses
**Symptom**: Quick exits losing $500+
**Fix**: Review confirmation strictness
```yaml
confirmation:
  momentum_volume_threshold: 1.2  # Lower from 1.3
```

## File Locations

```
logs/
├── trader_20251007.log          # Full session log
├── trades_20251007.json         # Trade records
└── analysis_20251007.json       # Analysis output

../scanner_validation/
└── rescored_20251007.csv        # Enhanced scoring

../stockscanner/output/
└── scanner_results_20251007.json # Standard scanner
```

## Key Metrics Targets

| Metric | Target | Warning |
|--------|--------|---------|
| Daily P&L | $1,000-2,000 | <$500 or >$3,000 |
| Win Rate | 35-50% | <30% or >70% |
| Profit Factor | ≥1.4 | <1.2 |
| Avg Trade | $50-100 | <$25 |
| Max Loss | <$1,500 | >$2,000 |
| TIER 1 Win% | ≥60% | <50% |

## Quick Diagnosis

### Low P&L Despite Many Trades
→ Check avg trade size (may need larger positions or better R/R)

### High P&L But Few Trades
→ Check filter blocks (may be over-filtering good setups)

### Many Losers from 5-Min Rule
→ Confirmation too strict or min_gain too low

### Many "Position Too Large" Blocks
→ Implement adaptive position sizing immediately

### TIER 1 Underperforming
→ Review scanner scoring logic or pivot width criteria

## Emergency Actions

### Session Lost Money (Daily P&L < -$2,000)
1. Review all trades in detail
2. Identify pattern (all 5-min rule? All one symbol?)
3. Adjust filter IMMEDIATELY before next session
4. Consider skipping next day if confidence low

### Multiple Losing Days
1. Run weekly analysis
2. Check if market conditions changed
3. Review backtest results for comparison
4. Consider tightening filters temporarily

### System Errors
1. Check IBKR connection stats in analysis
2. Review trader log for error patterns
3. Verify TWS/Gateway is stable
4. Check network connectivity

---

**Remember**: Analysis is only useful if you ACT on the insights. Don't just run reports - make adjustments based on data!
