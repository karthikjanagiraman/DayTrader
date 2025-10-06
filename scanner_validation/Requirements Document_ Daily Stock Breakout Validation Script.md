# Requirements Document: Daily Stock Breakout Validation Script

## Objective

Create a validation script that takes the daily stock scanner output (e.g. from Oct 1, 2025) and verifies, using intraday market data, which of those stocks actually broke out (upward or downward) the next trading day and whether those breakouts hit their price targets or turned into false breakouts. This will help back-test and validate the scanner's signals by comparing predicted breakout levels against actual intraday price movements.

## Data Inputs and Sources

### Scanner Output File (CSV)

The daily scanner results for a given date, containing the list of stock tickers and their technical levels. For example, the Oct 1, 2025 scanner output file includes columns like:

- **symbol** – Ticker symbol (e.g., NVDA, SPY, TSLA)
- **close** – Prior day closing price
- **resistance** – Key resistance level identified (potential breakout level to the upside)
- **support** – Key support level identified (potential breakdown level to the downside)
- **target1, target2, target3** – Projected upside target prices if a long breakout (upward move) occurs beyond resistance
- **downside1, downside2** – Projected downside target prices if a short breakout (downward move) occurs below support
- (Additional columns like dist_to_R%, dist_to_S%, breakout_reason, moving averages, etc., provide context but are mainly informational for the scan. The script may not need these for validation logic except as reference.)

### Market Data Source (Intraday Prices)

IBKR (Interactive Brokers) market data will be used to retrieve intraday price information for each stock on the trading day following the scanner date. The script will connect to IBKR's API (TWS or IB Gateway) to fetch high-resolution intraday data (e.g. 1-minute bars or at least daily High/Low prices) for each stock on that date. This data is needed to determine if and when the stock price crossed the scanner's support/resistance levels and how far it moved thereafter.

**Example:** For the Oct 1, 2025 scanner output (which reflects market conditions on Oct 1), the script will retrieve intraday data for Oct 2, 2025 for all listed symbols. (If the scanner output is intended for the same day's session, the script would use that day's intraday data instead. Assumption: The scanner output is generated after market close, listing setups for the next trading day.)

The IBKR API's historical data endpoint can provide the necessary intraday price series or at least daily high/low values. Ensure the script has appropriate permissions and subscriptions for each symbol (stock or ETF) to get real-time/historical data via IBKR.

## Key Definitions

### Breakout (Long)
Price moving above the identified resistance level. This is a bullish breakout trigger. We consider a breakout occurred if the stock's intraday high price is >= the resistance level on the target day.

### Breakdown (Short Breakout)
Price moving below the identified support level. This is a bearish breakdown trigger. A breakdown is considered to have occurred if the intraday low price is <= the support level.

### Breakout Confirmation (Successful Breakout)
The breakout is considered confirmed/successful if, after breaking the level, the price showed follow-through momentum by reaching the first target (target1) or coming very close to it intraday. In other words, the move sustained enough to approach the expected profit target. (The threshold for "very close" can be defined, e.g. within a few ticks or a small percentage of the target price.)

### False Breakout
A breakout that fails to sustain beyond the support/resistance level – the price moves past the level briefly but then reverts back into the prior range without hitting the intended target. In day-trading terms, the price "breaks out" but quickly reverses direction, trapping traders who bought the breakout or sold the breakdown. In this context, we identify a false breakout if the price crosses the level but does not reach the nearest target and subsequently falls back below the breakout level (for an upside break) or rises back above the breakdown level (for a downside break) during the same session. As trading literature notes, "a false breakout is a significant movement out of a market's normal support or resistance levels that doesn't last – hence it 'fails'"[1].

**Example:** False Breakout Patterns – The left chart shows a false-break of a key resistance (price briefly moved above the red line then fell back below it), and the right chart shows a false-break of support (price dipped below the support line then bounced back). In both cases the breakout did not last, indicating a bull trap (left) and bear trap (right). Such moves can mislead traders into expecting a continued trend, only for the price to revert[2].

### Both Directions
Occasionally, a stock might trigger both an upward breakout and a downward breakout in the same day (for instance, in a volatile session it could break below support early on and later rally above resistance, or vice versa). The script will account for and report such cases separately for each direction.

## Functional Requirements

The validation script must perform the following steps for each stock listed in the scanner output, without ignoring any symbols (including indices or ETFs like SPY, QQQ, etc.):

### 1. Read Scanner Data

Load the scanner output for the specified date (e.g., scanner_results_20251001.csv for Oct 1, 2025). Parse each line to extract:

- symbol (e.g., "NVDA")
- resistance level
- support level
- target1 (primary upward target)
- downside1 (primary downward target)
- (Optional: target2, target3, downside2 if needed for extended analysis, though primary targets are usually enough for basic validation)

