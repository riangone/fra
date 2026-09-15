"""Corporate Disclosures and Macro Indicators MCP Tools."""

from typing import Dict, Any, List
from src.models.finance import DisclosureItem, MacroIndicator

DISCLOSURES_DATABASE: Dict[str, DisclosureItem] = {
    "7203": DisclosureItem(
        ticker="7203",
        company_name="トヨタ自動車",
        fiscal_year="2024年3月期 通期",
        revenue_billion_jpy=45095.3,
        operating_income_billion_jpy=5352.9,
        net_income_billion_jpy=4944.9,
        guidance_revision="2025年3月期予想: 営業利益4兆3000億円 (先行投資2兆円織り込み)",
        major_catalysts=["HEV世界販売急増", "円安進行", "全固体電池2兆円追加投資"],
    ),
    "6758": DisclosureItem(
        ticker="6758",
        company_name="ソニーグループ",
        fiscal_year="2024年3月期 通期",
        revenue_billion_jpy=13020.8,
        operating_income_billion_jpy=1208.8,
        net_income_billion_jpy=970.6,
        guidance_revision="2025年3月期予想: 営業利益1兆2750億円 (半導体歩留まり改善)",
        major_catalysts=["CMOSイメージセンサー出荷増", "ソニーフィナンシャル分離上場", "PS5販売2080万台"],
    ),
    "9984": DisclosureItem(
        ticker="9984",
        company_name="ソフトバンクグループ",
        fiscal_year="2024年3月期 通期",
        revenue_billion_jpy=6756.5,
        operating_income_billion_jpy=740.2,
        net_income_billion_jpy=227.6,
        guidance_revision="非開示 (投資事業の変動性のため)",
        major_catalysts=["英Arm株価急伸による含み益拡大", "ASI/AIデータセンター集中投資", "LTV 8.4%健全性維持"],
    ),
    "8306": DisclosureItem(
        ticker="8306",
        company_name="三菱UFJフィナンシャル・グループ",
        fiscal_year="2024年3月期 通期",
        revenue_billion_jpy=11045.0,
        operating_income_billion_jpy=2050.0,
        net_income_billion_jpy=1490.7,
        guidance_revision="2025年3月期予想: 純利益1兆5000億円 (過去最高更新)",
        major_catalysts=["日銀マイナス金利解除による利ざや改善", "モルガン・スタンレー協業強化", "自社株買い1000億円"],
    ),
}

MACRO_INDICATORS: List[MacroIndicator] = [
    MacroIndicator(
        indicator="日銀政策金利 (無担保コール翌日物)",
        value="0.25%",
        trend="利上げ局面 (タカ派姿勢継続)",
        source="日本銀行 政策委員会",
        updated_at="2024-07-31",
    ),
    MacroIndicator(
        indicator="日経平均株価 (Nikkei 225)",
        value="38,500円水準",
        trend="高値圏保ち合い・海外投資家の日本株買い意欲継続",
        source="東京証券取引所",
        updated_at="2024-08-01",
    ),
    MacroIndicator(
        indicator="USD/JPY (ドル円レート)",
        value="149.80円",
        trend="日米金利差縮小観測に伴う円高バイアス",
        source="外為市場",
        updated_at="2024-08-01",
    ),
]


def get_financial_disclosure(ticker: str) -> Dict[str, Any]:
    """Retrieve the latest financial disclosures and earnings report for a given ticker."""
    clean_ticker = ticker.strip().upper()
    item = DISCLOSURES_DATABASE.get(clean_ticker)
    if not item:
        return {
            "error": f"Disclosure for ticker '{ticker}' not found.",
            "available_tickers": list(DISCLOSURES_DATABASE.keys()),
        }
    return item.model_dump()


def get_macro_indicators() -> List[Dict[str, Any]]:
    """Retrieve current macroeconomic indicators (BOJ interest rate, Nikkei 225, USD/JPY)."""
    return [m.model_dump() for m in MACRO_INDICATORS]
