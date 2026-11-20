from __future__ import annotations
import io
import pandas as pd
import streamlit as st

from nse_data import parse_upload, fetch_history_calendar_days
from car_strategy import analyze_car_strategy, apply_universe_filters, parse_symbol_list_upload

st.set_page_config(page_title="NSE CAR Breakout Screener", page_icon="📈", layout="wide")
st.title("📈 NSE Positive Breakout – CAR Strategy")
st.caption("Standalone app based on the referenced video/article strategy. NSE daily EOD data only; no orders are placed.")

with st.sidebar:
    st.header("Strategy settings")
    max_extension = st.number_input("Maximum distance above 200 DMA (%)", 0.0, 30.0, 10.0, 0.5)
    car_days = st.number_input("Consecutive rising CAR observations", 3, 30, 10, 1)
    min_volume = st.number_input("Latest volume / 20-day average", 0.0, 10.0, 1.0, 0.1)
    min_atr = st.number_input("Minimum ATR14 / price (%)", 0.0, 20.0, 2.0, 0.25)
    st.divider()
    st.subheader("Additional universe filters")
    require_metrics = st.toggle("Require delivery and fundamentals CSV", value=True)
    min_delivery = st.number_input("6-month average delivery value (₹ Cr/day)", 0.0, 1000.0, 35.0, 5.0)
    min_float = st.number_input("Minimum free-float (%)", 0.0, 100.0, 20.0, 1.0)
    min_float_value = st.number_input("Minimum free-float value (₹ Cr)", 0.0, 100000.0, 1500.0, 100.0)
    require_top500 = st.toggle("Require Nifty 500 membership", value=True)

st.markdown("### 1. Load official NSE daily Bhavcopy history")
st.info("Easiest option: try the automatic NSE archive downloader first. It requests roughly 430 calendar days to collect about 252 trading sessions. NSE may block or rate-limit cloud-hosted downloads; if that happens, use the manual ZIP/CSV uploader below. Data is end-of-day only.")
if st.button("⬇️ Fetch approximately 1 year of NSE history", type="primary", use_container_width=True):
    progress_bar = st.progress(0)
    status_line = st.empty()
    def update_progress(done, total, day):
        progress_bar.progress(done / total)
        if done % 10 == 0 or done == total:
            status_line.info(f"Checking {done}/{total} calendar dates; latest checked: {day.isoformat()}")
    with st.spinner("Requesting NSE daily archives. This can take several minutes..."):
        fetched, fetch_errors = fetch_history_calendar_days(430, update_progress)
    if not fetched.empty:
        st.session_state["car_data"] = fetched
        st.session_state["car_errors"] = fetch_errors
        st.success(f"Loaded {len(fetched):,} daily rows across {fetched['Symbol'].nunique():,} symbols, from {fetched['Date'].min().date()} to {fetched['Date'].max().date()}.")
        st.info("Next, press Run CAR strategy scan below. Upload delivery/fundamental data separately if those filters are enabled.")
    else:
        st.error("NSE did not return usable archives. This may be due to NSE access restrictions or cloud IP blocking. Use the manual uploader below, or retry later.")
    if fetch_errors:
        with st.expander(f"Download warnings ({len(fetch_errors)} shown)"):
            st.write(fetch_errors)

st.markdown("#### Or upload NSE Bhavcopy ZIP/CSV files manually")
bhav_files = st.file_uploader("NSE Bhavcopy ZIP or CSV files", type=["zip", "csv"], accept_multiple_files=True, key="bhav")

st.markdown("### 2. Optional universe and fundamental data")
c1, c2 = st.columns(2)
with c1:
    fno_file = st.file_uploader("Current NSE F&O underlying list CSV (optional)", type=["csv"], key="fno")
with c2:
    metrics_file = st.file_uploader("Delivery + market cap + free-float CSV (required if enabled)", type=["csv"], key="metrics")

with st.expander("Required supplementary CSV format"):
    st.code("Symbol,AvgDeliveryValue6M_Cr,MarketCapCr,FreeFloatPct,IsNifty500\nRELIANCE,42.5,1900000,49.5,true", language="csv")
    st.caption("Illustrative row only. AvgDeliveryValue6M_Cr should be the six-month average daily deliverable turnover in ₹ crore. FreeFloatPct should be a defensible free-float percentage, not automatically 100% minus promoter holding.")

