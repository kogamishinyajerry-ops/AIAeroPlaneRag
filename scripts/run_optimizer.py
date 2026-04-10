#!/usr/bin/env python3
"""
优化器CLI - 运行多Agent持续优化
"""
import asyncio
import logging
import sys
import os
from pathlib import Path

# Setup paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("AeroPower-RAG 多Agent优化器")
    logger.info("=" * 60)

    from src.multi_agent.optimizer import OptimizationCoordinator

    coordinator = OptimizationCoordinator()

    logger.info(f"加载了 {len(coordinator.tasks)} 个优化任务")
    logger.info("")

    # 执行优化周期
    logger.info("开始执行优化周期...")
    summary = await coordinator.run_optimization_cycle()

    logger.info("")
    logger.info("=" * 60)
    logger.info("优化周期完成")
    logger.info(f"总任务: {summary['total_tasks']}")
    logger.info(f"完成: {summary['completed']}")
    logger.info(f"失败: {summary['failed']}")
    logger.info("=" * 60)

    # 显示结果
    for result in summary.get("results", []):
        if result.get("result", {}).get("status") == "completed":
            improvements = result["result"].get("improvements", [])
            logger.info(f"✓ {result['task']}")
            for imp in improvements:
                logger.info(f"  - {imp}")

    return summary


if __name__ == "__main__":
    asyncio.run(main())
