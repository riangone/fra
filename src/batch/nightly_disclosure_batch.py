"""
Nightly Batch Processing Pipeline for Financial Disclosures.
(定期実行・非同期バッチによる生成基盤)

针对日经新闻社/金融机构的生产级需求：
用户输入并非唯一的触发源，在东证收盘（15:00）后，系统会接收批量决算开示与财经报道，
异步并发调用 LangGraph 工作流与引用一致率审计引擎，批量生成研报摘要与引用审计记录。
"""

import asyncio
import logging
import time
from typing import List, Dict, Any
from datetime import datetime, timezone

from src.graph.workflow import build_financial_rag_graph
from src.models.state import AgentState
from src.retrieval.hybrid_retriever import HybridRetriever

logger = logging.getLogger("financial_rag.batch")


class NightlyDisclosureBatchProcessor:
    """
    东证决算速报与宏观新闻离线批处理管线
    对应日经 JD:「定期実行・非同期バッチによる生成基盤など、ユーザー入力をトリガーとしない処理形態」
    """

    def __init__(self, concurrency_limit: int = 3):
        self.graph = build_financial_rag_graph()
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.retriever = HybridRetriever()

    async def process_single_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """异步处理单条决算或新闻批处理任务"""
        async with self.semaphore:
            start_time = time.perf_counter()
            task_id = task.get("id", f"task_{int(time.time()*1000)}")
            query = task.get("query", "")
            ticker = task.get("ticker", "")

            # 构造 LangGraph 初始状态
            initial_state: AgentState = {
                "session_id": task_id,
                "query": query,
                "data_source_mode": "snapshot",
                "rewritten_query": "",
                "target_tickers": [ticker] if ticker else [],
                "intent": "batch_disclosure",
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

            try:
                # 异步运行 LangGraph 状态图
                config = {"configurable": {"thread_id": task_id}}
                final_state = await self.graph.ainvoke(initial_state, config=config)
                latency_ms = (time.perf_counter() - start_time) * 1000

                audit = final_state.get("audit_report") or {}
                consistency = final_state.get("citation_consistency_score", 0.0)
                is_valid = final_state.get("verification_passed", False)

                return {
                    "task_id": task_id,
                    "ticker": ticker,
                    "query": query,
                    "status": "SUCCESS" if is_valid else "ATTRIBUTION_WARNING",
                    "latency_ms": round(latency_ms, 2),
                    "consistency_rate": consistency,
                    "generated_text": (final_state.get("final_response", "") or "")[:120] + "...",
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }
            except Exception as exc:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.error(f"Batch task {task_id} failed: {exc}")
                return {
                    "task_id": task_id,
                    "ticker": ticker,
                    "status": "FAILED",
                    "error": str(exc),
                    "latency_ms": round(latency_ms, 2),
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }

    async def run_batch(self, batch_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量并发执行，返回批处理统计报告"""
        start_all = time.perf_counter()
        logger.info(f"Starting batch generation for {len(batch_tasks)} disclosure items...")

        tasks = [self.process_single_task(item) for item in batch_tasks]
        results = await asyncio.gather(*tasks)

        total_time_ms = (time.perf_counter() - start_all) * 1000
        success_count = sum(1 for r in results if r["status"] == "SUCCESS")
        avg_consistency = (
            sum(r.get("consistency_rate", 0.0) for r in results if "consistency_rate" in r)
            / len(results)
            if results
            else 0.0
        )

        return {
            "total_items": len(batch_tasks),
            "success_items": success_count,
            "average_consistency_rate": round(avg_consistency, 4),
            "total_batch_duration_ms": round(total_time_ms, 2),
            "throughput_qps": round(len(batch_tasks) / (total_time_ms / 1000), 2) if total_time_ms > 0 else 0,
            "details": results,
        }


# 便捷测试与 CLI 驱动
if __name__ == "__main__":
    sample_batch = [
        {
            "id": "batch_7203",
            "ticker": "7203",
            "query": "トヨタ自動車の通期業績と営業利益水準の要約を生成せよ",
        },
        {
            "id": "batch_6758",
            "ticker": "6758",
            "query": "ソニーグループの金融事業スピンオフ計画の要点を整理せよ",
        },
        {
            "id": "batch_9984",
            "ticker": "9984",
            "query": "ソフトバンクグループの黒字転換要因とSVF投資先動向をまとめよ",
        },
    ]

    processor = NightlyDisclosureBatchProcessor(concurrency_limit=2)
    summary = asyncio.run(processor.run_batch(sample_batch))
    print("\n--- 批处理生成报告 (Batch Pipeline Summary) ---")
    print(f"总处理数: {summary['total_items']}, 成功数: {summary['success_items']}")
    print(f"平均引用一致率: {summary['average_consistency_rate'] * 100:.1f}%")
    print(f"总耗时: {summary['total_batch_duration_ms']} ms (吞吐: {summary['throughput_qps']} QPS)")
