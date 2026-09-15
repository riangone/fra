"""Valuation and Financial Metric MCP Tools (linking with stock_skills domain models)."""

from typing import Dict, Any, List, Optional
from src.models.finance import FinancialMetrics
from src.mcp_server.tools.live_market_client import fetch_live_stock_valuation
from config.settings import settings

# Latest real-world financial snapshot database for key Japanese companies (2025/2026 最新スナップショット)
FINANCIAL_DATABASE: Dict[str, FinancialMetrics] = {
    "7203": FinancialMetrics(
        ticker="7203",
        company_name="トヨタ自動車",
        currency="JPY",
        market_cap_trillion_jpy=44.8,
        per=9.2,
        pbr=1.05,
        roe_percent=13.8,
        tsr_percent=36.5,
        operating_profit_margin_percent=10.9,
        dividend_yield_percent=3.10,
        net_debt_to_equity=-0.12,  # Net cash position
        value_trap_risk="LOW",
        valuation_status="UNDERVALUED",
        as_of_date="2025-03-31 (最新決算スナップショット)",
        data_source="snapshot",
    ),
    "6758": FinancialMetrics(
        ticker="6758",
        company_name="ソニーグループ",
        currency="JPY",
        market_cap_trillion_jpy=18.2,
        per=17.5,
        pbr=2.25,
        roe_percent=13.6,
        tsr_percent=21.4,
        operating_profit_margin_percent=10.5,
        dividend_yield_percent=0.85,
        net_debt_to_equity=0.18,
        value_trap_risk="LOW",
        valuation_status="FAIR",
        as_of_date="2025-03-31 (最新決算スナップショット)",
        data_source="snapshot",
    ),
    "9984": FinancialMetrics(
        ticker="9984",
        company_name="ソフトバンクグループ",
        currency="JPY",
        market_cap_trillion_jpy=14.8,
        per=25.0,
        pbr=1.15,
        roe_percent=8.2,
        tsr_percent=42.0,
        operating_profit_margin_percent=8.5,
        dividend_yield_percent=0.55,
        net_debt_to_equity=0.62,
        value_trap_risk="LOW",
        valuation_status="FAIR",
        as_of_date="2025-03-31 (最新決算スナップショット)",
        data_source="snapshot",
    ),
    "8306": FinancialMetrics(
        ticker="8306",
        company_name="三菱UFJフィナンシャル・グループ",
        currency="JPY",
        market_cap_trillion_jpy=21.5,
        per=12.1,
        pbr=1.12,
        roe_percent=9.8,
        tsr_percent=44.2,
        operating_profit_margin_percent=26.0,
        dividend_yield_percent=3.25,
        net_debt_to_equity=0.0,
        value_trap_risk="LOW",
        valuation_status="UNDERVALUED",
        as_of_date="2025-03-31 (最新決算スナップショット)",
        data_source="snapshot",
    ),
    "8035": FinancialMetrics(
        ticker="8035",
        company_name="東京エレクトロン",
        currency="JPY",
        market_cap_trillion_jpy=15.2,
        per=26.4,
        pbr=6.8,
        roe_percent=27.5,
        tsr_percent=55.0,
        operating_profit_margin_percent=29.2,
        dividend_yield_percent=1.75,
        net_debt_to_equity=-0.38,
        value_trap_risk="LOW",
        valuation_status="FAIR",
        as_of_date="2025-03-31 (最新決算スナップショット)",
        data_source="snapshot",
    ),
}


def get_stock_valuation(ticker: str, mode: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve valuation metrics (PER, PBR, ROE, TSR, Value Trap Risk) for a given ticker.
    
    Supports both 'snapshot' (deterministic latest snapshot) and 'live_api' (yfinance live feed).
    """
    clean_ticker = ticker.strip().upper().replace(".T", "")
    active_mode = mode or settings.data_source_mode

    if active_mode == "live_api":
        live_res = fetch_live_stock_valuation(clean_ticker)
        if "error" not in live_res and not live_res.get("fallback_needed"):
            return live_res

    # Snapshot fallback or direct snapshot mode
    metric = FINANCIAL_DATABASE.get(clean_ticker)
    if not metric:
        return {
            "error": f"Ticker '{ticker}' not found in financial database.",
            "available_tickers": list(FINANCIAL_DATABASE.keys()),
        }
    return metric.model_dump()


def compare_companies(tickers: List[str], mode: Optional[str] = None) -> List[Dict[str, Any]]:
    """Compare multiple companies across key valuation and capital efficiency metrics."""
    results = []
    for t in tickers:
        res = get_stock_valuation(t, mode=mode)
        if "error" not in res:
            results.append(res)
    return results
