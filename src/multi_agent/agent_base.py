"""
多Agent知识库优化系统
每个Agent负责特定的优化任务，协同工作提升知识库质量
"""

import json
import logging
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent状态"""
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0  # 关键任务（影响准确性）
    HIGH = 1      # 高优先级（影响完整性）
    MEDIUM = 2    # 中等优先级（影响可用性）
    LOW = 3       # 低优先级（优化改进）


@dataclass
class AgentTask:
    """Agent任务"""
    task_id: str
    agent_type: str
    action: str
    params: Dict[str, Any]
    priority: TaskPriority = TaskPriority.MEDIUM
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: AgentStatus = AgentStatus.IDLE
    result: Optional[Any] = None
    error: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "action": self.action,
            "priority": self.priority.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": str(self.result)[:200] if self.result else None,
            "error": self.error
        }


@dataclass
class AgentMetrics:
    """Agent指标"""
    agent_name: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_time: float = 0.0
    last_execution: Optional[datetime] = None
    improvements_made: List[str] = field(default_factory=list)

    def success_rate(self) -> float:
        if self.tasks_completed + self.tasks_failed == 0:
            return 1.0
        return self.tasks_completed / (self.tasks_completed + self.tasks_failed)


class BaseAgent(ABC):
    """
    基础Agent类

    所有优化Agent的基类，定义了统一的接口和行为
    """

    def __init__(self, name: str, knowledge_base_path: str):
        self.name = name
        self.kb_path = Path(knowledge_base_path)
        self.status = AgentStatus.IDLE
        self.metrics = AgentMetrics(agent_name=name)
        self.task_queue: List[AgentTask] = []
        self.current_task: Optional[AgentTask] = None
        self.collaborators: Dict[str, 'BaseAgent'] = {}

        logger.info(f"Agent {self.name} initialized")

    @abstractmethod
    async def process(self, task: AgentTask) -> Any:
        """处理任务的核心方法，由子类实现"""
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """返回Agent的能力列表"""
        pass

    async def execute(self, task: AgentTask) -> Any:
        """执行任务"""
        if task.status != AgentStatus.IDLE:
            logger.warning(f"Task {task.task_id} already processed")
            return task.result

        # 检查依赖
        for dep_id in task.dependencies:
            dep_task = self._find_task(dep_id)
            if not dep_task or dep_task.status != AgentStatus.COMPLETED:
                logger.info(f"Task {task.task_id} waiting for dependency {dep_id}")
                task.status = AgentStatus.WAITING
                return None

        self.current_task = task
        task.status = AgentStatus.RUNNING
        task.started_at = datetime.now()

        logger.info(f"[{self.name}] Executing: {task.action}")

        try:
            start_time = datetime.now()
            result = await self.process(task)
            elapsed = (datetime.now() - start_time).total_seconds()

            task.result = result
            task.status = AgentStatus.COMPLETED
            task.completed_at = datetime.now()

            self.metrics.tasks_completed += 1
            self.metrics.total_execution_time += elapsed
            self.metrics.last_execution = datetime.now()

            # 记录改进
            if result and isinstance(result, dict) and result.get("improvements"):
                self.metrics.improvements_made.extend(result["improvements"])

            logger.info(f"[{self.name}] Completed: {task.action} ({elapsed:.2f}s)")
            return result

        except Exception as e:
            task.status = AgentStatus.FAILED
            task.error = str(e)
            self.metrics.tasks_failed += 1
            logger.error(f"[{self.name}] Failed: {task.action} - {e}")
            return None

        finally:
            self.current_task = None

    def add_task(self, action: str, params: Dict = None,
                 priority: TaskPriority = TaskPriority.MEDIUM,
                 dependencies: List[str] = None) -> AgentTask:
        """添加任务到队列"""
        task = AgentTask(
            task_id=f"{self.name}_{datetime.now().timestamp()}",
            agent_type=self.name,
            action=action,
            params=params or {},
            priority=priority,
            dependencies=dependencies or []
        )
        self.task_queue.append(task)
        return task

    async def process_queue(self) -> List[Any]:
        """处理队列中的所有任务"""
        results = []
        # 按优先级排序
        self.task_queue.sort(key=lambda t: t.priority.value)

        for task in self.task_queue:
            if task.status == AgentStatus.IDLE:
                result = await self.execute(task)
                results.append(result)

        return results

    def delegate(self, agent_name: str, action: str, params: Dict = None) -> Optional[AgentTask]:
        """委托任务给其他Agent"""
        if agent_name not in self.collaborators:
            logger.warning(f"Agent {agent_name} not found in collaborators")
            return None

        target_agent = self.collaborators[agent_name]
        return target_agent.add_task(action, params or {})

    def _find_task(self, task_id: str) -> Optional[AgentTask]:
        """查找任务"""
        for task in self.task_queue:
            if task.task_id == task_id:
                return task
        return None

    def get_status(self) -> Dict:
        """获取Agent状态"""
        return {
            "name": self.name,
            "status": self.status.value,
            "metrics": {
                "completed": self.metrics.tasks_completed,
                "failed": self.metrics.tasks_failed,
                "success_rate": f"{self.metrics.success_rate():.1%}",
                "total_time": f"{self.metrics.total_execution_time:.2f}s",
                "last_execution": self.metrics.last_execution.isoformat() if self.metrics.last_execution else None
            },
            "queue_size": len(self.task_queue),
            "capabilities": self.get_capabilities()
        }


class AgentOrchestrator:
    """
    Agent编排器

    负责协调多个Agent的协作，管理任务分发和结果聚合
    """

    def __init__(self, knowledge_base_path: str):
        self.kb_path = knowledge_base_path
        self.agents: Dict[str, BaseAgent] = {}
        self.global_task_queue: List[AgentTask] = []
        self.session_history: List[Dict] = []

    def register_agent(self, agent: BaseAgent):
        """注册Agent"""
        self.agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")

        # 建立协作网络
        for other_agent in self.agents.values():
            if other_agent.name != agent.name:
                agent.collaborators[other_agent.name] = other_agent
                other_agent.collaborators[agent.name] = agent

    async def run_optimization_cycle(self) -> Dict[str, Any]:
        """运行一轮优化周期"""
        logger.info("="*60)
        logger.info("Starting optimization cycle")
        logger.info("="*60)

        cycle_results = {
            "cycle_id": datetime.now().isoformat(),
            "agents_executed": [],
            "total_improvements": 0,
            "execution_time": 0.0,
            "errors": []
        }

        start_time = datetime.now()

        # 并行执行所有Agent的任务
        tasks = []
        for agent in self.agents.values():
            if agent.task_queue:
                task = asyncio.create_task(agent.process_queue())
                tasks.append((agent.name, task))

        # 等待所有任务完成
        for agent_name, task in tasks:
            try:
                results = await task
                cycle_results["agents_executed"].append(agent_name)

                # 统计改进
                agent = self.agents[agent_name]
                improvements = len(agent.metrics.improvements_made)
                cycle_results["total_improvements"] += improvements

            except Exception as e:
                cycle_results["errors"].append(f"{agent_name}: {str(e)}")

        elapsed = (datetime.now() - start_time).total_seconds()
        cycle_results["execution_time"] = elapsed

        # 保存历史
        self.session_history.append(cycle_results)

        logger.info("="*60)
        logger.info(f"Optimization cycle completed in {elapsed:.2f}s")
        logger.info(f"Improvements made: {cycle_results['total_improvements']}")
        logger.info("="*60)

        return cycle_results

    def get_system_status(self) -> Dict:
        """获取系统整体状态"""
        return {
            "agents": {name: agent.get_status() for name, agent in self.agents.items()},
            "total_agents": len(self.agents),
            "recent_cycles": self.session_history[-5:] if self.session_history else []
        }

    def generate_optimization_report(self) -> str:
        """生成优化报告"""
        report = ["="*70, "知识库优化报告", "="*70, ""]

        # Agent状态
        report.append("📊 Agent状态:")
        for name, agent in self.agents.items():
            status = agent.get_status()
            report.append(f"\n  {name}:")
            report.append(f"    状态: {status['status']}")
            report.append(f"    已完成: {status['metrics']['completed']}")
            report.append(f"    成功率: {status['metrics']['success_rate']}")

        # 改进汇总
        total_improvements = sum(
            len(agent.metrics.improvements_made)
            for agent in self.agents.values()
        )
        report.append(f"\n📈 总改进数: {total_improvements}")

        # 最近周期
        if self.session_history:
            recent = self.session_history[-1]
            report.append(f"\n⏱️  最近周期:")
            report.append(f"    时间: {recent['cycle_id']}")
            report.append(f"    执行时间: {recent['execution_time']:.2f}s")
            report.append(f"    改进数: {recent['total_improvements']}")

        report.append("\n" + "="*70)
        return "\n".join(report)


# 导出
__all__ = [
    'BaseAgent',
    'AgentOrchestrator',
    'AgentTask',
    'AgentStatus',
    'TaskPriority',
    'AgentMetrics'
]
