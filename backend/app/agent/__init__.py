"""Writing agent runtime built on LangGraph."""

__all__ = ["get_agent_run_manager"]


def __getattr__(name):
    if name == "get_agent_run_manager":
        from .runtime.manager import get_agent_run_manager

        return get_agent_run_manager
    raise AttributeError(name)
