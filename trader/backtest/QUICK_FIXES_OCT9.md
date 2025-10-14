# Quick Fixes for October 9 Backtest Issues

## Problem Summary

**Backtest Results**: 30 trades, -$13,793 P&L, 13.3% win rate

**Root Cause**: Confirmation logic too strict → late entries → missed moves

**Evidence**: Log analysis showed 4,600+ failed confirmation attempts across all stocks

---

## Top 3 Critical Fixes (In Priority Order)

### 1. 🔥 CRITICAL: Relax Room-to-Run Filter (1.5% → 0.75%)

**Problem**: 4,600 failed attempts blocked C and META entirely

**File**: `trader/config/trader_config.yaml` line 79

```yaml
# CHANGE THIS:
min_room_to_target_pct: 1.5

# TO THIS:
min_room_to_target_pct: 0.75
```

**Impact**: Will allow trades with 0.75-1.5% targets (still profitable), unblocks C/META

---

### 2. 🔥 HIGH: Reduce Candle Wait Time (60 sec → 30 sec)

**Problem**: 261+ failures waiting for 1-minute candle close (PYPL, COIN)

**File**: `trader/config/trader_config.yaml` line 82

```yaml
# CHANGE THIS:
bars_per_candle: 12  # 60 seconds

# TO THIS:
bars_per_candle: 6   # 30 seconds
```

**Impact**: 50% faster entries, less slippage

---

### 3. 🔥 HIGH: Disable Pullback Requirement

**Problem**: Adds unnecessary delay waiting for price to retrace

**File**: `trader/config/trader_config.yaml` line 83

```yaml
# CHANGE THIS:
require_pullback_retest: true

# TO THIS:
require_pullback_retest: false
```

**Impact**: Enter on first confirmation instead of waiting for pullback

---

## Testing Commands

### Before Changes (Baseline)
```bash
cd /Users/karthik/projects/DayTrader/trader/backtest
python3 backtester.py --scanner ../../stockscanner/output/scanner_results_20251009.json --date 2025-10-09 --account-size 100000

# Expected: 30 trades, -$13,793 P&L, 13.3% win rate
```

### After Fix #1 (Room-to-Run = 0.75%)
```bash
# Edit trader_config.yaml first (change min_room_to_target_pct to 0.75)
python3 backtester.py --scanner ../../stockscanner/output/scanner_results_20251009.json --date 2025-10-09 --account-size 100000

# Expected: 35-40 trades (C and META now enter), improved P&L
```

### After Fix #2 (30-second candles)
```bash
# Edit trader_config.yaml (change bars_per_candle to 6)
python3 backtester.py --scanner ../../stockscanner/output/scanner_results_20251009.json --date 2025-10-09 --account-size 100000

# Expected: Faster entries, less "Waiting for candle close" failures
```

### After Fix #3 (No pullback)
```bash
# Edit trader_config.yaml (change require_pullback_retest to false)
python3 backtester.py --scanner ../../stockscanner/output/scanner_results_20251009.json --date 2025-10-09 --account-size 100000

# Expected: Immediate entries after candle confirmation
```

### All Fixes Combined
```bash
# Apply all 3 fixes to trader_config.yaml
python3 backtester.py --scanner ../../stockscanner/output/scanner_results_20251009.json --date 2025-10-09 --account-size 100000

# Expected: 40-50 trades, 25-35% win rate, -$5k to +$2k P&L
```

---

## Validation Checklist

After each fix, check the log file for these improvements:

✅ **Fix #1 Validation** (Room-to-run):
- [ ] C and META show entries instead of "Insufficient room to target"
- [ ] Trade count increases by 5-10

✅ **Fix #2 Validation** (Candle size):
- [ ] "Waiting for 1-min candle close" failures decrease by 50%
- [ ] Entry bars are 6-12 bars earlier than before

✅ **Fix #3 Validation** (Pullback):
- [ ] No more "Waiting for pullback" messages
- [ ] Entries happen immediately after candle confirmation

---

## Expected Performance Improvement

| Metric | Before | After (Conservative) | After (Aggressive) |
|--------|--------|---------------------|-------------------|
| **Trades** | 30 | 40-45 | 50-60 |
| **Win Rate** | 13.3% | 25-30% | 30-35% |
| **P&L** | -$13,793 | -$5k to +$2k | +$3k to +$8k |
| **Entry Delay** | 60-400 bars | 30-200 bars | 10-50 bars |

**Conservative = Fix #1 + #2 only**
**Aggressive = All 3 fixes**

---

## Next Steps

1. **Immediate**: Apply Fix #1 (room-to-run = 0.75%) and re-run Oct 9
2. **If successful**: Apply Fix #2 (30-sec candles) and re-test
3. **If still good**: Apply Fix #3 (no pullback) and re-test
4. **Final test**: Run full month backtest (Sept 1-30) with all fixes
5. **Deploy**: If month backtest shows +$5k+ P&L, deploy to live paper trading

---

## Files Modified

- ✅ `trader/backtest/CONFIRMATION_LOGIC_ANALYSIS.md` - Full analysis report
- ✅ `trader/backtest/QUICK_FIXES_OCT9.md` - This quick reference
- ⏳ `trader/config/trader_config.yaml` - Pending user approval to modify

**DO NOT modify code without user approval!**
