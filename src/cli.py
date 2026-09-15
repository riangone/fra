"""Interactive CLI for Financial RAG Agent."""

import asyncio
import sys
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.workflow import financial_graph


async def run_query(query: str, stream: bool = True):
    print(f"\n==================================================================")
    print(f"📊 Financial RAG Agent: Processing Query")
    print(f"   Query: {query}")
    print(f"==================================================================")

    initial_state = {
        "session_id": "cli-session",
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

    config = {"configurable": {"thread_id": "cli-thread-1"}}

    if stream:
        print("\n⚡ [Agent Execution Flow]:")
        async for output in financial_graph.astream(initial_state, config=config):
            for node_name, state_update in output.items():
                if node_name == "query_rewriter":
                    print(f"  ✓ [Query Rewriter] Tickers: {state_update.get('target_tickers')}, Intent: {state_update.get('intent')}")
                elif node_name == "hybrid_search":
                    chunks = state_update.get("retrieved_chunks", [])
                    print(f"  ✓ [Hybrid Search] Retrieved {len(chunks)} chunks via BM25 + Dense RRF")
                elif node_name == "mcp_tool_runner":
                    metrics = state_update.get("financial_metrics", [])
                    print(f"  ✓ [MCP Tool Runner] Invoked MCP server, fetched {len(metrics)} metric objects")
                elif node_name == "synthesizer":
                    print(f"  ✓ [Synthesizer] Drafted synthesis with sentence-level citation tags")
                elif node_name == "citation_verifier":
                    audit = state_update.get("audit_report", {})
                    print(f"  ✓ [Citation Verifier] Consistency Rate: {audit.get('attribution_consistency_rate')*100:.1f}%, Verdict: {audit.get('verdict')}")
        
        # Get final state
        result = await financial_graph.ainvoke(initial_state, config=config)
    else:
        result = await financial_graph.ainvoke(initial_state, config=config)

    print("\n------------------------------------------------------------------")
    print("📝 [Generated Synthesis]:")
    print("------------------------------------------------------------------")
    print(result.get("final_response", ""))

    audit = result.get("audit_report", {})
    print("\n------------------------------------------------------------------")
    print("🔍 [Citation Attribution Audit Report (引用一致率監査)]:")
    print("------------------------------------------------------------------")
    print(f"• 引用一致率 (Attribution Consistency): {audit.get('attribution_consistency_rate', 0.0)*100:.1f}%")
    print(f"• 引用適合率 (Citation Precision):     {audit.get('citation_precision', 0.0)*100:.1f}%")
    print(f"• 引用再現率 (Citation Recall):        {audit.get('citation_recall', 0.0)*100:.1f}%")
    print(f"• 判定結果 (Audit Verdict):            {audit.get('verdict')}")
    print("==================================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Financial RAG Agent CLI")
    parser.add_argument("query", nargs="?", default="トヨタ自動車の2024年3月期の営業利益とBEV投資計画について教えてください")
    parser.add_argument("--sync", action="store_true", help="Run in sync non-streaming mode")
    args = parser.parse_args()

    asyncio.run(run_query(args.query, stream=not args.sync))


if __name__ == "__main__":
    main()
