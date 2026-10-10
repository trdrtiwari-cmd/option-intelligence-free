import asyncio
from datetime import datetime, timezone
import httpx

NSE_BASE = "https://www.nseindia.com"
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

YAHOO = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}


async def yahoo_candles(symbol: str):
    ticker = YAHOO[symbol]
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"interval": "5m", "range": "5d", "includePrePost": "false"}
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=12, headers=headers, follow_redirects=True) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        j = r.json()
    result = j["chart"]["result"][0]
    q = result["indicators"]["quote"][0]
    candles = []
    for i, ts in enumerate(result.get("timestamp", [])):
        o, h, l, cl, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if None in (o, h, l, cl):
            continue
        candles.append({
            "time": ts,
            "open": float(o), "high": float(h), "low": float(l),
            "close": float(cl), "volume": float(v or 0)
        })
    return candles


async def get_nse_option_chain(symbol: str):
    url = f"{NSE_BASE}/api/option-chain-indices"
    params = {"symbol": symbol}
    async with httpx.AsyncClient(timeout=15, headers=NSE_HEADERS, follow_redirects=True) as c:
        # Prime cookies first; NSE commonly rejects direct API calls without a session.
        await c.get(NSE_BASE + "/", timeout=10)
        r = await c.get(url, params=params)
        r.raise_for_status()
        j = r.json()

    records = j.get("records", {})
    rows = records.get("data", [])
    underlying = records.get("underlyingValue")
    expiry = records.get("expiryDates", [None])[0]

    total_ce_oi = total_pe_oi = 0
    total_ce_chg = total_pe_chg = 0
    parsed = []

    for row in rows:
        strike = row.get("strikePrice")
        ce, pe = row.get("CE"), row.get("PE")
        if ce:
            total_ce_oi += ce.get("openInterest", 0) or 0
            total_ce_chg += ce.get("changeinOpenInterest", 0) or 0
        if pe:
            total_pe_oi += pe.get("openInterest", 0) or 0
            total_pe_chg += pe.get("changeinOpenInterest", 0) or 0
        if ce or pe:
            parsed.append({
                "strike": strike,
                "ce": {
                    "ltp": ce.get("lastPrice") if ce else None,
                    "oi": ce.get("openInterest") if ce else None,
                    "chg_oi": ce.get("changeinOpenInterest") if ce else None,
                    "iv": ce.get("impliedVolatility") if ce else None,
                    "volume": ce.get("totalTradedVolume") if ce else None,
                },
                "pe": {
                    "ltp": pe.get("lastPrice") if pe else None,
                    "oi": pe.get("openInterest") if pe else None,
                    "chg_oi": pe.get("changeinOpenInterest") if pe else None,
                    "iv": pe.get("impliedVolatility") if pe else None,
                    "volume": pe.get("totalTradedVolume") if pe else None,
                }
            })

    pcr = (total_pe_oi / total_ce_oi) if total_ce_oi else None
    return {
        "ok": True,
        "source": "NSE",
        "underlying": underlying,
        "expiry": expiry,
        "total_ce_oi": total_ce_oi,
        "total_pe_oi": total_pe_oi,
        "ce_oi_change": total_ce_chg,
        "pe_oi_change": total_pe_chg,
        "pcr": pcr,
        "rows": parsed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def get_market_snapshot(symbol: str):
    candles = await yahoo_candles(symbol)
    has_volume = any(c["volume"] > 0 for c in candles)
    return {
        "ok": bool(candles),
        "source": "Yahoo Finance 5m candles",
        "symbol": symbol,
        "candles": candles,
        "last": candles[-1]["close"] if candles else None,
        "volume_available": has_volume,
        "diagnostics": {
            "candles": "OK" if candles else "No candles returned",
            "volume": "OK" if has_volume else "Yahoo index candles report zero volume; VWAP/volume ratio cannot be calculated from this feed",
            "option_chain": "Fetched separately from NSE; NSE may reject cloud requests"
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
