"""Production Showcase Demo Script for Financial RAG Agent.

Demonstrates:
1. Multi-step LangGraph State Machine execution
2. MCP Tool discovery and dynamic execution
3. BM25 + Dense Vector Hybrid Search with Reciprocal Rank Fusion (RRF)
4. Sentence-level Citation Attribution & Consistency Verification (引用一致率監査)
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.workflow import financial_graph
from src.mcp_server.server import mcp_server


async def run_showcase():
    print("==========================================================================")
    print("🌟 Production Showcase: Financial RAG Agent (日経・金融向け AI エージェント)")
    print("==========================================================================")

    # 1. Inspect MCP Tools
    tools = await mcp_server.list_tools()
    print("\n[1] 🛠️  Registered MCP Tools:")
    for t in tools:
        print(f"    • {t.name}: {t.description}")

    # 2. Sample Financial Query
    test_queries = [
        "トヨタ自動車の2024年3月期の営業利益とBEV投資計画について教えてください",
        "ソニーグループの金融子会社スピンオフ計画と半導体事業の動向は？",
    ]

    for idx, query in enumerate(test_queries, 1):
        print(f"\n--------------------------------------------------------------------------")
        print(f"[2.{idx}] 🔎 Processing Query: \"{query}\"")
        print(f"--------------------------------------------------------------------------")

        initial_state = {
            "session_id": f"showcase-session-{idx}",
            "query": query,
            "rewritten_query": "",
            "target_tickers": [],
            "intent": "general",
            "retrieved_chunks": [],
            "financial_metrics": [],
            "draft_response": "",
            "final_response": "",
            "citations": [],
            "audit_report": None,
            "citation_consistency_score": 0.0,
            "verification_passed": False,
            "retry_count": 0,
            "execution_trace": [],
            "error": None,
        }

        config = {"configurable": {"thread_id": f"showcase-thread-{idx}"}}
        result = await financial_graph.ainvoke(initial_state, config=config)

        print(f"  • Target Tickers: {result['target_tickers']}")
        print(f"  • Detected Intent: {result['intent']}")
        print(f"  • Hybrid Retrieved Chunks: {len(result['retrieved_chunks'])}")
        for c in result['retrieved_chunks'][:2]:
            print(f"    - [{c['id']}] {c['title']} (RRF Score: {c['rrf_score']:.4f})")

        print("\n  📄 [Synthesized Report with Grounded Citations]:")
        for line in result['final_response'].split("\n"):
            print(f"    {line}")

        audit = result['audit_report']
        print("\n  🛡️  [Automated Citation Consistency Audit (引用一致率監査)]:")
        print(f"    - 判定 (Verdict):             {audit['verdict']}")
        print(f"    - 引用一致率 (Consistency):    {audit['attribution_consistency_rate']*100:.1f}%")
        print(f"    - 引用適合率 (Precision):      {audit['citation_precision']*100:.1f}%")
        print(f"    - 引用再現率 (Recall):         {audit['citation_recall']*100:.1f}%")
        print(f"    - 検証済み引用文数:            {audit['verified_citations']} / {audit['cited_sentences']}")

    print("\n==========================================================================")
    print("✅ Showcase execution finished successfully!")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_showcase())
