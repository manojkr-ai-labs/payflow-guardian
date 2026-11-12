"""Allowlisted assistant tools. The assistant does not call PayPal directly."""

from app.modules.assistant.tools import TOOL_NAMES

__all__ = ["TOOL_NAMES"]
