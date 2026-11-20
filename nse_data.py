"""NSE UDiFF Common Bhavcopy adapter. Daily EOD only; no unofficial quote API."""
from __future__ import annotations
import io, zipfile, time
from datetime import date, timedelta
from typing import Iterable
import pandas as pd
import requests

NSE_ARCHIVE = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.nseindia.com/"
}

COLUMN_ALIASES = {
    "TckrSymb": "Symbol", "TradDt": "Date", "OpnPric": "Open", "HghPric": "High",
    "LwPric": "Low", "ClsPric": "Close", "TtlTradgVol": "Volume",
    "FinInstrmNm": "Instrument", "SctySrs": "Series", "ISIN": "ISIN",
    # legacy / alternate report labels
    "SYMBOL": "Symbol", "DATE1": "Date", "OPEN_PRICE": "Open", "HIGH_PRICE": "High",
    "LOW_PRICE": "Low", "CLOSE_PRICE": "Close", "TOTTRDQTY": "Volume",
}


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["Date", "Symbol", "Open", "High", "Low", "Close", "Volume"])
    d = frame.copy()
    d.columns = [str(c).strip() for c in d.columns]
    rename = {c: COLUMN_ALIASES[c] for c in d.columns if c in COLUMN_ALIASES}
    d = d.rename(columns=rename)
    if "Series" in d.columns:
        d["Series"] = d["Series"].astype(str).str.upper().str.strip()
        d = d[d["Series"].isin(["EQ", "BE", "BZ", "SM", "ST", "SZ", "E1", "E2"])]
    # Some UDiFF exports use lower-case headers.
    lower_map = {str(c).lower(): c for c in d.columns}
    for src, dst in [("trad dt", "Date"), ("tckr symb", "Symbol"), ("opn pric", "Open"),
                     ("hgh pric", "High"), ("lw pric", "Low"), ("cls pric", "Close"),
                     ("ttl tradg vol", "Volume")]:
        if dst not in d.columns and src in lower_map:
            d = d.rename(columns={lower_map[src]: dst})
    required = ["Date", "Symbol", "Open", "High", "Low", "Close", "Volume"]
    if not all(c in d.columns for c in required):
        return pd.DataFrame(columns=required)
    d = d[required].copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce", dayfirst=True)
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        d[c] = pd.to_numeric(d[c].astype(str).str.replace(",", "", regex=False), errors="coerce")
    d["Symbol"] = d["Symbol"].astype(str).str.strip().str.upper()
    d = d.dropna(subset=["Date", "Close"])
    d = d[(d["Symbol"] != "") & (d["Close"] > 0)]
    if "Series" in frame.columns:
        pass
    return d.sort_values(["Symbol", "Date"]).drop_duplicates(["Symbol", "Date"], keep="last")


def parse_upload(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Parse NSE UDiFF CSV or ZIP upload; supports ZIPs containing one or more CSVs."""
    frames = []
    if filename.lower().endswith(".zip") or file_bytes[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".csv"):
                    with zf.open(name) as f:
                        frames.append(pd.read_csv(f, low_memory=False))
    else:
        frames.append(pd.read_csv(io.BytesIO(file_bytes), low_memory=False))
    parsed = [_normalize(f) for f in frames]
    parsed = [f for f in parsed if not f.empty]
    return pd.concat(parsed, ignore_index=True) if parsed else pd.DataFrame()


def fetch_one_day(day: date, session: requests.Session | None = None) -> pd.DataFrame:
    sess = session or requests.Session()
    url = NSE_ARCHIVE.format(ymd=day.strftime("%Y%m%d"))
    response = sess.get(url, headers=HEADERS, timeout=20)
    if response.status_code == 404:
        return pd.DataFrame()
    response.raise_for_status()
    if not response.content.startswith(b"PK"):
        raise ValueError("NSE archive response was not a ZIP file")
    return parse_upload(response.content, f"bhavcopy_{day:%Y%m%d}.zip")


def fetch_history_calendar_days(calendar_days: int = 430, progress_callback=None) -> tuple[pd.DataFrame, list[str]]:
    """Best-effort download of recent NSE CM UDiFF daily archives.

    NSE may rate-limit or block cloud-hosted requests. Missing dates (weekends,
    holidays, unpublished files) are skipped; errors are returned for display.
    """
    sess = requests.Session()
    # Establish a browser-like session first; NSE archive access can require cookies.
    try:
        sess.get("https://www.nseindia.com/", headers=HEADERS, timeout=15)
    except Exception:
        pass
    all_frames, errors = [], []
    today = date.today()
    for offset in range(calendar_days):
        day = today - timedelta(days=offset)
        try:
            frame = fetch_one_day(day, sess)
            if not frame.empty:
                all_frames.append(frame)
        except Exception as exc:
            # Record a small sample of failures to avoid a huge UI message.
            if len(errors) < 20:
                errors.append(f"{day.isoformat()}: {exc}")
        if progress_callback:
            progress_callback(offset + 1, calendar_days, day)
        time.sleep(0.25)
    if not all_frames:
        return pd.DataFrame(), errors
    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.drop_duplicates(["Symbol", "Date"], keep="last")
    return combined.sort_values(["Symbol", "Date"]), errors


def fetch_recent(days_back: int = 12) -> tuple[pd.DataFrame, list[str]]:
    """Fetch recent calendar dates (weekends/holidays naturally return no file)."""
    sess = requests.Session()
    all_frames, errors = [], []
    today = date.today()
    for offset in range(days_back):
        day = today - timedelta(days=offset)
        try:
            frame = fetch_one_day(day, sess)
            if not frame.empty:
                all_frames.append(frame)
        except Exception as exc:
            errors.append(f"{day.isoformat()}: {exc}")
        time.sleep(0.15)
    if not all_frames:
        return pd.DataFrame(), errors
    return pd.concat(all_frames, ignore_index=True).drop_duplicates(["Symbol", "Date"], keep="last"), errors


def symbol_history(all_data: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if all_data is None or all_data.empty:
        return pd.DataFrame()
    s = symbol.strip().upper().replace(".NS", "")
    d = all_data[all_data["Symbol"].astype(str).str.upper() == s].copy()
    if d.empty:
        return pd.DataFrame()
    d = d.set_index("Date").sort_index()
    return d[["Open", "High", "Low", "Close", "Volume"]].astype(float)
