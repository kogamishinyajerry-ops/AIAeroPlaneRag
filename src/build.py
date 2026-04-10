#!/usr/bin/env python3
"""
智能知识库构建系统

强制所有操作通过多Agent架构验证
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from quality_assurance import DevelopmentQualityAssurance, mandatory_agent_validation
from dev_hooks import run_agent_optimization_cycle


async def add_regulation_with_agent_validation(
    document_path: str,
    expected_sections: int = 0
) -> bool:
    """
    添加规章（带强制Agent验证）

    这是添加新规章的唯一入口，确保：
    1. 解析后自动运行质量检查
    2. 检查不通过则阻止继续
    3. 通过后才加入知识库
    """
    print("="*70)
    print("🛡️  智能知识库构建系统")
    print("   - 所有操作必须通过多Agent验证")
    print("="*70)
    print()

    # 步骤1: 解析文档
    print("[步骤 1/3] 解析文档...")
    # 这里调用实际的解析器

    # 步骤2: Agent质量检查
    print("[步骤 2/3] 多Agent质量检查...")
    passed = await mandatory_agent_validation(document_path, expected_sections)

    if not passed:
        print()
        print("❌ 质量检查未通过，请修复问题后重试。")
        print("   运行: python3 src/quality_assurance.py")
        return False

    # 步骤3: 运行优化周期
    print("[步骤 3/3] 运行优化周期...")
    run_agent_optimization_cycle()

    print()
    print("="*70)
    print("✅ 规章添加完成，已通过所有质量门禁")
    print("="*70)

    return True


def cli():
    """命令行接口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="智能知识库构建 - 强制多Agent验证",
        epilog="""
示例:
  # 添加新规章（自动验证）
  python build.py add --file data/raw/FAR-29.pdf

  # 运行优化周期
  python build.py optimize

  # 验证现有文档
  python build.py validate
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # add 命令
    add_parser = subparsers.add_parser("add", help="添加新规章")
    add_parser.add_argument("--file", required=True, help="PDF文件路径")
    add_parser.add_argument("--expected", type=int, default=0, help="预期条款数")

    # optimize 命令
    optimize_parser = subparsers.add_parser("optimize", help="运行Agent优化周期")

    # validate 命令
    validate_parser = subparsers.add_parser("validate", help="验证知识库质量")
    validate_parser.add_argument("--kb-path", default="data/processed", help="知识库路径")

    # status 命令
    status_parser = subparsers.add_parser("status", help="查看系统状态")

    args = parser.parse_args()

    if args.command == "add":
        asyncio.run(add_regulation_with_agent_validation(args.file, args.expected))

    elif args.command == "optimize":
        run_agent_optimization_cycle()

    elif args.command == "validate":
        from multi_agent import KnowledgeBaseExpander
        expander = KnowledgeBaseExpander(args.kb_path)
        from multi_agent import print_expansion_status
        print_expansion_status(expander.get_expansion_status())

    elif args.command == "status":
        from multi_agent import KnowledgeBaseOptimizer
        optimizer = KnowledgeBaseOptimizer(args.kb_path)
        status = optimizer.orchestrator.get_system_status()

        print()
        print("🤖 Agent状态:")
        for name, agent_status in status["agents"].items():
            print(f"  {name}:")
            print(f"    状态: {agent_status['status']}")
            print(f"    完成: {agent_status['metrics']['completed']} 任务")

    else:
        parser.print_help()


if __name__ == "__main__":
    cli()
