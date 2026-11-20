# NSE CAR Positive Breakout Screener — Standalone App

This is a separate Streamlit application for the positive-breakout/CAR strategy from the referenced YouTube video and companion article. It does not modify or depend on the user's main AI Stock Analyst app.

## Included
- `app.py`: standalone Streamlit interface
- `car_strategy.py`: CAR, moving-average, volume and ATR calculations
- `nse_data.py`: parser for NSE CM-UDiFF Common Bhavcopy Final ZIP/CSV files
- `requirements.txt`: dependencies
- `VIDEO_CAR_STRATEGY.md`: strategy notes and source distinctions
- `SCREENING_DATA_FORMAT.md`: supplementary data format notes

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy as a separate Streamlit app
1. Create a **new GitHub repository**, e.g. `nse-car-breakout-screener`.
2. Upload all files in this folder to the repository root (not the parent folder).
3. Open https://share.streamlit.io/ and choose **New app**.
4. Select the new repository, branch `main`, and main file `app.py`.
5. Deploy. This creates a separate app URL and leaves your existing stock analyst untouched.

## Data required
- Upload multiple NSE `CM-UDiFF Common Bhavcopy Final` ZIP/CSV files. Each symbol needs at least 252 daily sessions to calculate the 52-week high and 200-DMA reliably.
- Optional F&O list CSV: a column named `Symbol`, `TckrSymb`, `Underlying` or similar.
- For delivery/free-float/Nifty 500 gates, upload a CSV with columns:
  `Symbol,AvgDeliveryValue6M_Cr,MarketCapCr,FreeFloatPct,IsNifty500`
- The app does not fabricate missing delivery/fundamental data. If the supplementary metrics gate is enabled, missing values fail qualification.

## Strategy interpretation
- CAR is the expanding average of closing prices from the date of the highest High in the trailing 252 sessions.
- The last 10 CAR values must be monotonically increasing.
- Close must be above 30-, 50- and 200-day simple moving averages.
- The article prose specifies no more than 10% above 200-DMA; this is configurable.
- Volume ratio and ATR% thresholds are additional configurable filters, not exact numerical rules from the video.
- The screener is end-of-day only. It is not an execution system and does not place trades.

## Important
NSE data terms apply. Free public reports are not a blanket permission to redistribute market data. This app has no permanent database; uploaded files are held in Streamlit session state and may need to be uploaded again after a new session/restart.
