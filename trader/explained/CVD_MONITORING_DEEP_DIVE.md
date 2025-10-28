# CVD Monitoring State - Complete Deep Dive

**Created**: October 27, 2025
**Purpose**: Comprehensive explanation of CVD_MONITORING state with candle-by-candle examples

---

## 📊 What is CVD Monitoring?

**CVD (Cumulative Volume Delta)** monitors the **buying vs selling pressure** on each 1-minute candle to detect institutional accumulation or distribution.

**Entry State**: `CVD_MONITORING`
**Trigger**: Stock breaks pivot but doesn't meet momentum criteria (volume or candle size too weak)
**Goal**: Wait for CVD to signal strong buying/selling pressure before entering

**Formula**:
```
imbalance_pct = (sell_volume - buy_volume) / total_volume × 100

Positive imbalance = More selling (BEARISH)
Negative imbalance = More buying (BULLISH)
```

---

## 🎯 Two Entry Paths

### PATH 1: Aggressive Entry (Strong Spike + Confirmation)

**Criteria**:
- Initial candle: ≥20% imbalance (strong spike)
- Next candle: ≥10% imbalance (confirmation)
- Volume: ≥1.2x average
- Price: Must stay beyond pivot

**Speed**: 2 candles (2 minutes)
**Use Case**: Explosive moves with immediate follow-through

---

### PATH 2: Patient Entry (Sustained Imbalance)

**Criteria**:
- 3 consecutive candles with ≥10% imbalance
- Uses sliding window (searches continuously)
- Volume: ≥1.2x average (PATH 1 only)
- Price: Must stay beyond pivot

**Speed**: 3+ candles (3+ minutes)
**Use Case**: Gradual accumulation/distribution building over time

---

## 📋 Complete State Machine Flow

```
1. Stock breaks pivot (resistance or support)
   ↓
2. Initial volume/candle check → WEAK breakout
   ↓
3. Enter CVD_MONITORING state
   ↓
4. On EVERY 1-minute candle close:
   ├─ Calculate CVD imbalance (buy vs sell volume)
   ├─ Check candle color alignment
   ├─ PATH 1: Check for strong spike (≥20%)
   │  └─ If detected: Wait for next candle confirmation (≥10%)
   │     ├─ Confirmed? → Check filters → ENTER
   │     └─ Failed? → Clear pending spike, continue monitoring
   ├─ PATH 2: Add imbalance to history
   │  └─ Sliding window search for 3 consecutive ≥10%
   │     ├─ Found? → Check filters → ENTER
   │     └─ Not found? → Continue monitoring
   └─ Price validation: Still beyond pivot?
      ├─ Yes → Continue monitoring
      └─ No → RESET (price reversed)
```

---

## 🔍 PATH 1 - Aggressive Entry: Candle-by-Candle Example

### Scenario: NVDA SHORT Entry

**Setup**:
- Pivot: $181.50 (support level)
- Side: SHORT
- Initial breakout: Price breaks below $181.50 at 10:05 AM
- Volume: 0.95x (weak) → Enters CVD_MONITORING

---

### Candle #1: 10:05-10:06 AM

**Data**:
- Price: Open $181.45, Close $181.38, High $181.48, Low $181.35
- Volume: 85,000 shares
- Buy Volume: 30,000 shares (35%)
- Sell Volume: 55,000 shares (65%)

**CVD Calculation**:
```
imbalance_pct = (55,000 - 30,000) / 85,000 × 100 = 29.4%
```

**State Machine Processing**:
```
[CVD_MONITORING] NVDA Bar 181:
  ✅ CVD from CACHE: imbalance=29.4%, trend=BEARISH
  ✅ CANDLE COLOR VALIDATION PASSED (red candle, selling imbalance)

  PATH 1 CHECK:
  strong_imbalance_threshold = 20.0%
  29.4% >= 20.0% ✅

  🔔 STRONG SPIKE detected (29.4% ≥ 20.0%), awaiting confirmation next candle

  state.pending_strong_spike = True
  state.pending_strong_imbalance = 29.4
```

**Result**: Spike detected, waiting for next candle
**Entry**: Not yet (need confirmation)

---

### Candle #2: 10:06-10:07 AM (Confirmation Candle)

**Data**:
- Price: Open $181.38, Close $181.25, High $181.40, Low $181.22
- Volume: 72,000 shares
- Buy Volume: 25,000 shares (35%)
- Sell Volume: 47,000 shares (65%)

**CVD Calculation**:
```
imbalance_pct = (47,000 - 25,000) / 72,000 × 100 = 30.6%
```

