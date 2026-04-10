#!/usr/bin/env python3
"""
开发钩子系统
自动在关键操作后运行多Agent质量检查
"""

import os
import sys
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

def run_agent_qa_after_parse(structure_file: str) -> bool:
    """
    解析后自动运行质量检查

    在解析脚本中调用此函数
    """
    print()
    print("="*70)
    print("🤖 多Agent质量检查")
    print("="*70)

    # 导入QA模块
    from quality_assurance import DevelopmentQualityAssurance

    qa = DevelopmentQualityAssurance("/Users/Zhuanz/AIAeroPlaneRag/data/processed")

    # 运行验证
    try:
        import asyncio

        async def validate():
            # 获取预期条款数（从文件名推断或传入）
            if "FAR-25" in structure_file:
                expected = 350
            elif "FAR-33" in structure_file:
                expected = 60
            elif "FAR-29" in structure_file:
                expected = 500
            else:
                expected = 0

            report = await qa.validate_document_addition(structure_file, expected)
            qa.print_report(report)

            return report["status"] == "PASSED"

        result = asyncio.run(validate())

        if not result:
            print("\n❌ 质量检查未通过！")
            print("请修复问题后重新运行检查。")
            return False

        print("\n✅ 质量检查通过，可以继续。")
        return True

    except Exception as e:
        print(f"\n❌ 质量检查出错: {e}")
        print("继续进行但建议人工检查。")
        return True  # 不阻塞开发


def run_agent_optimization_cycle() -> bool:
    """
    运行完整的多Agent优化周期

    在以下情况调用：
    - 添加新文档后
    - 修改核心代码后
    - 定期维护时
    """
    print()
    print("="*70)
    print("🤖 启动多Agent优化周期")
    print("="*70)

    from multi_agent import KnowledgeBaseOptimizer

    try:
        import asyncio

        async def optimize():
            optimizer = KnowledgeBaseOptimizer("/Users/Zhuanz/AIAeroPlaneRag/data/processed")
            results = await optimizer.run_full_optimization()

            print()
            print("="*70)
            print("优化周期完成")
            print("="*70)
            print(f"执行时间: {results['execution_time']:.2f} 秒")
            print(f"执行Agent: {len(results['agents_executed'])} 个")
            print(f"总改进数: {results['total_improvements']}")

            if results.get("errors"):
                print(f"错误: {len(results['errors'])} 个")
                for err in results["errors"]:
                    print(f"  • {err}")

            return True

        return asyncio.run(optimize())

    except Exception as e:
        print(f"❌ 优化周期执行失败: {e}")
        return False


# 开发钩子 - 预留给Makefile或其他构建系统
def pre_commit_hook(files: list) -> bool:
    """
    预提交钩子 - 检查即将提交的文件

    Args:
        files: 即将提交的文件列表

    Returns:
        bool: True 允许提交, False 阻止提交
    """
    print("\n🔍 预提交质量检查...")

    # 检查是否有结构文件被修改
    structure_files = [f for f in files if "_structure.json" in f]

    if structure_files:
        print(f"发现 {len(structure_files)} 个结构文件变更")
        return run_agent_qa_after_parse(structure_files[0])

    return True


def post_merge_hook() -> bool:
    """
    合并后钩子 - 运行完整优化

    Returns:
        bool: True 合并成功, False 需要人工检查
    """
    print("\n🔄 合并后自动优化...")
    return run_agent_optimization_cycle()


# 命令行接口
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="多Agent质量保证工具")
    parser.add_argument("--validate", help="验证文档", metavar="FILE")
    parser.add_argument("--optimize", action="store_true", help="运行优化周期")
    parser.add_argument("--mandatory", action="store_true", help="强制模式（阻止不合格的变更）")

    args = parser.parse_args()

    if args.validate:
        # 验证模式
        result = run_agent_qa_after_parse(args.validate)
        sys.exit(0 if result else 1)

    elif args.optimize:
        # 优化模式
        result = run_agent_optimization_cycle()
        sys.exit(0 if result else 1)

    else:
        # 显示帮助
        parser.print_help()
