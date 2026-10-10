import math


def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for x in values[period:]:
        e = x * k + e * (1 - k)
    return e


def sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def rsi(values, period=14):
    if len(values) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        d = values[i] - values[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def atr(high, low, close, period=14):
    if len(close) < period + 1:
        return None
    trs = []
    for i in range(1, len(close)):
        trs.append(max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1])))
    return sum(trs[-period:]) / period


def adx(high, low, close, period=14):
    if len(close) < period * 2 + 1:
        return None
    tr, plus, minus = [], [], []
    for i in range(1, len(close)):
        tr.append(max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1])))
        up = high[i] - high[i-1]
        dn = low[i-1] - low[i]
        plus.append(up if up > dn and up > 0 else 0)
        minus.append(dn if dn > up and dn > 0 else 0)
    atrs = sum(tr[:period]) / period
    p = sum(plus[:period]) / period
    m = sum(minus[:period]) / period
    dx = []
    for i in range(period, len(tr)):
        atrs = (atrs * (period-1) + tr[i]) / period
        p = (p * (period-1) + plus[i]) / period
        m = (m * (period-1) + minus[i]) / period
        if atrs == 0:
            dx.append(0)
        else:
            dip = 100 * p / atrs
            dim = 100 * m / atrs
            dx.append(100 * abs(dip-dim) / max(dip+dim, 1e-9))
    if len(dx) < period:
        return None
    return sum(dx[-period:]) / period


def calculate_indicators(candles):
    if not candles:
        return {"close": None}
    o = [x["open"] for x in candles]
    h = [x["high"] for x in candles]
    l = [x["low"] for x in candles]
    c = [x["close"] for x in candles]
    v = [x["volume"] for x in candles]

    # Session VWAP based on available 5m data.
    pv = 0.0
    vv = 0.0
    for hh, ll, cc, vol in zip(h, l, c, v):
        typical = (hh + ll + cc) / 3
        pv += typical * vol
        vv += vol
    vw = pv / vv if vv else None

    avg_vol = sma(v, 20)
    # Spot index candles often carry zero volume. Do not report a fake VWAP.
    usable_volume = sum(v) > 0
    return {
        "close": c[-1],
        "ema9": ema(c, 9),
        "ema21": ema(c, 21),
        "rsi": rsi(c, 14),
        "atr": atr(h, l, c, 14),
        "adx": adx(h, l, c, 14),
        "vwap": vw if usable_volume else None,
        "vwap_available": usable_volume,
        "volume": v[-1] if usable_volume else None,
        "volume_avg20": avg_vol if usable_volume else None,
        "volume_ratio": (v[-1] / avg_vol) if usable_volume and avg_vol and avg_vol > 0 else None,
        "high": h[-1],
        "low": l[-1],
    }