**State Machine Processing**:
```
[CVD_MONITORING] NVDA: Checking STRONG SPIKE CONFIRMATION
  Initial: 29.4%
  Current: 30.6%

  confirmation_imbalance = 10.0%
  30.6% >= 10.0% ✅

  ✅ STRONG SPIKE CONFIRMED! (initial 29.4% + confirm 30.6%)

  PRICE VALIDATION:
  pivot = $181.50
  current_price = $181.25
  $181.25 < $181.50 ✅ (still below pivot for SHORT)

  VOLUME FILTER:
  candle_volume = 72,000
  avg_candle_volume = 65,000 (from prev 20 candles)
  volume_ratio = 72,000 / 65,000 = 1.11x

  cvd_volume_threshold = 1.2x
  1.11x < 1.2x ❌

  ❌ VOLUME FILTER - 72,000 shares (1.11x) < 1.2x threshold

  state.pending_strong_spike = False
  tracker.reset_state()

  BLOCKED: "Volume filter: 1.11x < 1.2x"
```

**Result**: Confirmation candle had strong CVD (30.6%) BUT volume filter blocked entry
**Entry**: BLOCKED by volume filter
**Lesson**: ALL filters must pass, not just CVD

---

### Alternative Scenario: Successful PATH 1 Entry

**Candle #2 (Modified)**:
- Volume: 85,000 shares (1.31x average) ✅
- Imbalance: 30.6% ✅

**State Machine Processing**:
```
[CVD_MONITORING] NVDA: Checking STRONG SPIKE CONFIRMATION
  Initial: 29.4%
  Current: 30.6%

  ✅ STRONG SPIKE CONFIRMED!
  ✅ Price $181.25 < pivot $181.50
  ✅ VOLUME PASSED - 85,000 shares (1.31x) >= 1.2x

  STOCHASTIC FILTER:
  ✅ PASSED

  ROOM-TO-RUN FILTER:
  current_price = $181.25
  target_price = $178.50 (downside1)
  room_pct = ($181.25 - $178.50) / $181.25 = 1.52%
  min_room = 1.5%
  1.52% >= 1.5% ✅

  🎯 ENTER SHORT @ $181.25

  Return: (True, "Strong spike confirmed (29.4% + 30.6%)", {
    'phase': 'cvd_aggressive_confirmed',
    'initial_imbalance': 29.4,
    'confirm_imbalance': 30.6
  })
```

**Result**: ENTERED via PATH 1 (aggressive)
**Duration**: 2 minutes from initial breakout

---

## 🔍 PATH 2 - Patient Entry: Candle-by-Candle Example

### Scenario: SMCI SHORT Entry

**Setup**:
- Pivot: $54.50 (support level)
- Side: SHORT
- Initial breakout: Price breaks below $54.50 at 11:30 AM
- Volume: 0.88x (weak) → Enters CVD_MONITORING

---

### Candle #1: 11:30-11:31 AM

**Data**:
- Price: $54.42
- Volume: 38,000 shares
- Buy Volume: 16,000 (42%)
- Sell Volume: 22,000 (58%)

**CVD Calculation**:
```
imbalance_pct = (22,000 - 16,000) / 38,000 × 100 = 15.8%
```

**State Machine Processing**:
```
[CVD_MONITORING] SMCI Bar 205:
  ✅ CVD from CACHE: imbalance=15.8%, trend=BEARISH

  PATH 1 CHECK:
  15.8% < 20.0% (not a strong spike)

  PATH 2 PROCESSING:
  sustained_imbalance = 10.0%
  min_consecutive = 3

  state.cvd_imbalance_history.append(15.8)

  Imbalance history: [15.8]
  len(history) = 1 < 3 (need 3 consecutive)

  Continue monitoring
```

**Result**: First candle added to history, need 2 more
**Entry**: Not yet

---

### Candle #2: 11:31-11:32 AM

**Data**:
- Price: $54.38
- Volume: 42,000 shares
- Buy Volume: 14,000 (33%)
- Sell Volume: 28,000 (67%)

**CVD Calculation**:
```
imbalance_pct = (28,000 - 14,000) / 42,000 × 100 = 33.3%
```

**State Machine Processing**:
```
[CVD_MONITORING] SMCI Bar 206:
  ✅ CVD from CACHE: imbalance=33.3%, trend=BEARISH

  PATH 1 CHECK:
  33.3% >= 20.0% ✅

  🔔 STRONG SPIKE detected (33.3% ≥ 20.0%), awaiting confirmation next candle
  state.pending_strong_spike = True
  state.pending_strong_imbalance = 33.3

  PATH 2 PROCESSING:
  state.cvd_imbalance_history.append(33.3)

  Imbalance history: [15.8, 33.3]
  len(history) = 2 < 3 (need 3 consecutive)

  Continue monitoring (now have pending spike)
```

