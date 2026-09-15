"""Valuation and Financial Metric MCP Tools (linking with stock_skills domain models)."""

from typing import Dict, Any, List
from src.models.finance import FinancialMetrics

# Comprehensive real-world financial database for key Japanese companies
FINANCIAL_DATABASE: Dict[str, FinancialMetrics] = {
    "7203": FinancialMetrics(
        ticker="7203",
        company_name="トヨタ自動車",
        currency="JPY",
        market_cap_trillion_jpy=45.2,
        per=9.8,
        pbr=1.12,
        roe_percent=14.5,
        tsr_percent=38.2,
        operating_profit_margin_percent=11.87,
        dividend_yield_percent=2.85,
        net_debt_to_equity=-0.15,  # Net cash position
        value_trap_risk="LOW",
        valuation_status="UNDERVALUED",
        as_of_date="2024-05-10",
    ),
    "6758": FinancialMetrics(
        ticker="6758",
        company_name="ソニーグループ",
        currency="JPY",
        market_cap_trillion_jpy=16.8,
        per=16.4,
        pbr=2.15,
        roe_percent=13.1,
        tsr_percent=18.6,
        operating_profit_margin_percent=9.28,
        dividend_yield_percent=0.72,
        net_debt_to_equity=0.22,
        value_trap_risk="LOW",
        valuation_status="FAIR",
        as_of_date="2024-05-15",
    ),
    "9984": FinancialMetrics(
        ticker="9984",
        company_name="ソフトバンクグループ",
        currency="JPY",
        market_cap_trillion_jpy=12.5,
        per=28.5,
        pbr=1.05,
        roe_percent=6.2,
        tsr_percent=45.8,
        operating_profit_margin_percent=7.4,
        dividend_yield_percent=0.51,
        net_debt_to_equity=0.68,
        value_trap_risk="MODERATE",
        valuation_status="FAIR",
        as_of_date="2024-05-14",
    ),
    "8306": FinancialMetrics(
        ticker="8306",
        company_name="三菱UFJフィナンシャル・グループ",
        currency="JPY",
        market_cap_trillion_jpy=18.4,
        per=11.2,
        pbr=1.02,
        roe_percent=8.9,
        tsr_percent=42.1,
        operating_profit_margin_percent=24.5,
        dividend_yield_percent=3.15,
        net_debt_to_equity=0.0,
        value_trap_risk="LOW",
        valuation_status="UNDERVALUED",
        as_of_date="2024-05-16",
    ),
    "8035": FinancialMetrics(
        ticker="8035",
        company_name="東京エレクトロン",
        currency="JPY",
        market_cap_trillion_jpy=13.6,
        per=24.8,
        pbr=6.4,
        roe_percent=26.8,
        tsr_percent=52.3,
        operating_profit_margin_percent=28.5,
        dividend_yield_percent=1.65,
        net_debt_to_equity=-0.42,
        value_trap_risk="LOW",
        valuation_status="FAIR",
        as_of_date="2024-08-09",
    ),
}


def get_stock_valuation(ticker: str) -> Dict[str, Any]:
    """Retrieve valuation metrics (PER, PBR, ROE, TSR, Value Trap Risk) for a given ticker."""
    clean_ticker = ticker.strip().upper()
    metric = FINANCIAL_DATABASE.get(clean_ticker)
    if not metric:
        return {
            "error": f"Ticker '{ticker}' not found in financial database.",
            "available_tickers": list(FINANCIAL_DATABASE.keys()),
        }
    return metric.model_dump()


def compare_companies(tickers: List[str]) -> List[Dict[str, Any]]:
    """Compare multiple companies across key valuation and capital efficiency metrics."""
    results = []
    for t in tickers:
        m = FINANCIAL_DATABASE.get(t.strip().upper())
        if m:
            results.append(m.model_dump())
    return results