if st.button("🔎 Run CAR strategy scan", type="primary", use_container_width=True):
    frames, errors = [], []
    if "car_data" in st.session_state and not st.session_state["car_data"].empty:
        frames.append(st.session_state["car_data"])
    if bhav_files:
        progress = st.progress(0)
        for i, uploaded in enumerate(bhav_files):
            try:
                frame = parse_upload(uploaded.getvalue(), uploaded.name)
                if not frame.empty:
                    frames.append(frame)
                else:
                    errors.append(f"{uploaded.name}: no recognized NSE OHLCV rows")
            except Exception as exc:
                errors.append(f"{uploaded.name}: {exc}")
            progress.progress((i + 1) / len(bhav_files))
    if not frames:
        st.error("First use Fetch approximately 1 year of NSE history or upload at least one NSE Bhavcopy ZIP/CSV.")
        st.stop()
    data = pd.concat(frames, ignore_index=True).drop_duplicates(["Symbol", "Date"], keep="last")
    data = data.sort_values(["Symbol", "Date"])
    st.session_state["car_data"] = data
    st.session_state["car_errors"] = st.session_state.get("car_errors", []) + errors
    st.session_state["car_fno"] = fno_file.getvalue() if fno_file else None
    st.session_state["car_metrics"] = metrics_file.getvalue() if metrics_file else None
    st.session_state["car_params"] = (max_extension, int(car_days), min_volume, min_atr, require_metrics, min_delivery, min_float, min_float_value, require_top500)

if "car_data" in st.session_state:
    data = st.session_state["car_data"]
    errors = st.session_state.get("car_errors", [])
    params = st.session_state.get("car_params", (10.0, 10, 1.0, 2.0, True, 35.0, 20.0, 1500.0, True))
    max_extension, car_days, min_volume, min_atr, require_metrics, min_delivery, min_float, min_float_value, require_top500 = params
    symbols = sorted(data["Symbol"].dropna().astype(str).str.upper().unique().tolist())
    if st.session_state.get("car_fno"):
        try:
            fno = pd.read_csv(io.BytesIO(st.session_state["car_fno"]))
            fno_symbols = parse_symbol_list_upload(fno)
            if fno_symbols:
                symbols = sorted(set(symbols).intersection(fno_symbols))
                st.caption(f"Restricted to intersection with uploaded F&O list: {len(symbols)} symbols")
        except Exception as exc:
            st.warning(f"Could not read F&O list: {exc}")
    st.markdown("### 3. Scan results")
    st.write(f"Imported **{len(data):,}** daily rows, **{len(symbols):,}** symbols, from **{data['Date'].min().date()}** to **{data['Date'].max().date()}**.")
    if errors:
        with st.expander(f"Import warnings ({len(errors)})"):
            st.write(errors)
    rows = []
    for symbol in symbols:
        hist = data[data["Symbol"] == symbol].set_index("Date").sort_index()
        result = analyze_car_strategy(hist, max_extension_pct=max_extension, car_days=car_days, min_volume_ratio=min_volume, min_atr_pct=min_atr)
        rows.append({"Symbol": symbol, **{k:v for k,v in result.items() if k != "RuleChecks"}})
    results = pd.DataFrame(rows)
    if st.session_state.get("car_metrics"):
        try:
            metrics = pd.read_csv(io.BytesIO(st.session_state["car_metrics"]))
        except Exception as exc:
            metrics = pd.DataFrame()
            st.error(f"Could not read metrics CSV: {exc}")
    else:
        metrics = pd.DataFrame()
    results = apply_universe_filters(results, metrics, min_delivery_value_cr=min_delivery, min_free_float_pct=min_float, min_free_float_value_cr=min_float_value, require_top500=require_top500, require_uploaded_metrics=require_metrics)
    if not require_metrics:
        results["UniversePassed"] = True
        results["UniverseStatus"] = "Supplementary filters disabled"
    results["FinalStatus"] = results.apply(lambda r: "QUALIFIED" if r.get("Status") == "Positive Breakout" and bool(r.get("UniversePassed", False)) else "NOT QUALIFIED", axis=1)
    results = results.sort_values(["FinalStatus", "Distance200Pct"], ascending=[True, True], na_position="last")
    qualified = results[results["FinalStatus"] == "QUALIFIED"]
    a,b,c,d = st.columns(4)
    a.metric("Symbols scanned", f"{len(results):,}")
    b.metric("Technical positives", int((results["Status"] == "Positive Breakout").sum()))
    c.metric("Final qualified", len(qualified))
    d.metric("Symbols with <252 bars", int(results["Status"].astype(str).str.contains("Insufficient data").sum()))
    st.dataframe(qualified.drop(columns=["RuleChecks"], errors="ignore"), use_container_width=True, hide_index=True)
    with st.expander("All stocks and failure reasons", expanded=True):
        st.dataframe(results.drop(columns=["RuleChecks"], errors="ignore"), use_container_width=True, hide_index=True)
    st.download_button("Download full scan CSV", results.to_csv(index=False).encode("utf-8"), "nse_car_strategy_scan.csv", "text/csv")
    st.download_button("Download qualified stocks CSV", qualified.to_csv(index=False).encode("utf-8"), "nse_car_qualified.csv", "text/csv")

st.divider()
st.caption("Research tool only. Uses uploaded end-of-day NSE data; no live feed or broker execution. Strategy rules are based on the referenced video/article, with additional user-configurable liquidity/volatility/fundamental filters. Historical results do not guarantee future performance.")
