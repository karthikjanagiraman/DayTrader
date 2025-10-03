# ⚠️ CRITICAL WARNING: SCANNER DUPLICATION BUG ⚠️

## THE PROBLEM

**`run_monthly_backtest.py` uses a BROKEN embedded scanner that produces FALSE results!**

## IMPACT - THIS IS CATASTROPHIC

### Incident #1 (October 1, 2025)
- **Embedded scanner result**: -$7,986 P&L (33.6% win rate)
- **Production scanner result**: +$8,895 P&L (39.9% win rate)
- **Difference**: $16,881 swing!

### Incident #2 (October 3, 2025)
- **Embedded scanner result**: -$56,362 P&L (26.8% win rate) ❌ WRONG
- **Production scanner result**: +$8,895 P&L (39.9% win rate) ✅ CORRECT
- **Difference**: $65,257 swing!

## WHY THIS KEEPS HAPPENING

1. Someone (Claude or developer) creates a "simplified" or "historical" version of the scanner
2. They embed it in the backtest script instead of importing production code
3. The embedded scanner is missing critical scoring logic
4. Backtest results are completely wrong
5. We waste time debugging non-existent strategy problems

## THE SOLUTION

### ❌ WRONG (What we're doing now):
```python
class HistoricalScanner:
    """Scanner that works with historical dates"""
    # ... 200 lines of duplicated/simplified scanner logic
```

### ✅ CORRECT (What we MUST do):
```python
# Import the ACTUAL production scanner
from scanner import Scanner

# Use it with historical date parameter
scanner = Scanner()
results = scanner.scan(date=historical_date)
```

## MANDATORY RULES

**When you need scanner functionality in ANY script:**

1. ✅ **ALWAYS import production scanner** from `stockscanner/scanner.py`
2. ✅ **NEVER create embedded/simplified scanners** - this is BANNED
3. ✅ **ASK FIRST** if you think you need a "special version"
4. ✅ **Verify results** match production scanner before trusting them

**If you see yourself typing `class` followed by any word containing "Scanner":**
- **STOP IMMEDIATELY** ✋
- **Ask if this is the right approach** 🤔
- **Explain why you think duplication is needed** 📝
- **Wait for approval** ⏸️

## HOW TO FIX run_monthly_backtest.py

1. **Delete** the entire `HistoricalScanner` class (lines 39-257)
2. **Import** production scanner: `from scanner import Scanner`
3. **Modify** production scanner to accept historical date parameter
4. **Test** that results match previous production scanner backtest
5. **Never** create embedded scanners again

## THIS HAS HAPPENED TWICE - IT MUST NEVER HAPPEN AGAIN

See CLAUDE.md "🚨 CRITICAL LESSON LEARNED - SCANNER DUPLICATION BUG 🚨" for full details.

---

**Last Updated**: October 3, 2025
**Status**: ⚠️ UNFIXED - Do not use run_monthly_backtest.py until corrected
