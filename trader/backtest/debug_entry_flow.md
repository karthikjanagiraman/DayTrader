# CRITICAL BUG ANALYSIS - Entry Logic Flow

## The Bug: Room-to-Run Filter Says "BLOCK" But Trade Still Enters

### Entry Flow in Backtester (lines 390-447)

```python
# STEP 1: Check if pivot broken
should_enter, reason = self.strategy.should_enter_long(stock, price, long_attempts)

if should_enter:  # ✅ Returns TRUE if price > resistance
    
    # STEP 2: Check hybrid entry (momentum/pullback/sustained)
    confirmed, confirm_reason, entry_state = self.strategy.check_hybrid_entry(
        bars, bar_count - 1, resistance, side='LONG',
        target_price=stock.get('target1'),
        symbol=stock['symbol'],
        cached_hourly_bars=cached_bars
    )
    
    if confirmed:  # ✅ Returns TRUE if sustained break OR momentum OR pullback
        # ENTER THE TRADE
        position = self.enter_long(...)
```

### Problem Flow for ROKU

**What happened:**
1. Price breaks below support ($99.75)
2. `should_enter_short()` returns TRUE (pivot broken)
3. `check_hybrid_entry()` is called 15+ times (each bar)
4. Each time prints: "Sustained break confirmed! About to return TRUE..."
5. Then prints: "Blocked by room-to-run filter"
6. **BUT** `check_hybrid_entry()` STILL RETURNS **TRUE** on one of those calls!
7. Trade enters even though filter said block

### Root Cause: Multiple Calls with Different Results

The backtester calls `check_hybrid_entry()` **EVERY BAR** after pivot breaks:

```
Bar 870: check_hybrid_entry() → "Blocked by room-to-run" → Return FALSE
Bar 871: check_hybrid_entry() → "Blocked by room-to-run" → Return FALSE
...
Bar 901: check_hybrid_entry() → "Blocked by room-to-run" → Return FALSE (?)
                              → BUT SOMETIMES RETURNS TRUE!!!
```

### Hypothesis

The room-to-run filter is INCONSISTENT or has a BUG where:
- It blocks most of the time
- But occasionally returns TRUE
- Allowing the trade to enter

Let me check the room-to-run filter logic...