**Result**: Strong spike detected (PATH 1), also added to history (PATH 2)
**Entry**: Not yet (need confirmation for PATH 1, or 1 more candle for PATH 2)

---

### Candle #3: 11:32-11:33 AM

**Data**:
- Price: $54.35
- Volume: 45,000 shares
- Buy Volume: 18,000 (40%)
- Sell Volume: 27,000 (60%)

**CVD Calculation**:
```
imbalance_pct = (27,000 - 18,000) / 45,000 × 100 = 20.0%
```

**State Machine Processing**:
```
[CVD_MONITORING] SMCI: Checking STRONG SPIKE CONFIRMATION
  Initial: 33.3%
  Current: 20.0%

  confirmation_imbalance = 10.0%
  20.0% >= 10.0% ✅

  ✅ STRONG SPIKE CONFIRMED! (initial 33.3% + confirm 20.0%)

  ... (filters check) ...

  BUT PATH 2 ALSO TRIGGERS:

  state.cvd_imbalance_history.append(20.0)
  Imbalance history: [15.8, 33.3, 20.0]

  SLIDING WINDOW SEARCH:
  sustained_imbalance = 10.0%
  min_consecutive = 3

  Window #1: [15.8, 33.3, 20.0]
    15.8% >= 10.0% ✅
    33.3% >= 10.0% ✅
    20.0% >= 10.0% ✅

  🎯 SUSTAINED SELLING found! 3 consecutive candles: [15.8%, 33.3%, 20.0%]

  (Note: PATH 1 and PATH 2 both trigger - code will enter via PATH 1 first)
```

**Result**: BOTH paths trigger on this candle
**Entry**: ENTERED (via PATH 1 confirmation)
**Duration**: 3 minutes from initial breakout

---

## 🔍 PATH 2 - Sliding Window Example (Advanced)

### Scenario: Non-consecutive pattern

**Imbalance History**: [8.5%, 12.3%, 6.2%, 11.8%, 13.5%, 10.2%]

**Sliding Window Search**:
```
min_consecutive = 3
sustained_imbalance = 10.0%

Window #1: [8.5%, 12.3%, 6.2%]
  8.5% < 10.0% ❌
  FAIL

Window #2: [12.3%, 6.2%, 11.8%]
  6.2% < 10.0% ❌
  FAIL

Window #3: [6.2%, 11.8%, 13.5%]
  6.2% < 10.0% ❌
  FAIL

Window #4: [11.8%, 13.5%, 10.2%]
  11.8% >= 10.0% ✅
  13.5% >= 10.0% ✅
  10.2% >= 10.0% ✅
  MATCH FOUND! ✅
```

**Result**: Pattern found at window #4 (candles 4-6), even though candles 1-3 didn't qualify
**Key Insight**: Sliding window never resets - continuously searches for patterns

---

## ❌ Failure Scenarios

### Scenario A: Price Reversal (PATH 1)

**Candle #1**: Strong spike detected (25.5% selling)
**Candle #2**: Confirmation check
- Imbalance: 18.2% ✅ (≥10% threshold)
- Price: $181.55 ❌ (rose above pivot $181.50)

**Processing**:
```
[CVD_MONITORING] NVDA: Checking STRONG SPIKE CONFIRMATION
  Initial: 25.5%
  Current: 18.2%

  ✅ Confirmation met (18.2% >= 10.0%)

  PRICE VALIDATION:
  pivot = $181.50
  current_price = $181.55
  $181.55 >= $181.50 ❌

  ❌ BLOCKED - Price $181.55 rose above pivot $181.50

  state.pending_strong_spike = False
  tracker.reset_state(symbol)

  Return: (False, "Price rose above pivot", {'phase': 'cvd_price_reversal'})
```

**Result**: CVD confirmed but price invalidated the setup
**Outcome**: BLOCKED, CVD monitoring ends

---

### Scenario B: Candle Color Conflict

**Candle Data**:
- Price: Open $181.45, Close $181.52 (GREEN candle, up $0.07)
- Buy Volume: 20,000 (25%)
- Sell Volume: 60,000 (75%)
- Imbalance: +50% (selling imbalance)

