"""Prompt fragments and builders for agent writing stages."""

from .draft import WRITING_SOURCE_RULES
from .review import KNG_USAGE_RULES

__all__ = ["KNG_USAGE_RULES", "WRITING_SOURCE_RULES"]
