"""Runtime state and durable execution management for writing-agent runs."""

from .state import WritingState

__all__ = ["WritingState", "get_agent_run_manager"]


def __getattr__(name: str):
    if name == "get_agent_run_manager":
        from .manager import get_agent_run_manager

        return get_agent_run_manager
    raise AttributeError(name)
