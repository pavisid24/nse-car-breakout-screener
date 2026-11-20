# Video-derived CAR positive-breakout strategy

Source video: https://youtu.be/2MjnPmUePl0
Companion article/code walkthrough: https://nishatimes.com/kaunsa-stock-kharide-screener/

## Rules transcribed from the source

1. Build a candidate universe from NSE F&O underlyings (the video/article refers to roughly 210 names).
2. Prefer high traded volume, high price fluctuations, six-month average delivery value above ₹35 crore, non-promoter/free-float holding above 20%, free-float value above ₹1,500 crore and companies within the top 500 by market capitalisation.
3. Calculate 30-, 50- and 200-session simple moving averages from daily closing prices.
4. Find the highest daily High during the latest 252 trading sessions.
5. Starting from that high date, calculate CAR as the expanding mean of daily closing prices.
6. Require the latest 10 CAR values to be monotonically increasing. The published Python code uses pandas `is_monotonic_increasing`, which allows equal adjacent values; it is not simply CAR > 0.
7. Require current close above 30, 50 and 200 DMA.
8. The article prose says the stock should not be more than 10% above 200 DMA. The sample code shown in the article does not implement this cap. The app implements it as a separate configurable rule to follow the prose.
9. Rank passed stocks by the smallest positive percentage distance above 200 DMA.
10. The article also mentions no more than one stock purchase and one stock sale in a day, and a 6.28% profit-booking level.

## What this app adds or changes

- Uses imported NSE CM-UDiFF daily Bhavcopy OHLCV rather than the article's sample Yahoo Finance download.
- Requires 252 daily observations for a full 52-week-high lookback and 200 DMA.
- Makes the 10% distance-to-200-DMA cap explicit and adjustable.
- Converts the qualitative volume / volatility conditions into user-adjustable screening thresholds: latest volume divided by 20-day average volume, and ATR(14) as a percentage of close. The video does not specify numeric thresholds for these, so they are application settings, not source-mandated constants.
- Calculates free-float value as market capitalisation × free-float percentage. This depends on the uploaded fundamentals file being current and consistently defined.
- Requires a current NSE F&O underlying list upload if the user wants the scanner constrained to that exact universe. If no F&O list is uploaded, the app scans the entered symbols / imported NSE symbol universe and does not claim it is F&O-only.
- Delivery value, free float, free-float value and Nifty 500 membership are supplementary CSV metrics. They cannot be inferred from regular CM Bhavcopy alone. When the supplementary-data filter is enabled, missing values do not pass.

## Data formats

### F&O list CSV

A one-column CSV is enough. Accepted column names include `SYMBOL`, `TckrSymb`, `UNDERLYING`, `SECURITY`, or `NAME`.

### Delivery CSV

Use the format documented in `SCREENING_DATA_FORMAT.md`, with at least Symbol, Date, DeliverableQty and Close. The app computes daily delivery value = DeliverableQty × Close / 1 crore, then takes the average over the most recent six months available in the file.

### Fundamentals CSV

Required for all fundamental filters: Symbol, MarketCapCr, FreeFloatPct, IsNifty500. The free-float value is computed inside the app. Use a dated, current dataset and confirm the definition/source of free float before relying on it.

## Important omissions in the source strategy

The video/article does not define a stop loss, position-sizing formula, gap-risk handling, maximum holding period, or what to do if the 6.28% target is never reached. It does not provide a sufficiently complete exit system for a trustworthy return backtest. Therefore this app is a screener and candidate-ranking tool; it does not claim to backtest the complete strategy or recommend automatic orders. The 6.28% level is displayed as a reference target only.

## Data quality warning

NSE Bhavcopy daily prices are end-of-day records. Corporate actions such as splits and bonuses can make unadjusted historical price series distort moving averages and CAR. Verify corporate-action adjustments and missing dates before trusting older historical signals. The app does not fill missing bars or fabricate prices.
