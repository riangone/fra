"""Conditional routing edges for LangGraph workflow."""

from langgraph.graph import END
from src.models.state import AgentState
from config.settings import settings


def should_retry_or_finish(state: AgentState) -> str:
    """
    Decides whether to route to END or loop back to synthesizer for self-correction.
    """
    if state.get("verification_passed", False):
        return END

    retry_count = state.get("retry_count", 0)
    if retry_count < settings.max_verification_retries:
        return "synthesizer"

    return END
