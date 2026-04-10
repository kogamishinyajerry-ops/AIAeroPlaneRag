"""
Multi-Agent Base Module
提供多Agent架构的基础类和接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class AgentRole(Enum):
    PLANNER = "planner"
    TOOL = "tool"
    CHECKER = "checker"
    ANSWER = "answer"


@dataclass
class AgentMessage:
    """Agent之间的消息传递格式"""
    role: AgentRole
    content: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class RetrievalPlan:
    """Planner生成的检索计划"""
    query: str
    intent_type: str
    intent_confidence: float
    retrieval_strategy: str  # "simple", "expanded", "graph_first", "multi_source"
    top_k: int
    use_graph: bool
    use_expansion: bool
    follow_up_queries: List[str]
    response_mode: str = "standard"
    answer_style: str = "standard"


@dataclass
class RetrievalResult:
    """检索结果"""
    contexts: List[Dict[str, Any]]
    graph_data: Optional[Dict[str, Any]]
    relevance_scores: Optional[List[float]]
    success: bool
    error: Optional[str]


@dataclass
class ValidationResult:
    """Checker验证结果"""
    is_valid: bool
    quality_score: float
    issues: List[str]
    suggestions: List[str]


class BaseAgent(ABC):
    """Agent基类"""

    def __init__(self, name: str, role: AgentRole):
        self.name = name
        self.role = role

    @abstractmethod
    async def process(self, message: AgentMessage) -> AgentMessage:
        """处理消息并返回响应"""
        pass

    def log(self, level: str, message: str):
        """日志记录"""
        import logging
        logger = logging.getLogger(f"agent.{self.role.value}")
        getattr(logger, level.lower())(f"[{self.name}] {message}")