**Processing**:
```
[CVD_MONITORING] NVDA Bar 210:
  CVD imbalance: +50% (BEARISH - more selling)
  Candle color: GREEN (price up)

  CANDLE COLOR VALIDATION:
  signals_aligned = False
  validation_reason = "Bearish CVD (50.0% selling) conflicts with green candle"

  ❌ CANDLE COLOR CONFLICT - Bearish CVD (50.0% selling) conflicts with green candle

  tracker.reset_state(symbol)

  Return: (False, "Candle color conflict: ...", {'phase': 'cvd_candle_color_conflict'})
```

**Result**: CVD shows selling but price went up → conflicting signals
**Outcome**: BLOCKED, CVD monitoring ends
**Reason**: Prevents entries on manipulated/spoofed volume

---

### Scenario C: Confirmation Timeout (PATH 1)

**Candle #1**: Strong spike detected (28.3% selling)
**Candle #2**: Weak confirmation
- Imbalance: 4.2% ❌ (<10% threshold)

**Processing**:
```
[CVD_MONITORING] SMCI: Checking STRONG SPIKE CONFIRMATION
  Initial: 28.3%
  Current: 4.2%

  confirmation_imbalance = 10.0%
  4.2% < 10.0% ❌

  ❌ Confirmation failed (4.2% < 10.0%), clearing pending spike

  state.pending_strong_spike = False

  (Continue monitoring via PATH 2)
```

**Result**: Spike not confirmed, falls back to PATH 2 monitoring
**Outcome**: NOT entered via PATH 1, but continues monitoring for PATH 2

---

### Scenario D: Volume Filter Block (PATH 2)

**Pattern Found**: [12.5%, 11.8%, 10.3%] (3 consecutive ≥10%)
**Volume Check**:
```
candle_volume = 52,000 shares
avg_candle_volume = 68,000 shares
volume_ratio = 52,000 / 68,000 = 0.76x

cvd_volume_threshold = 1.2x
0.76x < 1.2x ❌
```

**Processing**:
```
🎯 SUSTAINED SELLING found! 3 consecutive candles: [12.5%, 11.8%, 10.3%]

✅ Price $54.35 < pivot $54.50

VOLUME FILTER CHECK:
(Note: Volume filter is checked in PATH 1 only, not PATH 2 in current implementation)

STOCHASTIC FILTER:
fails_stochastic = True
stochastic_reason = "Overbought (K: 92.5, D: 88.3)"

❌ BLOCKED - Stochastic filter
```

