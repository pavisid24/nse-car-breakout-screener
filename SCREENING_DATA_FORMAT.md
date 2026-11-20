# NSE pre-screen supplementary CSV formats

The official CM UDiFF Bhavcopy does not by itself contain all the fields required for this screen. Upload two supplementary CSV files in the Stock scanner tab.

## 1. Six-month delivery history CSV

One row per symbol per trading date. Required columns (case-insensitive aliases accepted):

- `Symbol`
- `Date`
- `DeliverableQty` (NSE security-wise deliverable quantity)
- `Close` (closing price for the same date)

The app calculates daily delivery value as `DeliverableQty * Close / 10,000,000` and takes the arithmetic average across available trading sessions in the last six months. The filter is ₹35 crore per trading day on average, not total six-month value. Ensure the uploaded file contains the full six-month period; incomplete files can overstate or understate the average.

## 2. Fundamentals / universe CSV

One latest row per symbol, with columns:

- `Symbol`
- `MarketCapCr` (market capitalisation in ₹ crore)
- `FreeFloatPct` (free-float percentage, not simply all non-promoter holdings)
- `IsNifty500` (`true`/`false`, `yes`/`no`, or `1`/`0`)

`IsNifty500` is used as the top-500 universe membership flag. Market cap is shown and can optionally be given a minimum threshold. Free float should exclude promoter and other strategic/locked-in holdings where applicable; do not equate it automatically with 100% minus promoter holding.

## Screening logic

- High trading volume: existing scanner relative-volume condition (latest volume >= 1.2x 20-session average).
- Price movement: 20-session ATR as a percentage of price, configurable in the scanner (default 2%). ATR measures range/volatility; it does not guarantee profitable or directionally useful movement.
- Delivery value: six-month average daily delivery value >= ₹35 crore by default.
- Free float: configurable minimum free-float percentage (default 20%).
- Large-cap universe: Nifty 500 membership required by default.

Missing delivery/free-float/universe data is marked unverified and does not pass the pre-screen. The app does not invent missing data. Verify data definitions, dates and licensing before using the metrics for decisions.