### 2. Retrieve Intraday Price Data

For each symbol, fetch the intraday price data for the next trading day (since the scanner likely identifies potential breakouts for the following session). Use IBKR API calls to get at least the day's High, Low, and ideally the time-series of price movements.

- If using the IBKR API, request 1-minute bar data for the full trading session of that date for accuracy. Alternatively, at minimum, get Daily OHLC data (which includes the day's high and low price).
- Ensure that the date in question is a trading day. If the scanner date is a Friday or the day before a market holiday, the "next trading day" should skip to the following market-open day.
- **Do not skip any symbols:** if a data request fails for a particular ticker (e.g., due to an API issue or subscription), the script should log the error and attempt to continue or use an alternative method, but ultimately every symbol in the list must be accounted for in the output (even if noted as "data not available" or similar error, rather than silently dropping it).

### 3. Determine Breakout Occurrence

Using the intraday data:

#### Upward Breakout Check (Long)
Compare the day's High price to the resistance level.
- If High >= resistance, then an upward breakout occurred at some point during the day. Note the time if possible (e.g., 10:30 AM) when it first crossed the resistance, which can be derived from minute data.
- If High < resistance, then no upward breakout occurred that day (price never exceeded the resistance level).

#### Downward Breakout Check (Short)
Compare the day's Low price to the support level.
- If Low <= support, then a downward breakout (breakdown) occurred intraday.
- If Low > support, then no downward breakout occurred (price never dropped below support).

### 4. Evaluate Breakout Outcome

For each breakout that occurred (either direction), determine if it was a confirmed breakout (hit target) or a false breakout:

#### If an upward breakout occurred (price crossed above resistance):

Check if the price reached at least the first target (target1). This can be done by comparing the day's High to target1.

- If High >= target1, the stock hit its first target (or beyond) on the breakout. This is considered a **successful/confirmed long breakout**. The breakout had follow-through momentum.
- If High fell short of target1 but came very close (within an acceptable margin, e.g. within a few tenths of a percent or a few cents), you may also consider it achieved the breakout objective (for example, hitting 95%+ of the target distance could count as "near target"). This threshold should be defined (perhaps configurable) in the script.
- If High did not reach near the target, then the breakout failed to hit its objective. Now check if the price fell back below the resistance level after the breakout:
  - If the stock's closing price (or any subsequent significant pullback intraday) is below the resistance level, it indicates a **false breakout** – the price could not sustain above the broken level and reverted back into the range[1]. In practical terms, the stock gave a bullish signal by breaking out, but then pulled back below that level and never resumed upward that day.
  - If the stock remained above the old resistance (now support) into the close but just didn't reach the target, we might not label it as a "false" breakout (since it didn't actually fail or trap traders – it still closed higher than the breakout level). Instead, that would be an **unconfirmed breakout** (lack of target achievement) but not a full failure. However, for simplicity, the script can categorize any breakout that didn't reach a target as "not confirmed," and only use the term "false breakout" when there was a clear reversion back below the level. (This distinction can be noted in the output.)

#### If a downward breakout occurred (price broke below support):

Check if the price dropped to at least the first downside target (downside1). For example, if support was $50 and downside1 is $48, did the intraday Low reach $48 or below?

- If Low <= downside1, then the short breakout succeeded in hitting its first target (**confirmed breakdown**).
- If Low did not reach the target (stayed above downside1) and instead the price rebounded back above the support level, then it was a **false breakdown** (a bear trap). In this scenario, the stock gave a bearish signal by breaking support, but failed to continue lower and buyers pushed it back into the range. For instance, a stock dipping under support at $50 but then recovering to $51 by midday, never reaching $48, would qualify as a false breakout to the downside.
- If the price broke down but remained just under the support level without hitting the target by close, that's an **unconfirmed breakout** (didn't reach target, but also didn't clearly reject the level). Like above, the script can simply mark it as "no target hit" (not confirmed) if no bounce back above support occurred.

#### No breakout