**Result**: CVD pattern found but stochastic filter blocked entry
**Outcome**: Continue monitoring (don't reset history - filter may pass later)
**Key**: PATH 2 doesn't reset on filter failures, keeps searching

---

## 📊 Real Example: October 21st HOOD SHORT #2

### Actual Data from Validation Report

**Context**:
- Stock: HOOD (Robinhood)
- Side: SHORT
- Pivot: Support level
- Result: 17 candles in CVD monitoring, never entered

**Candle-by-Candle Timeline**:

```
Candle #1-3: Weak imbalances (3-7%)
  → Not enough for sustained pattern

Candle #4-8: Mixed imbalances (2-15%, not consecutive)
  → Sliding window can't find 3 consecutive ≥10%

Candle #9: Price rose above pivot
  → Should have RESET, but continued monitoring (potential bug?)

Candle #10-17: Continued weak/mixed patterns
  → Never found 3 consecutive ≥10%
  → Never triggered strong spike ≥20%

Result: 17 minutes of monitoring, no entry
```

**Why It Failed**:
1. No strong spike (≥20%) ever detected → PATH 1 never triggered
2. No 3 consecutive candles ≥10% → PATH 2 never triggered
3. Imbalance pattern: [7%, 4%, 12%, 5%, 15%, 8%, 11%, ...]
   - Window [12%, 5%, 15%]: Middle value fails (5% < 10%)
   - Window [15%, 8%, 11%]: Middle value fails (8% < 10%)

**Lesson**: Sliding window requires ALL 3 candles ≥10%, not just majority

---

## 🔧 Configuration Parameters

```yaml
confirmation:
  cvd:
    enabled: true

    # Monitoring settings
    continuous_monitoring: true
    max_monitoring_time_minutes: 999   # No timeout
    check_every_candle: true           # Check on every 1-min close

    # PATH 2: Sustained imbalance
    min_consecutive_bullish: 3         # LONG: 3 consecutive buying candles
    min_consecutive_bearish: 3         # SHORT: 3 consecutive selling candles
    imbalance_threshold: 10.0          # 10% sustained imbalance

    # PATH 1: Strong spike + confirmation
    strong_imbalance_threshold: 20.0   # Initial spike ≥20%
    strong_confirmation_threshold: 10.0 # Next candle ≥10%

    # Volume filter (PATH 1 only in current implementation)
    cvd_volume_threshold: 1.2          # 1.2x average volume

    # Calculation
    slope_lookback: 5                  # Used for divergence detection
```

---

## 🎯 Key Insights

### PATH 1 (Aggressive)

**Strengths**:
- Fast entry (2 minutes)
- High conviction (strong CVD spike)
- Includes volume filter (quality check)

**Weaknesses**:
- Rare (requires ≥20% spike)
- Can fail confirmation (need ≥10% follow-through)
- Volume requirement (1.2x)

**Best For**: Explosive breakouts with institutional activity

---

### PATH 2 (Patient)

**Strengths**:
- Catches gradual accumulation
- Sliding window (never resets)
- More forgiving (10% vs 20%)

**Weaknesses**:
- Slower entry (3+ minutes)
- No volume filter (in current implementation)
- Can monitor for long periods without entry

**Best For**: Steady accumulation/distribution patterns

---

## 🚨 Common Pitfalls

### Pitfall #1: "CVD looks good but didn't enter"

**Likely Causes**:
1. Volume filter blocked (PATH 1): <1.2x average
2. Price reversed (crossed back over pivot)
3. Candle color conflict (CVD bearish but green candle)
4. Stochastic filter blocked (overbought/oversold)
5. Room-to-run filter blocked (<1.5% to target)

**Solution**: Check logs for filter that blocked entry

---

### Pitfall #2: "Why did it monitor for 17 candles without entering?"

**Likely Causes**:
1. Never found 3 consecutive ≥10% (PATH 2)
2. Never detected ≥20% spike (PATH 1)
3. Filters kept failing (stochastic, room-to-run)
4. Pattern exists but not consecutive (e.g., [12%, 8%, 11%])

**Solution**: Review imbalance history, check for gaps <10%

---

### Pitfall #3: "Strong spike detected but not confirmed"

**Likely Causes**:
1. Next candle <10% imbalance (confirmation failed)
2. Price reversed before confirmation
3. Volume <1.2x on confirmation candle

**Solution**: PATH 1 falls back to PATH 2, continues monitoring

---

## 📈 Success Metrics

**Ideal CVD Entry** (PATH 1):
```
Candle #1: 28% imbalance → Spike detected
Candle #2: 15% imbalance → Confirmed
Volume: 1.35x average → Passed
Price: Still beyond pivot → Passed
Stochastic: Not overbought → Passed
Room: 2.3% to target → Passed

Result: ENTERED in 2 minutes
```

**Ideal CVD Entry** (PATH 2):
```
Candles 1-3: [12.5%, 11.8%, 13.2%] → Pattern found
Price: Still beyond pivot → Passed
Stochastic: Not overbought → Passed
Room: 1.8% to target → Passed

Result: ENTERED in 3 minutes
```

---

## 🔍 Debugging CVD Monitoring

### Step 1: Check if CVD monitoring started
```
grep "CVD_MONITORING" trader/logs/trader_YYYYMMDD.log
```

### Step 2: Check imbalance values
```
grep "imbalance=" trader/logs/trader_YYYYMMDD.log | grep SYMBOL
```

### Step 3: Check for strong spikes
```
grep "STRONG SPIKE detected" trader/logs/trader_YYYYMMDD.log
```

### Step 4: Check for sustained patterns
```
grep "SUSTAINED" trader/logs/trader_YYYYMMDD.log
```

### Step 5: Check filters
```
grep "VOLUME FILTER\|PRICE VALIDATION\|CANDLE COLOR" trader/logs/trader_YYYYMMDD.log
```

---

## 🎓 Conclusion

**CVD Monitoring** provides two complementary entry paths:

1. **PATH 1 (Aggressive)**: For explosive moves with strong institutional activity
2. **PATH 2 (Patient)**: For gradual accumulation/distribution patterns

**Key Success Factors**:
- Volume must support CVD signal (≥1.2x for PATH 1)
- Price must stay beyond pivot (no reversals)
- Candle color must align with CVD direction
- All filters must pass (stochastic, room-to-run)

**When It Works Best**:
- Strong directional pressure (buying or selling)
- Consistent volume patterns
- Clear price trend beyond pivot
- Not overbought/oversold (stochastic)

**When It Struggles**:
- Choppy/mixed volume patterns
- Price whipsaws around pivot
- Volume spikes then dies (no follow-through)
- Overbought/oversold conditions

---

**For More Information**:
- Implementation: `trader/strategy/ps60_entry_state_machine.py` (lines 550-912)
- Configuration: `trader/config/trader_config.yaml` (lines 393-439)
- CVD Calculator: `trader/indicators/cvd_calculator.py`
