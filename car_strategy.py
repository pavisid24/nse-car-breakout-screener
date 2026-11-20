"""Video-derived CAR + 30/50/200 DMA positive-breakout screener.

Source logic reproduced from the companion article for YouTube video 2MjnPmUePl0:
- find the highest High in the last 252 trading sessions;
- take closing prices from that high date to the latest session;
- calculate expanding mean (CAR);
- CAR is positive when the latest 10 CAR observations are monotonically increasing;
- require Close > 30/50/200-day simple moving averages.

The source prose additionally says the stock should be no more than 10% above 200 DMA.
The published sample code does not enforce that cap; this module enforces it as a separately
reported source-prose filter. Other liquidity/volatility/fundamental thresholds are configurable
user-added universe filters, not parameters specified precisely by the video.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def analyze_car_strategy(
    history: pd.DataFrame,
    *,
    max_extension_pct: float = 10.0,
    car_days: int = 10,
    min_volume_ratio: float = 1.0,
    min_atr_pct: float = 2.0,
) -> dict:
    """Analyze one NSE symbol history and return metrics + pass/fail reasons."""
    required = {"High", "Low", "Close", "Volume"}
    if history is None or history.empty or not required.issubset(history.columns):
        return {"Status": "Insufficient data", "Reason": "Missing OHLCV history."}

    d = history.copy().sort_index()
    for col in ["High", "Low", "Close", "Volume"]:
        d[col] = _num(d[col])
    d = d.dropna(subset=["High", "Low", "Close", "Volume"])
    d = d[(d["Close"] > 0) & (d["High"] > 0) & (d["Low"] > 0)]
    if len(d) < 252:
        return {"Status": "Insufficient data", "Reason": f"Need 252 daily bars for a full 52-week high plus 200-DMA; found {len(d)}."}

    close = d["Close"]
    high_252 = d.tail(252)
    high_date = high_252["High"].idxmax()
    car_data = close.loc[high_date:]
    if len(car_data) < car_days:
        return {"Status": "Insufficient data", "Reason": f"Only {len(car_data)} CAR observations since the latest 52-week high."}

    car = car_data.expanding().mean()
    car_tail = car.tail(car_days)
    # Pandas monotonic_increasing allows equal successive observations, matching published code.
    car_rising = bool(car_tail.is_monotonic_increasing)

    dma30 = float(close.rolling(30).mean().iloc[-1])
    dma50 = float(close.rolling(50).mean().iloc[-1])
    dma200 = float(close.rolling(200).mean().iloc[-1])
    cmp = float(close.iloc[-1])
    dist200 = (cmp / dma200 - 1.0) * 100.0 if dma200 else np.nan

    prev = close.shift(1)
    tr = pd.concat([
        d["High"] - d["Low"],
        (d["High"] - prev).abs(),
        (d["Low"] - prev).abs(),
    ], axis=1).max(axis=1)
    atr14 = float(tr.rolling(14).mean().iloc[-1])
    atr_pct = (atr14 / cmp * 100.0) if cmp else np.nan
    vol20 = float(d["Volume"].rolling(20).mean().iloc[-1])
    vol_ratio = float(d["Volume"].iloc[-1] / vol20) if vol20 > 0 else np.nan
    avg_turnover_cr = float((close * d["Volume"]).tail(20).mean() / 1e7)

    checks = {
        "Close > 30 DMA": cmp > dma30,
        "Close > 50 DMA": cmp > dma50,
        "Close > 200 DMA": cmp > dma200,
        f"CAR rising for {car_days} days": car_rising,
        f"Distance from 200 DMA <= {max_extension_pct:.1f}%": dist200 <= max_extension_pct,
        f"Volume ratio >= {min_volume_ratio:.2f}x (user filter)": pd.notna(vol_ratio) and vol_ratio >= min_volume_ratio,
        f"ATR% >= {min_atr_pct:.1f}% (user filter)": pd.notna(atr_pct) and atr_pct >= min_atr_pct,
    }
    passed = all(checks.values())
    failed = [name for name, ok in checks.items() if not ok]
    return {
        "Status": "Positive Breakout" if passed else "Does not meet rules",
        "Reason": "All technical filters passed." if passed else "; ".join(failed),
        "AsOf": pd.Timestamp(d.index[-1]).strftime("%Y-%m-%d"),
        "CMP": cmp,
        "DMA30": dma30,
        "DMA50": dma50,
        "DMA200": dma200,
        "Distance200Pct": dist200,
        "Latest52WHighDate": pd.Timestamp(high_date).strftime("%Y-%m-%d"),
        "DaysSince52WHigh": int((d.index >= high_date).sum() - 1),
        "CARLatest": float(car.iloc[-1]),
        "CAR10Increasing": car_rising,
        "CAR10Start": float(car_tail.iloc[0]),
        "CAR10End": float(car_tail.iloc[-1]),
        "VolumeRatio": vol_ratio,
        "ATR14Pct": atr_pct,
        "AvgDailyTurnover20Cr": avg_turnover_cr,
        "ChecksPassed": int(sum(checks.values())),
        "ChecksTotal": len(checks),
        "RuleChecks": checks,
    }


def apply_universe_filters(
    result: pd.DataFrame,
    metrics: pd.DataFrame | None,
    *,
    min_delivery_value_cr: float = 35.0,
    min_free_float_pct: float = 20.0,
    min_free_float_value_cr: float = 1500.0,
    require_top500: bool = True,
    require_uploaded_metrics: bool = True,
) -> pd.DataFrame:
    """Apply source/user universe filters using separately uploaded data.

    Free-float value is estimated as market cap × non-promoter/free-float percentage.
    It is only as accurate as the uploaded market-cap and free-float dataset.
    """
    out = result.copy()
    if out.empty:
        return out
    if metrics is None or metrics.empty:
        out["UniverseStatus"] = "Not verified — upload delivery/fundamentals CSV"
        out["UniversePassed"] = not require_uploaded_metrics
        return out

    m = metrics.copy()
    if "Symbol" not in m.columns:
        out["UniverseStatus"] = "Invalid uploaded metrics: Symbol column missing"
        out["UniversePassed"] = False
        return out
    m["Symbol"] = m["Symbol"].astype(str).str.upper().str.strip()
    for c in ["AvgDeliveryValue6M_Cr", "MarketCapCr", "FreeFloatPct"]:
        if c in m:
            m[c] = pd.to_numeric(m[c], errors="coerce")
    if "IsNifty500" in m:
        m["IsNifty500"] = m["IsNifty500"].astype(str).str.lower().isin(["true", "1", "yes", "y"])
    else:
        m["IsNifty500"] = np.nan

    out = out.merge(m.drop_duplicates("Symbol", keep="last"), on="Symbol", how="left")
    out["FreeFloatValueCr"] = out.get("MarketCapCr", np.nan) * out.get("FreeFloatPct", np.nan) / 100.0
    have_data = out.get("AvgDeliveryValue6M_Cr", pd.Series(np.nan, index=out.index)).notna()
    have_data &= out.get("FreeFloatPct", pd.Series(np.nan, index=out.index)).notna()
    have_data &= out.get("MarketCapCr", pd.Series(np.nan, index=out.index)).notna()
    passed = have_data
    passed &= out["AvgDeliveryValue6M_Cr"].fillna(-1) >= min_delivery_value_cr
    passed &= out["FreeFloatPct"].fillna(-1) >= min_free_float_pct
    passed &= out["FreeFloatValueCr"].fillna(-1) >= min_free_float_value_cr
    if require_top500:
        passed &= out["IsNifty500"].fillna(False)
    out["UniversePassed"] = passed
    out["UniverseStatus"] = np.where(
        ~have_data,
        "Missing delivery/free-float/market-cap data",
        np.where(passed, "Pass", "Fails delivery/free-float/top-500 filters"),
    )
    return out


def scan_symbols(symbols, get_history, *, max_extension_pct=10.0,
                 car_days=10, min_volume_ratio=1.0, min_atr_pct=2.0) -> pd.DataFrame:
    """Run strategy across symbols. get_history(symbol) must return daily OHLCV."""
    rows = []
    for symbol in symbols:
        sym = str(symbol).strip().upper().replace(".NS", "")
        if not sym:
            continue
        try:
            hist = get_history(sym)
            metrics = analyze_car_strategy(
                hist,
                max_extension_pct=max_extension_pct,
                car_days=car_days,
                min_volume_ratio=min_volume_ratio,
                min_atr_pct=min_atr_pct,
            )
            row = {"Symbol": sym, **{k: v for k, v in metrics.items() if k != "RuleChecks"}}
            row["RuleChecks"] = metrics.get("RuleChecks", {})
            rows.append(row)
        except Exception as exc:
            rows.append({"Symbol": sym, "Status": "Analysis error", "Reason": str(exc)})
    out = pd.DataFrame(rows)
    if not out.empty and "Distance200Pct" in out:
        out = out.sort_values(["Status", "Distance200Pct"], ascending=[True, True], na_position="last")
    return out


def parse_symbol_list_upload(frame: pd.DataFrame) -> list[str]:
    """Extract symbols from common NSE F&O CSV header variants."""
    if frame is None or frame.empty:
        return []
    aliases = {"SYMBOL", "TCKRSYMB", "UNDERLYING", "UNDERLYINGSYMBOL", "SECURITY", "NAME"}
    col = next((c for c in frame.columns if str(c).strip().upper().replace(" ", "") in aliases), None)
    if col is None:
        col = frame.columns[0]
    vals = frame[col].dropna().astype(str).str.strip().str.upper()
    vals = vals[~vals.isin(["", "SYMBOL", "NAN", "NONE"])]
    vals = vals.str.replace(".NS", "", regex=False)
    return sorted(vals.unique().tolist())