If neither resistance nor support was breached intraday, the stock had no breakout that day. The script should record that outcome (the stock stayed within the set range), as this also validates the scanner (in this case the scanner identified a setup but the trigger didn't happen).

### 5. Handle Dual Breakouts

If a stock triggers both an upside and downside breakout in the same session (for example, gaps down below support then later rallies above the original resistance):

- The script should evaluate each direction separately as above. It should be possible to have, say, a false breakdown in the morning and a successful breakout in the afternoon for the same stock (or vice versa). Each should be identified and reported.
- This scenario is rare but the script logic should not assume only one direction per stock. Use the intraday data to catch both events if they occur.

### 6. Compile Results

For each stock, produce a summary of what happened:

- Whether an upward breakout occurred, and if so, whether it hit target1 (or came close) or was a false breakout (failed breakout).
- Whether a downward breakout occurred, and if so, whether it hit downside1 or was a false breakdown.
- If no breakout occurred in a particular direction, note that it stayed below resistance (no long breakout) or stayed above support (no short breakout) as applicable.
- If no breakout occurred at all, you can note that the stock remained range-bound that day (neither long nor short trigger was hit).

## Output Format

The script should output the validation results in a clear, structured format for easy analysis. Possible output formats:

### CSV/Spreadsheet

A table with columns for symbol, and outcome columns (Long Breakout Occurred Y/N, Long Target Hit Y/N or False Breakout, Short Breakout Y/N, Short Target Hit Y/N or False Breakout). For example:

| Symbol | Long Breakout? | Long Outcome           | Short Breakout? | Short Outcome            |
|--------|----------------|------------------------|-----------------|--------------------------|
| NVDA   | Yes – broke $187.35 | ❌ False (reversed, no target hit) | No | – (stayed above $178.24) |
| COIN   | No             | – (stayed below $343.44) | Yes – broke $327.02 | ✅ Hit $318.81 target (confirmed) |
| PLTR   | Yes – broke $18.224 | ✅ Near Target (reached $18.14)    | No  | – (stayed above $17.842)  |
| ...    | ...            | ...                    | ...             | ...                      |

*(This is just an illustrative example; the actual outcomes would be computed from real intraday data.)*

### Textual Report

Alternatively, a written summary per stock, e.g.:

- "NVDA: Broke above resistance $187.35 around 11:00 AM but failed to reach $191.91 target (day's high $189). Reversed below $187.35 by close – False breakout. No downside break (support $178.24 held)."
- "COIN: No upside breakout (stayed below $343.44). Broke below support $327.02 at 10:15 AM, reaching $318.50 low which surpassed downside target $318.81 – Successful short breakout."

The format should be easy to read and highlight which setups worked and which failed. Using a table or well-structured bullet points for each stock is recommended for clarity.

### Analysis Metrics (Optional)

The script might also compute some aggregate statistics if desired, for example:

- Total number of stocks that had a breakout (out of the list)
- Number of successful breakouts vs false breakouts (could be a simple success rate for the scanner's picks hitting their targets)
- Separate stats for long side vs short side performance

These are not explicitly requested but could be a useful extension in the requirements if the user wants a summary view of scanner accuracy.

## Example Scenario (Using Oct 1, 2025 Scanner Output)

To illustrate, here's how the script would handle a few entries from the Oct 1, 2025 scanner output (note: hypothetical outcomes for demonstration):

### NVDA
**Resistance $187.35, Support $178.24, Target1 $191.91, Downside1 $173.68**

On Oct 2, suppose NVDA's intraday high was $188.50 and it closed at $186.00. It did break above $187.35 (long breakout occurred), but did not reach the $191.91 target (high fell short). It also closed back below $187.35, indicating the breakout didn't hold. Thus, NVDA had a false upside breakout (no confirmed long target hit). Its intraday low stayed above $178, so there was no short breakout.

*(The script would record NVDA: Long breakout – false (no target hit, reverted), Short breakout – no.)*

### COIN
**Resistance $343.44, Support $327.02, Target1 $351.65, Downside1 $318.81**

On Oct 2, COIN's price never went above $343 (no upside breakout), but did fall below $327.02 in the morning. The low of the day was $319.00, which is roughly at the first downside target (very close to $318.81). If it hit or nearly hit $318.81, we count that as a successful short breakout (target reached). If it also closed well below $327.02, the breakdown was sustained.

*(Script output: COIN: Long breakout – no; Short breakout – yes, target hit ~($319 reached) confirmed.)*

### PLTR
**Resistance $18.224, Support $17.842, Target1 $18.414**

On Oct 2, suppose PLTR broke above $18.224 in the afternoon, reaching an intraday high of $18.40 before pulling back slightly and closing at $18.30. Here, the breakout did occur and it got very close to target1 ($18.414) – within a few cents. This would count as a confirmed long breakout (hit/nearly hit the target). It remained above the old resistance, so no false breakout. No break of support occurred.

*(Script output: PLTR: Long breakout – yes, reached ~99% of target (confirmed); Short breakout – no.)*

### SPY
**Resistance $666.65, Support $662.83, Target1 $668.56, Downside1 $660.92**

SPY on Oct 2 might have been choppy but let's say it broke above $666.65 early, but only got to a high of $667 (didn't quite hit $668.56 target), then reversed down, even dipping below $662.83 briefly, and finally closed at $664. This would be a complex case: an upside breakout that failed (false long breakout, since it reversed before target and fell back under resistance), and also a downside breakout in the same day (breaking support) but that too didn't reach the $660.92 target and then recovered above $662.83 by close – i.e., also a false breakdown.

*(Script output: SPY: Long breakout – yes but false (no target, fell back); Short breakout – yes but false (no target, recovered).)*

The script should be able to handle all such scenarios and label them appropriately.

## Edge Cases & Considerations

### No Breakout vs. False Breakout

It's important to distinguish between a stock that never broke the level (no breakout occurred) and one that broke it but failed. The script's logic outlined above handles this by first checking High/Low relative to the levels:

- If no breach, outcome is simply "no breakout"
- If breach but no follow-through, outcome is "false breakout" (with details)
- If breach with follow-through to target, outcome is "successful breakout"

### Multiple Target Levels

The scanner output often provides up to 3 upward targets (and 2 downward targets). This validation script primarily checks reaching target1 (the first target) as the basic measure of success. However, it could be extended to see if target2 or target3 were reached for a stronger move. For the requirements, hitting target1 (or close to it) is sufficient to call it a confirmed breakout. Not reaching target1 means the higher targets by definition weren't reached either (so the breakout was weak/failed). If target1 is hit, the script might optionally check if target2 was also achieved, and report that (e.g. "Target1 hit, target2 also hit" or "target1 hit but not target2"). This detail can provide more nuance but isn't strictly necessary for the basic validation.

### "Very Close" to Target Definition

The script should allow a tolerance for calling a move "close enough" to the target. This could be a configurable percentage of the stock price or of the gap between breakout level and target. For example, within 0.5% of target price could qualify as achieving the intended move. This prevents classifying a breakout as false just because it missed the target by a few cents. In the requirements, simply note that "very close to target" means within an acceptable small range, to be defined (e.g., 0.5% or a few ticks).

### Time-of-day Sensitivity

While not a strict requirement, noting when the breakout happened can be useful (e.g., a breakout in late afternoon might not reach target before market close even if momentum is strong). The script could log the timestamp of the breakout for additional analysis, but the core requirement is just hit/miss outcome by end of day. So time data is optional for the output, but will be available from intraday data if needed.

### Holidays/Weekends

If automating this script daily, ensure it accounts for non-trading days. The scanner might not produce output on weekends, but if running for Friday's list, the next trading day is Monday (or Tuesday if Monday holiday). The data-fetch logic should handle that (the IBKR API's historical data request can specify an exact date and will return the nearest trading day's data).

### Error Handling

In case a symbol is not recognized by IBKR or data is missing (e.g., a stock that has just IPO'd or an unusual ticker):

- The script should mark that stock with an error or "data unavailable" in the output, rather than ignoring it. (This ties to "don't ignore any stock in the scanner output".) Every ticker in the input list should have an entry in the results, even if the entry is "Could not retrieve data for XYZ" so the user knows it wasn't forgotten.
- Log any API errors or missed data for troubleshooting.

### Performance

If the scanner output has many symbols, fetching intraday data for each serially could be time-consuming. The requirements might include that the script should run efficiently:

- Possibly use IBKR's API in an asynchronous or batched manner (IB allows one historical data request at a time by default, but you can queue them). Alternatively, if only daily high/low is needed, one could use a lighter API or even a public API for daily data as a backup (though IBKR is preferred for accuracy).
- However, since typically the scanner might output a manageable number of tickers (for Oct 1, 2025 we have 8 symbols), performance is not a huge concern. Just ensure the script waits for IBKR rate limits between requests if needed.

### Extensibility

This script is focused on intraday validation of breakout signals. In the future, one could extend it to track if a breakout eventually succeeded on a later day (e.g. maybe it was a false breakout on day 1 but then broke again on day 3 and hit target). For now, the scope is strictly the day following the scanner output ("intraday only" as specified).

## Conclusion

By following these requirements, the validation script will systematically verify each scanner-picked stock's performance. It will identify which stocks truly broke out and hit their targets and which ones ended up being false breakouts (or no breakouts at all). This produces a clear feedback loop for the scanner's efficacy. Traders can use this output to refine their strategies – for example, understanding how often the scanner's "near breakout" candidates actually follow through versus fake out.

Ultimately, this tool leverages IBKR's reliable intraday data to ensure no stock from the scanner output is overlooked, providing a comprehensive daily breakout validation report. The result is a well-organized breakdown of Oct 1, 2025 (as an example) scanner signals versus actual market movements on Oct 2, 2025, which can be generalized to any trading day's analysis going forward.

## References

[1] [What is a False Breakout and How Do You Avoid It? | IG International](https://www.ig.com/en/trading-strategies/what-is-a-false-breakout-and-how-can-you-avoid-it--230130)

[2] [Understanding False Breakouts in Day Trading - Warrior Trading](https://www.warriortrading.com/understanding-false-breakouts-in-day-trading/)
