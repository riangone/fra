"""LangGraph Financial RAG Agent Workflow Construction."""

from typing import Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.models.state import AgentState
from src.graph.nodes.query_rewriter import query_rewriter_node
from src.graph.nodes.hybrid_search import hybrid_search_node
from src.graph.nodes.mcp_tool_runner import mcp_tool_runner_node
from src.graph.nodes.synthesizer import synthesizer_node
from src.graph.nodes.citation_verifier import citation_verifier_node
from src.graph.edges import should_retry_or_finish


def build_financial_rag_graph():
    """
    Constructs the multi-step StateGraph for Financial RAG:
    START -> query_rewriter -> hybrid_search -> mcp_tool_runner -> synthesizer -> citation_verifier
    -> (conditional: pass -> END | retry -> synthesizer)
    """
    workflow = StateGraph(AgentState)

    # Register nodes
    workflow.add_node("query_rewriter", query_rewriter_node)
    workflow.add_node("hybrid_search", hybrid_search_node)
    workflow.add_node("mcp_tool_runner", mcp_tool_runner_node)
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("citation_verifier", citation_verifier_node)

    # Linear pipelines
    workflow.add_edge(START, "query_rewriter")
    workflow.add_edge("query_rewriter", "hybrid_search")
    workflow.add_edge("hybrid_search", "mcp_tool_runner")
    workflow.add_edge("mcp_tool_runner", "synthesizer")
    workflow.add_edge("synthesizer", "citation_verifier")

    # Conditional branch with review loop
    workflow.add_conditional_edges(
        "citation_verifier",
        should_retry_or_finish,
        {
            "synthesizer": "synthesizer",
            END: END,
        }
    )

    # Checkpointer for state persistence and time-travel debugging
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    return app


# Singleton compiled graph
financial_graph = build_financial_rag_graph()
