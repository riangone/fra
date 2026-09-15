import asyncio
import json
import time
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Dict, Any, List
from src.graph.workflow import financial_graph
from eval.metrics import compute_hit_rate_at_k, compute_mrr, compute_faithfulness_heuristic


async def evaluate_dataset(golden_dataset_path: Path) -> Dict[str, Any]:
    with open(golden_dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    results = []
    total_latency = 0.0

    hit_1_list = []
    hit_3_list = []
    hit_5_list = []
    mrr_list = []
    precision_list = []
    recall_list = []
    consistency_list = []
    faithfulness_list = []

    print(f"\n=======================================================")
    print(f"🚀 Running Financial RAG Evaluation ({len(cases)} Cases)")
    print(f"=======================================================\n")

    for idx, case in enumerate(cases, start=1):
        cid = case["id"]
        query = case["query"]
        expected_docs = case.get("expected_doc_ids", [])
        expected_keywords = case.get("expected_keywords", [])

        start_time = time.time()
        initial_state = {
            "session_id": f"eval-{cid}",
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
        config = {"configurable": {"thread_id": f"eval-thread-{cid}"}}
        output = await financial_graph.ainvoke(initial_state, config=config)
        elapsed_ms = (time.time() - start_time) * 1000
        total_latency += elapsed_ms

        retrieved_ids = [c["id"] for c in output.get("retrieved_chunks", [])]
        answer = output.get("final_response", "")
        audit = output.get("audit_report", {})

        # Compute metrics
        h1 = compute_hit_rate_at_k(retrieved_ids, expected_docs, k=1)
        h3 = compute_hit_rate_at_k(retrieved_ids, expected_docs, k=3)
        h5 = compute_hit_rate_at_k(retrieved_ids, expected_docs, k=5)
        mrr = compute_mrr(retrieved_ids, expected_docs, k=5)
        faith = compute_faithfulness_heuristic(answer, expected_keywords)

        prec = audit.get("citation_precision", 0.0)
        rec = audit.get("citation_recall", 0.0)
        cons = audit.get("attribution_consistency_rate", 0.0)

        hit_1_list.append(h1)
        hit_3_list.append(h3)
        hit_5_list.append(h5)
        mrr_list.append(mrr)
        precision_list.append(prec)
        recall_list.append(rec)
        consistency_list.append(cons)
        faithfulness_list.append(faith)

        print(f"[{idx}/{len(cases)}] {cid}: {query[:35]}...")
        print(f"      Top Retrieved: {retrieved_ids[:2]}")
        print(f"      Hit@1: {h1:.1f} | MRR@5: {mrr:.2f} | 引用一致率: {cons:.2f} | 適合率: {prec:.2f} | {elapsed_ms:.1f}ms\n")

        results.append({
            "id": cid,
            "query": query,
            "retrieved_ids": retrieved_ids,
            "hit_at_1": h1,
            "hit_at_3": h3,
            "hit_at_5": h5,
            "mrr": mrr,
            "faithfulness": faith,
            "citation_precision": prec,
            "citation_recall": rec,
            "citation_consistency": cons,
            "latency_ms": elapsed_ms,
        })

    n = len(cases)
    summary = {
        "total_cases": n,
        "avg_hit_at_1": round(sum(hit_1_list) / n, 3),
        "avg_hit_at_3": round(sum(hit_3_list) / n, 3),
        "avg_hit_at_5": round(sum(hit_5_list) / n, 3),
        "avg_mrr_at_5": round(sum(mrr_list) / n, 3),
        "avg_faithfulness": round(sum(faithfulness_list) / n, 3),
        "avg_citation_precision": round(sum(precision_list) / n, 3),
        "avg_citation_recall": round(sum(recall_list) / n, 3),
        "avg_citation_consistency": round(sum(consistency_list) / n, 3),
        "avg_latency_ms": round(total_latency / n, 2),
    }

    print("=======================================================")
    print("📊 BENCHMARK SUMMARY REPORT")
    print("=======================================================")
    print(f"• 検索精度 (Retrieval):")
    print(f"  - Hit Rate@1:            {summary['avg_hit_at_1'] * 100:.1f}%")
    print(f"  - Hit Rate@3:            {summary['avg_hit_at_3'] * 100:.1f}%")
    print(f"  - Hit Rate@5:            {summary['avg_hit_at_5'] * 100:.1f}%")
    print(f"  - Mean Reciprocal Rank:  {summary['avg_mrr_at_5']:.3f}")
    print(f"• 根拠性・引用精度 (Citation Attribution):")
    print(f"  - 引用一致率 (Consistency): {summary['avg_citation_consistency'] * 100:.1f}%")
    print(f"  - 引用適合率 (Precision):   {summary['avg_citation_precision'] * 100:.1f}%")
    print(f"  - 引用再現率 (Recall):      {summary['avg_citation_recall'] * 100:.1f}%")
    print(f"  - 忠実度 (Faithfulness):    {summary['avg_faithfulness'] * 100:.1f}%")
    print(f"• システム性能 (Latency):")
    print(f"  - 平均レイテンシ:          {summary['avg_latency_ms']:.1f} ms")
    print("=======================================================\n")

    return {"summary": summary, "details": results}


def main():
    dataset_path = Path(__file__).resolve().parents[1] / "data" / "golden_eval_dataset.json"
    asyncio.run(evaluate_dataset(dataset_path))


if __name__ == "__main__":
    main()
