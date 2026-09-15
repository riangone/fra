"""Financial Domain and Metric Models."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FinancialMetrics(BaseModel):
    ticker: str
    company_name: str
    currency: str = "JPY"
    market_cap_trillion_jpy: float
    per: float = Field(description="Price-to-Earnings Ratio")
    pbr: float = Field(description="Price-to-Book Ratio")
    roe_percent: float = Field(description="Return on Equity in percentage")
    tsr_percent: float = Field(description="Total Shareholder Return")
    operating_profit_margin_percent: float
    dividend_yield_percent: float
    net_debt_to_equity: float
    value_trap_risk: str = "LOW"  # LOW, MODERATE, HIGH
    valuation_status: str = "FAIR"  # UNDERVALUED, FAIR, OVERVALUED
    as_of_date: str


class DisclosureItem(BaseModel):
    ticker: str
    company_name: str
    fiscal_year: str
    revenue_billion_jpy: float
    operating_income_billion_jpy: float
    net_income_billion_jpy: float
    guidance_revision: Optional[str] = None
    major_catalysts: List[str] = Field(default_factory=list)


class MacroIndicator(BaseModel):
    indicator: str
    value: str
    trend: str
    source: str
    updated_at: str
