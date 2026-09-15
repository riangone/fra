"""Corporate Disclosures and Macro Indicators MCP Tools."""

from typing import Dict, Any, List, Optional
from src.models.finance import DisclosureItem, MacroIndicator
from src.mcp_server.tools.live_market_client import fetch_live_macro_indicators
from config.settings import settings

DISCLOSURES_DATABASE: Dict[str, DisclosureItem] = {
    "7203": DisclosureItem(
        ticker="7203",
        company_name="トヨタ自動車",
        fiscal_year="2025年3月期 通期予想 / 2024実績",
        revenue_billion_jpy=46000.0,
        operating_income_billion_jpy=4300.0,
        net_income_billion_jpy=3570.0,
        guidance_revision="2025年3月期予想: 営業利益4兆3000億円 (次世代BEV・全固体電池先行投資2兆円織り込み)",
        major_catalysts=["HEV世界販売急増", "次世代EVソフトウェアArene投入", "全固体電池2兆円追加投資"],
        data_source="snapshot",
    ),
    "6758": DisclosureItem(
        ticker="6758",
        company_name="ソニーグループ",
        fiscal_year="2025年3月期 通期予想 / 2024実績",
        revenue_billion_jpy=12600.0,
        operating_income_billion_jpy=1310.0,
        net_income_billion_jpy=980.0,
        guidance_revision="2025年3月期予想: 営業利益1兆3100億円 (イメージセンサー増産及び音楽・アニメ伸長)",
        major_catalysts=["CMOSイメージセンサー出荷増", "ソニーフィナンシャル分離上場", "PS5 Pro投入"],
        data_source="snapshot",
    ),
    "9984": DisclosureItem(
        ticker="9984",
        company_name="ソフトバンクグループ",
        fiscal_year="2025年3月期 通期 / 最新",
        revenue_billion_jpy=7100.0,
        operating_income_billion_jpy=820.0,
        net_income_billion_jpy=650.0,
        guidance_revision="非開示 (投資事業公正価値変動のため)",
        major_catalysts=["英Arm時価総額拡大による含み益増大", "ASI/AIデータセンター集中投資", "LTV 8.4%健全性維持"],
        data_source="snapshot",
    ),
    "8306": DisclosureItem(
        ticker="8306",
        company_name="三菱UFJフィナンシャル・グループ",
        fiscal_year="2025年3月期 通期予想 / 2024実績",
        revenue_billion_jpy=11500.0,
        operating_income_billion_jpy=2200.0,
        net_income_billion_jpy=1750.0,
        guidance_revision="2025年3月期予想: 純利益1兆7500億円 (過去最高益更新見通し)",
        major_catalysts=["日銀利上げによる国内預貸金利ざや拡大", "モルガン・スタンレー協業強化", "自社株買い及び増配"],
        data_source="snapshot",
    ),
}

MACRO_INDICATORS: List[MacroIndicator] = [
    MacroIndicator(
        indicator="日銀政策金利 (無担保コール翌日物)",
        value="0.25%",
        trend="利上げ局面 (追加利上げ観測継続・タカ派姿勢)",
        source="日本銀行 政策委員会",
        updated_at="2025-03-31",
        data_source="snapshot",
    ),
    MacroIndicator(
        indicator="日経平均株価 (Nikkei 225)",
        value="38,800円水準",
        trend="高値圏保ち合い・東証資本効率要請による下支え",
        source="東京証券取引所",
        updated_at="2025-03-31",
        data_source="snapshot",
    ),
    MacroIndicator(
        indicator="USD/JPY (ドル円レート)",
        value="151.50円",
        trend="日米金利差縮小観測と為替介入警戒感",
        source="外為市場",
        updated_at="2025-03-31",
        data_source="snapshot",
    ),
]


def get_financial_disclosure(ticker: str, mode: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve the latest financial disclosures and earnings report for a given ticker."""
    clean_ticker = ticker.strip().upper().replace(".T", "")
    item = DISCLOSURES_DATABASE.get(clean_ticker)
    if not item:
        return {
            "error": f"Disclosure for ticker '{ticker}' not found.",
            "available_tickers": list(DISCLOSURES_DATABASE.keys()),
        }
    return item.model_dump()


def get_macro_indicators(mode: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve current macroeconomic indicators (BOJ interest rate, Nikkei 225, USD/JPY).
    
    Supports both 'snapshot' (deterministic snapshot) and 'live_api' (real-time yfinance market feed).
    """
    active_mode = mode or settings.data_source_mode

    if active_mode == "live_api":
        live_res = fetch_live_macro_indicators()
        if live_res:
            return live_res

    return [m.model_dump() for m in MACRO_INDICATORS]
