#!/usr/bin/env python3
"""
深度知识库分析脚本

使用多Agent系统对知识库进行深度挖掘和分析
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from multi_agent.agent_base import AgentOrchestrator, TaskPriority
from multi_agent.enhanced_deep_interpretation_agent import EnhancedDeepInterpretationAgent
from multi_agent.enhanced_cross_mapping_agent import EnhancedCrossMappingAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_deep_analysis(kb_path: str, output_path: str = None):
    """运行深度分析"""

    kb_path = Path(kb_path)
    if output_path is None:
        output_path = kb_path / "deep_analysis_report.json"

    print("\n" + "="*80)
    print(" "*20 + "AIAeroPlaneRag 深度知识库分析")
    print("="*80)

    # 初始化 orchestrator
    orchestrator = AgentOrchestrator(str(kb_path))

    # 注册增强版 Agent
    interp_agent = EnhancedDeepInterpretationAgent(str(kb_path))
    mapper_agent = EnhancedCrossMappingAgent(str(kb_path))

    orchestrator.register_agent(interp_agent)
    orchestrator.register_agent(mapper_agent)

    print(f"\n已初始化 {len(orchestrator.agents)} 个 Agent:")
    for name, agent in orchestrator.agents.items():
        print(f"  - {name}")
        print(f"    能力: {', '.join(agent.get_capabilities()[:3])}...")

    # ========================================================================
    # 1. 深度解读分析
    # ========================================================================
    print("\n" + "-"*80)
    print("[1/3] 深度条款解读分析...")
    print("-"*80)

    interp_tasks = [
        ("deep_interpret_clauses", {"max_clauses": 300, "doc_filter": ""}, TaskPriority.HIGH),
        ("find_cross_clause_references", {}, TaskPriority.HIGH),
        ("build_clause_dependency_graph", {}, TaskPriority.MEDIUM),
        ("extract_compliance_methods", {}, TaskPriority.HIGH),
        ("generate_design_review_checklist", {}, TaskPriority.MEDIUM),
    ]

    for action, params, priority in interp_tasks:
        interp_agent.add_task(action, params, priority=priority)

    # ========================================================================
    # 2. 跨机构映射分析
    # ========================================================================
    print("\n" + "-"*80)
    print("[2/3] 跨机构映射分析...")
    print("-"*80)

    mapper_tasks = [
        ("build_comprehensive_mappings", {"max_mappings": 500}, TaskPriority.HIGH),
        ("analyze_differences", {}, TaskPriority.MEDIUM),
        ("verify_equivalence", {}, TaskPriority.MEDIUM),
        ("find_terminology_differences", {}, TaskPriority.MEDIUM),
        ("generate_mapping_summary_report", {}, TaskPriority.LOW),
        ("recommend_reading_order", {}, TaskPriority.LOW),
    ]

    for action, params, priority in mapper_tasks:
        mapper_agent.add_task(action, params, priority=priority)

    # ========================================================================
    # 3. 执行分析
    # ========================================================================
    print("\n" + "-"*80)
    print("[3/3] 执行所有分析任务...")
    print("-"*80)

    results = await orchestrator.run_optimization_cycle()

    # ========================================================================
    # 4. 生成报告
    # ========================================================================
    print("\n" + "="*80)
    print("分析完成！生成报告...")
    print("="*80)

    # 收集详细结果
    detailed_report = {
        "timestamp": datetime.now().isoformat(),
        "kb_path": str(kb_path),
        "analysis_summary": {},
        "deep_interpretation": {},
        "cross_mapping": {},
        "recommendations": []
    }

    # 从 agent 获取详细结果
    if hasattr(interp_agent, 'interpretations') and interp_agent.interpretations:
        detailed_report["deep_interpretation"]["total_clauses"] = len(interp_agent.interpretations)

        # 按领域统计
        by_domain = {}
        for interp in interp_agent.interpretations:
            domain = interp.get("domain", "未分类")
            by_domain[domain] = by_domain.get(domain, 0) + 1
        detailed_report["deep_interpretation"]["by_domain"] = by_domain

    if hasattr(mapper_agent, 'mappings') and mapper_agent.mappings:
        total_maps = sum(len(m) for m in mapper_agent.mappings.values())
        detailed_report["cross_mapping"]["total_mappings"] = total_maps
        detailed_report["cross_mapping"]["groups"] = list(mapper_agent.mappings.keys())

    # 保存报告
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(detailed_report, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n报告已保存到: {output_path}")

    # ========================================================================
    # 5. 打印摘要
    # ========================================================================
    print("\n" + "="*80)
    print("分析摘要")
    print("="*80)

    if "deep_interpretation" in detailed_report:
        di = detailed_report["deep_interpretation"]
        if "total_clauses" in di:
            print(f"\n深度解读:")
            print(f"  - 分析条款数: {di['total_clauses']}")
            if "by_domain" in di:
                print(f"  - 领域分布:")
                for domain, count in di["by_domain"].items():
                    print(f"      * {domain}: {count}")

    if "cross_mapping" in detailed_report:
        cm = detailed_report["cross_mapping"]
        if "total_mappings" in cm:
            print(f"\n跨机构映射:")
            print(f"  - 映射数量: {cm['total_mappings']}")
            if "groups" in cm:
                print(f"  - 规章组: {', '.join(cm['groups'])}")

    print("\n" + "="*80)

    return detailed_report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="深度知识库分析")
    parser.add_argument("--kb-path", default="data/processed", help="知识库路径")
    parser.add_argument("--output", help="输出报告路径")

    args = parser.parse_args()

    asyncio.run(run_deep_analysis(args.kb_path, args.output))
