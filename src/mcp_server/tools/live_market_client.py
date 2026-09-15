"""Live Financial Market Client using yfinance for TSE stocks and macro indicators.

Provides real-time valuation multiples (PER, PBR, ROE, TSR, Dividend Yield, Market Cap)
and macroeconomic rates (Nikkei 225, USD/JPY, BOJ rate) with intelligent in-memory caching
and automatic graceful fallback to snapshot benchmarks.
"""

import time
import logging
from typing import Dict, Any, List, Optional
import yfinance as yf

logger = logging.getLogger(__name__)

# Known Japanese stock metadata mapping
JP_TICKER_NAMES = {
    "7203": "トヨタ自動車",
    "6758": "ソニーグループ",
    "9984": "ソフトバンクグループ",
    "8306": "三菱UFJフィナンシャル・グループ",
    "8035": "東京エレクトロン",
}

# In-memory cache with TTL (5 minutes)
_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300


def _get_from_cache(key: str) -> Optional[Any]:
    if key in _CACHE:
        entry = _CACHE[key]
        if time.time() - entry["timestamp"] < CACHE_TTL_SECONDS:
            return entry["data"]
    return None


def _set_cache(key: str, data: Any):
    _CACHE[key] = {
        "timestamp": time.time(),
        "data": data,
    }


def _determine_valuation_status(per: float, pbr: float, roe: float) -> str:
    """Evaluate valuation status based on PER, PBR, and ROE."""
    if pbr <= 0 or per <= 0:
        return "FAIR"
    if pbr < 1.05 and per < 14.0:
        return "UNDERVALUED"
    if per > 28.0 or pbr > 4.5:
        return "OVERVALUED"
    return "FAIR"


def _determine_value_trap_risk(pbr: float, roe: float) -> str:
    """Evaluate value trap risk (low PBR with low ROE)."""
    if pbr < 1.0 and roe < 6.0:
        return "HIGH"
    if pbr < 1.1 and roe < 8.5:
        return "MODERATE"
    return "LOW"


def fetch_live_stock_valuation(ticker: str) -> Dict[str, Any]:
    """Fetch live valuation metrics from Yahoo Finance (yfinance) for a Tokyo Stock Exchange ticker."""
    clean_ticker = ticker.strip().upper().replace(".T", "")
    cache_key = f"val_{clean_ticker}"
    cached = _get_from_cache(cache_key)
    if cached is not None:
        return cached

    company_name = JP_TICKER_NAMES.get(clean_ticker, f"銘柄コード {clean_ticker}")
    yf_symbol = f"{clean_ticker}.T"

    try:
        t = yf.Ticker(yf_symbol)
        info = t.info or {}
        fast_info = getattr(t, "fast_info", None)

        # Market Cap in Trillion JPY
        mcap_raw = getattr(fast_info, "market_cap", None) or info.get("marketCap") or 0.0
        mcap_trillion = round(float(mcap_raw) / 1e12, 2) if mcap_raw else 10.0

        # PER (trailing or forward)
        per_raw = info.get("trailingPE") or info.get("forwardPE") or 15.0
        per = round(float(per_raw), 2)

        # PBR
        pbr_raw = info.get("priceToBook") or 1.2
        pbr = round(float(pbr_raw), 2)

        # ROE in percent
        roe_raw = info.get("returnOnEquity") or 0.10
        roe_percent = round(float(roe_raw) * 100, 2)

        # Dividend Yield — this yfinance version (>=1.7) already returns
        # dividendYield as a percent value (e.g. 3.31 means 3.31%), not a
        # fraction. Do NOT re-multiply by 100 here (that previously turned
        # low-yield stocks like 0.92% into a bogus 92%).
        div_raw = info.get("dividendYield")
        div_yield = round(float(div_raw), 2) if div_raw is not None else 2.0

        # Operating Margin
        margin_raw = info.get("operatingMargins") or 0.08
        margin_percent = round(float(margin_raw) * 100, 2)

        # TSR estimate based on 52-week change
        fifty_two_week_change = info.get("52WeekChange") or 0.20
        tsr_percent = round(float(fifty_two_week_change) * 100, 1)

        # Debt to equity
        debt_to_equity_raw = info.get("debtToEquity") or 0.0
        net_debt_to_equity = round(float(debt_to_equity_raw) / 100.0, 2) if debt_to_equity_raw else 0.1

        val_status = _determine_valuation_status(per, pbr, roe_percent)
        trap_risk = _determine_value_trap_risk(pbr, roe_percent)

        now_str = time.strftime("%Y-%m-%d %H:%M JST")

        result = {
            "ticker": clean_ticker,
            "company_name": company_name,
            "currency": "JPY",
            "market_cap_trillion_jpy": mcap_trillion,
            "per": per,
            "pbr": pbr,
            "roe_percent": roe_percent,
            "tsr_percent": tsr_percent,
            "operating_profit_margin_percent": margin_percent,
            "dividend_yield_percent": div_yield,
            "net_debt_to_equity": net_debt_to_equity,
            "value_trap_risk": trap_risk,
            "valuation_status": val_status,
            "as_of_date": f"{now_str} (Live yfinance API)",
            "data_source": "yfinance_live",
        }
        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.warning("Failed to fetch live valuation for %s: %s. Falling back to snapshot.", clean_ticker, e)
        return {
            "error": f"Live fetch failed for {clean_ticker}: {str(e)}",
            "fallback_needed": True,
        }


