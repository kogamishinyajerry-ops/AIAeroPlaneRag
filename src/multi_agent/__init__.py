"""
Multi-Agent System for AeroPower-RAG
提供Planner-Checker-Answer的多Agent架构
"""
from .base import AgentRole, AgentMessage, BaseAgent
from .planner import PlannerAgent
from .tool import ToolAgent
from .checker import CheckerAgent
from .answer import AnswerAgent
from .coordinator import AgentCoordinator

__all__ = [
    "AgentRole",
    "AgentMessage",
    "BaseAgent",
    "PlannerAgent",
    "ToolAgent",
    "CheckerAgent",
    "AnswerAgent",
    "AgentCoordinator",
]
