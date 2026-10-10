import asyncio
import math
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from indicators import calculate_indicators
from market_data import get_market_snapshot

app = FastAPI(title="Option Intelligence Free", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def home():
    return FileResponse("static/index.html")


@app.get("/api/health")
async def health():
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/market")
async def market(symbol: str = Query("NIFTY", pattern="^(NIFTY|BANKNIFTY)$")):
    try:
        data = await get_market_snapshot(symbol)
        return data
    except Exception as e:
        return {
            "ok": False,
            "symbol": symbol,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/api/option-chain")
async def option_chain(symbol: str = Query("NIFTY", pattern="^(NIFTY|BANKNIFTY)$")):
    try:
        from market_data import get_nse_option_chain
        return await get_nse_option_chain(symbol)
    except Exception as e:
        return {
            "ok": False,
            "symbol": symbol,
            "source": "NSE",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/api/analysis")
async def analysis(symbol: str = Query("NIFTY", pattern="^(NIFTY|BANKNIFTY)$")):
    try:
        market_data = await get_market_snapshot(symbol)
    except Exception as e:
        return {
            "ok": False,
            "symbol": symbol,
            "market": {"ok": False, "error": str(e), "candles": []},
            "indicators": {"close": None},
            "option_chain": {"ok": False, "error": "Not requested because market data failed"},
            "decision": {
                "signal": "WAIT",
                "condition": "MARKET DATA UNAVAILABLE",
                "score": 0,
                "confidence": 0,
                "reason": "Market data request failed. Check the data provider and server logs."
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    try:
        from market_data import get_nse_option_chain
        chain = await get_nse_option_chain(symbol)
    except Exception as e:
        chain = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:180]}"}

    ind = calculate_indicators(market_data.get("candles", []))
    decision = build_decision(market_data, ind, chain)

    return {
        "ok": True,
        "symbol": symbol,
        "market": market_data,
        "indicators": ind,
        "option_chain": chain,
        "decision": decision,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def build_decision(market, ind, chain):
    close = ind.get("close")
    ema9 = ind.get("ema9")
    ema21 = ind.get("ema21")
    rsi = ind.get("rsi")
    vwap = ind.get("vwap")
    atr = ind.get("atr")
    adx = ind.get("adx")
    volume_ratio = ind.get("volume_ratio")

    # VWAP and volume are optional for index spot feeds: Yahoo often reports
    # zero volume for indices, so a VWAP cannot be computed honestly from it.
    if None in (close, ema9, ema21, rsi, atr, adx):
        missing = [name for name, value in {
            "close": close, "EMA9": ema9, "EMA21": ema21,
            "RSI": rsi, "ATR": atr, "ADX": adx
        }.items() if value is None]
        return {
            "signal": "WAIT",
            "condition": "DATA INCOMPLETE",
            "score": 0,
            "confidence": 0,
            "reason": "Waiting for sufficient candle history. Missing: " + ", ".join(missing),
        }

    bull = 0
    bear = 0
    reasons = []

    if close > ema9: bull += 1
    else: bear += 1
    if ema9 > ema21: bull += 2
    else: bear += 2
    if vwap is not None:
        if close > vwap: bull += 2
        else: bear += 2
    if 55 <= rsi <= 75: bull += 2
    elif 25 <= rsi <= 45: bear += 2
    if adx >= 20:
        if ema9 > ema21: bull += 1
        else: bear += 1
    if volume_ratio is not None and volume_ratio >= 1.15:
        if close > ema9: bull += 1
        else: bear += 1

    pcr = chain.get("pcr") if isinstance(chain, dict) else None
    if isinstance(pcr, (int, float)):
        if pcr > 1.05: bull += 1
        elif pcr < 0.80: bear += 1

    total = bull + bear
    if total == 0:
        return {"signal": "WAIT", "condition": "SIDEWAYS", "score": 0, "confidence": 0, "reason": "No valid score."}

    if bull >= 7 and bull > bear + 2:
        signal = "BUY CALL"
        condition = "BULLISH"
        score = bull
    elif bear >= 7 and bear > bull + 2:
        signal = "BUY PUT"
        condition = "BEARISH"
        score = bear
    else:
        signal = "WAIT"
        condition = "SIDEWAYS / MIXED"
        score = max(bull, bear)

    confidence = round(min(100, score / 10 * 100))
    if adx < 18:
        signal = "WAIT"
        condition = "LOW TREND STRENGTH"
        confidence = min(confidence, 55)

    return {
        "signal": signal,
        "condition": condition,
        "bull_score": bull,
        "bear_score": bear,
        "score": score,
        "confidence": confidence,
        "reason": (
            f"EMA/RSI/ADX plus optional VWAP, volume and PCR confirmation. "
            f"Bull={bull}, Bear={bear}. "
            + ("VWAP/volume unavailable from index feed; those factors were excluded. " if vwap is None or volume_ratio is None else "")
            + ("PCR/OI unavailable; no OI-based confirmation used." if not isinstance(pcr, (int, float)) else "PCR was included.")
        ),
        "entry": close,
        "atr": atr,
        "suggested_sl": round(close - atr * 1.2, 2) if signal == "BUY CALL" else round(close + atr * 1.2, 2) if signal == "BUY PUT" else None,
        "suggested_target": round(close + atr * 2.0, 2) if signal == "BUY CALL" else round(close - atr * 2.0, 2) if signal == "BUY PUT" else None,
    }


# Paper trading is intentionally client-side so no broker account is required.