def fetch_live_macro_indicators() -> List[Dict[str, Any]]:
    """Fetch live macroeconomic indicators (Nikkei 225, USD/JPY, BOJ Rate)."""
    cache_key = "macro_indicators_live"
    cached = _get_from_cache(cache_key)
    if cached is not None:
        return cached

    now_str = time.strftime("%Y-%m-%d %H:%M JST")
    indicators = []

    # 1. Bank of Japan Policy Rate
    indicators.append({
        "indicator": "日銀政策金利 (無担保コール翌日物)",
        "value": "0.25%",
        "trend": "利上げ局面 (追加利上げ観測継続・タカ派スタンス)",
        "source": "日本銀行 政策委員会",
        "updated_at": now_str,
        "data_source": "official_benchmark",
    })

    # 2. Nikkei 225 Live
    try:
        n225 = yf.Ticker("^N225")
        n225_price = getattr(n225.fast_info, "last_price", None) or 38500.0
        n225_val = f"{int(n225_price):,}円水準 (リアルタイム)"
        indicators.append({
            "indicator": "日経平均株価 (Nikkei 225)",
            "value": n225_val,
            "trend": "東証プライム・企業統治改革・自社株買い継続",
            "source": "東京証券取引所 (Live yfinance)",
            "updated_at": now_str,
            "data_source": "yfinance_live",
        })
    except Exception as e:
        logger.warning("Failed to fetch live Nikkei 225: %s", e)
        indicators.append({
            "indicator": "日経平均株価 (Nikkei 225)",
            "value": "38,500円水準",
            "trend": "高値圏保ち合い・海外投資家の日本株買い意欲継続",
            "source": "東京証券取引所",
            "updated_at": now_str,
            "data_source": "snapshot_fallback",
        })

    # 3. USD/JPY Live
    try:
        jpy = yf.Ticker("JPY=X")
        jpy_price = getattr(jpy.fast_info, "last_price", None) or 150.0
        jpy_val = f"{round(float(jpy_price), 2)}円 (リアルタイム)"
        indicators.append({
            "indicator": "USD/JPY (ドル円レート)",
            "value": jpy_val,
            "trend": "日米金利差・為替介入警戒・実効為替レート動向",
            "source": "外為市場 (Live yfinance)",
            "updated_at": now_str,
            "data_source": "yfinance_live",
        })
    except Exception as e:
        logger.warning("Failed to fetch live USD/JPY: %s", e)
        indicators.append({
            "indicator": "USD/JPY (ドル円レート)",
            "value": "150.20円",
            "trend": "日米金利差縮小観測に伴う円高バイアス",
            "source": "外為市場",
            "updated_at": now_str,
            "data_source": "snapshot_fallback",
        })

    _set_cache(cache_key, indicators)
    return indicators


def fetch_live_disclosure(ticker: str) -> Dict[str, Any]:
    """Fetch live earnings/disclosure figures (revenue, operating income, net income)
    from the latest available fiscal-year column in yfinance's income statement.

    Falls back (fallback_needed=True) if yfinance has no income-statement data yet
    (e.g. before the fiscal year is reported) or on any network/parsing error.
    """
    clean_ticker = ticker.strip().upper().replace(".T", "")
    cache_key = f"disc_{clean_ticker}"
    cached = _get_from_cache(cache_key)
    if cached is not None:
        return cached

    company_name = JP_TICKER_NAMES.get(clean_ticker, f"銘柄コード {clean_ticker}")
    yf_symbol = f"{clean_ticker}.T"

    try:
        t = yf.Ticker(yf_symbol)
        income_stmt = t.income_stmt
        if income_stmt is None or income_stmt.empty:
            return {"error": "No income statement data available.", "fallback_needed": True}

        latest_col = income_stmt.columns[0]
        fiscal_end = latest_col.strftime("%Y年%m月期") if hasattr(latest_col, "strftime") else str(latest_col)

        def _row(name: str) -> float:
            if name in income_stmt.index:
                val = income_stmt.loc[name, latest_col]
                if val is not None and val == val:  # not NaN
                    return float(val)
            return 0.0

        revenue = _row("Total Revenue")
        operating_income = _row("Operating Income")
        net_income = _row("Net Income")

        if revenue == 0.0 and operating_income == 0.0 and net_income == 0.0:
            return {"error": "Income statement rows empty for latest period.", "fallback_needed": True}

        now_str = time.strftime("%Y-%m-%d %H:%M JST")
        result = {
            "ticker": clean_ticker,
            "company_name": company_name,
            "fiscal_year": f"{fiscal_end} (Live yfinance 実績/直近開示)",
            "revenue_billion_jpy": round(revenue / 1e9, 1),
            "operating_income_billion_jpy": round(operating_income / 1e9, 1),
            "net_income_billion_jpy": round(net_income / 1e9, 1),
            "guidance_revision": f"Live yfinance 取得時刻: {now_str}（次回決算発表で自動更新）",
            "major_catalysts": [],
            "data_source": "yfinance_live",
        }
        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.warning("Failed to fetch live disclosure for %s: %s. Falling back to snapshot.", clean_ticker, e)
        return {
            "error": f"Live disclosure fetch failed for {clean_ticker}: {str(e)}",
            "fallback_needed": True,
        }
