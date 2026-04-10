"""
优化器API路由 - 管理持续优化任务
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging

from src.api.dependencies.auth import require_auth
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/optimizer", tags=["Optimizer"])


def _get_optimizer():
    from src.background import optimizer as optimizer_module

    return optimizer_module.continuous_optimizer


class OptimizationStatusResponse(BaseModel):
    running: bool
    total_jobs: int
    completed: int
    failed: int
    pending: int
    running_job: Optional[str]
    progress_pct: float
    jobs: List[Dict[str, Any]]


class TriggerOptimizationRequest(BaseModel):
    job_id: Optional[str] = None  # 如果指定则只运行该任务，否则运行所有


class TriggerOptimizationResponse(BaseModel):
    status: str
    message: str
    triggered_jobs: List[str]


@router.get("/status", response_model=OptimizationStatusResponse)
async def get_optimization_status(
    api_key: str = Depends(require_auth),
) -> OptimizationStatusResponse:
    """
    获取优化器当前状态
    """
    status = _get_optimizer().get_status()
    return OptimizationStatusResponse(**status)


@router.post("/trigger", response_model=TriggerOptimizationResponse)
async def trigger_optimization(
    req: TriggerOptimizationRequest,
    api_key: str = Depends(require_auth),
) -> TriggerOptimizationResponse:
    """
    触发优化任务执行
    如果指定了job_id，则只运行该任务
    否则运行所有待处理任务
    """
    import asyncio
    optimizer = _get_optimizer()

    if req.job_id:
        # 运行指定任务
        job = next((j for j in optimizer.jobs if j.job_id == req.job_id), None)
        if not job:
            return TriggerOptimizationResponse(
                status="error",
                message=f"Job {req.job_id} not found",
                triggered_jobs=[]
            )
        if job.status.value in ["running", "completed"]:
            return TriggerOptimizationResponse(
                status="skipped",
                message=f"Job {job.name} is {job.status.value}",
                triggered_jobs=[req.job_id]
            )

        await optimizer.execute_job(job)
        return TriggerOptimizationResponse(
            status="completed",
            message=f"Job {job.name} completed",
            triggered_jobs=[req.job_id]
        )
    else:
        # 运行所有待处理任务
        triggered = []
        while True:
            job = optimizer.get_next_job()
            if not job:
                break
            await optimizer.execute_job(job)
            triggered.append(job.job_id)

        return TriggerOptimizationResponse(
            status="completed",
            message=f"Completed {len(triggered)} optimization jobs",
            triggered_jobs=triggered
        )


@router.get("/jobs")
async def list_optimization_jobs(
    api_key: str = Depends(require_auth),
) -> List[Dict[str, Any]]:
    """
    列出所有优化任务
    """
    status = _get_optimizer().get_status()
    return status.get("jobs", [])


@router.post("/reset")
async def reset_optimizer(
    api_key: str = Depends(require_auth),
) -> Dict[str, str]:
    """
    重置优化器状态（重新初始化所有任务）
    """
    from src.background.optimizer import ContinuousOptimizer
    import src.background.optimizer as optimizer_module

    # 重新初始化
    optimizer_module.continuous_optimizer = ContinuousOptimizer()

    return {"status": "ok", "message": "Optimizer reset successfully"}


class StartContinuousRequest(BaseModel):
    interval_seconds: int = 60
    max_iterations: int = None  # None表示无限


@router.post("/continuous/start")
async def start_continuous_optimizer(
    req: StartContinuousRequest,
    api_key: str = Depends(require_auth),
) -> Dict[str, str]:
    """
    启动持续优化模式（后台运行）
    """
    import asyncio
    optimizer = _get_optimizer()

    if optimizer.running:
        return {"status": "already_running", "message": "Optimizer is already running"}

    # 在后台启动持续优化
    asyncio.create_task(
        optimizer.run_continuous(
            interval_seconds=req.interval_seconds,
            max_iterations=req.max_iterations
        )
    )

    return {
        "status": "started",
        "message": f"Continuous optimizer started (interval={req.interval_seconds}s)"
    }


@router.post("/continuous/stop")
async def stop_continuous_optimizer(
    api_key: str = Depends(require_auth),
) -> Dict[str, str]:
    """
    停止持续优化模式
    """
    optimizer = _get_optimizer()
    optimizer.running = False
    return {"status": "stopped", "message": "Continuous optimizer stopped"}
