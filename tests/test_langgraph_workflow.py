"""Integration tests for LangGraph Workflow execution."""

import pytest
from src.graph.workflow import financial_graph


@pytest.mark.asyncio
async def test_full_workflow_execution():
    initial_state = {
        "session_id": "test-integ-1",
        "query": "ソニーグループの金融事業スピンオフ計画について教えてください",
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

    config = {"configurable": {"thread_id": "integ-thread-1"}}
    result = await financial_graph.ainvoke(initial_state, config=config)

    assert "6758" in result["target_tickers"]
    assert len(result["retrieved_chunks"]) > 0
    assert len(result["final_response"]) > 50
    assert result["audit_report"] is not None
    assert result["citation_consistency_score"] > 0.5
    assert len(result["execution_trace"]) >= 5
