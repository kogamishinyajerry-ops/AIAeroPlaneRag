#!/usr/bin/env python3
"""
持续深度知识库优化脚本

使用多Agent系统进行持续、深度的知识库优化和评估
"""

import asyncio
import json
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from collections import defaultdict

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from multi_agent.agent_base import AgentOrchestrator, TaskPriority
from multi_agent.enhanced_deep_interpretation_agent import EnhancedDeepInterpretationAgent
from multi_agent.enhanced_cross_mapping_agent import EnhancedCrossMappingAgent
from multi_agent.specialized_agents import (
    TerminologyAgent,
    QualityAgent,
    LinkageAgent,
    QueryAgent,
    DocumentAgent
)

# 导入专家团队
sys.path.insert(0, str(PROJECT_ROOT / "src" / "expert_evaluation"))
from aviation_expert_team import AviationExpertTeam

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ContinuousKnowledgeBaseOptimizer:
    """持续知识库优化器"""

    def __init__(self, kb_path: str, output_dir: str = None):
        self.kb_path = Path(kb_path)
        self.output_dir = Path(output_dir) if output_dir else self.kb_path / "optimization_reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 orchestrator
        self.orchestrator = AgentOrchestrator(str(self.kb_path))

        # 初始化所有 agents
        self._initialize_agents()

        # 初始化专家团队
        self.expert_team = AviationExpertTeam()

        # 优化历史
        self.optimization_history = []
        self.cycle_count = 0

    def _initialize_agents(self):
        """初始化所有Agent"""

        # 核心专业Agent
        self.orchestrator.register_agent(TerminologyAgent(str(self.kb_path)))
        self.orchestrator.register_agent(QualityAgent(str(self.kb_path)))
        self.orchestrator.register_agent(LinkageAgent(str(self.kb_path)))
        self.orchestrator.register_agent(QueryAgent(str(self.kb_path)))
        self.orchestrator.register_agent(DocumentAgent(str(self.kb_path)))

        # 增强版Agent
        self.orchestrator.register_agent(EnhancedDeepInterpretationAgent(str(self.kb_path)))
        self.orchestrator.register_agent(EnhancedCrossMappingAgent(str(self.kb_path)))

        logger.info(f"Initialized {len(self.orchestrator.agents)} agents")

    async def run_single_cycle(self, cycle_num: int) -> Dict[str, Any]:
        """运行单个优化周期"""

        logger.info(f"\n{'='*80}")
        logger.info(f"优化周期 #{cycle_num}")
        logger.info(f"{'='*80}\n")

        cycle_results = {
            "cycle_num": cycle_num,
            "timestamp": datetime.now().isoformat(),
            "phases": {},
            "improvements": []
        }

        # ========================================================================
        # 阶段 1: 知识抽取与增强
        # ========================================================================
        logger.info("[阶段 1/6] 知识抽取与增强")

        interp_agent = self.orchestrator.agents.get("EnhancedDeepInterpretationAgent")

        if interp_agent:
            # 深度解读所有条款
            interp_agent.add_task("deep_interpret_clauses", {
                "max_clauses": 500,
                "doc_filter": ""
            }, TaskPriority.HIGH)

            # 跨条款引用分析
            interp_agent.add_task("find_cross_clause_references", {}, TaskPriority.HIGH)

            # 构建依赖图
            interp_agent.add_task("build_clause_dependency_graph", {}, TaskPriority.MEDIUM)

            # 提取符合性方法
            interp_agent.add_task("extract_compliance_methods", {}, TaskPriority.HIGH)

            # 生成设计评审清单
            interp_agent.add_task("generate_design_review_checklist", {}, TaskPriority.MEDIUM)

        # ========================================================================
        # 阶段 2: 跨机构映射
        # ========================================================================
        logger.info("[阶段 2/6] 跨机构映射分析")

        mapper_agent = self.orchestrator.agents.get("EnhancedCrossMappingAgent")

        if mapper_agent:
            # 构建全面映射
            mapper_agent.add_task("build_comprehensive_mappings", {
                "max_mappings": 1000
            }, TaskPriority.HIGH)

            # 差异分析
            mapper_agent.add_task("analyze_differences", {}, TaskPriority.MEDIUM)

            # 等效性验证
            mapper_agent.add_task("verify_equivalence", {}, TaskPriority.MEDIUM)

            # 术语差异分析
            mapper_agent.add_task("find_terminology_differences", {}, TaskPriority.HIGH)

            # 生成映射摘要报告
            mapper_agent.add_task("generate_mapping_summary_report", {}, TaskPriority.LOW)

            # 推荐阅读顺序
            mapper_agent.add_task("recommend_reading_order", {}, TaskPriority.LOW)

        # ========================================================================
        # 阶段 3: 术语管理
        # ========================================================================
        logger.info("[阶段 3/6] 术语管理")

        term_agent = self.orchestrator.agents.get("TerminologyAgent")

        if term_agent:
            term_agent.add_task("discover_new_terms", {}, TaskPriority.HIGH)
            term_agent.add_task("expand_synonyms", {}, TaskPriority.MEDIUM)
            term_agent.add_task("categorize_terms", {}, TaskPriority.MEDIUM)

        # ========================================================================
        # 阶段 4: 质量评估
        # ========================================================================
        logger.info("[阶段 4/6] 质量评估")

        quality_agent = self.orchestrator.agents.get("QualityAgent")

        if quality_agent:
            quality_agent.add_task("check_completeness", {}, TaskPriority.HIGH)
            quality_agent.add_task("detect_gaps", {}, TaskPriority.HIGH)
            quality_agent.add_task("validate_structure", {}, TaskPriority.MEDIUM)

        # ========================================================================
        # 阶段 5: 关联分析
        # ========================================================================
        logger.info("[阶段 5/6] 关联分析")

        link_agent = self.orchestrator.agents.get("LinkageAgent")

        if link_agent:
            link_agent.add_task("discover_cross_references", {}, TaskPriority.HIGH)
            link_agent.add_task("build_topic_clusters", {}, TaskPriority.MEDIUM)
            link_agent.add_task("find_related_sections", {}, TaskPriority.MEDIUM)

        # ========================================================================
        # 阶段 6: 专家团队评估
        # ========================================================================
        logger.info("[阶段 6/6] 专家团队评估")

        expert_results = await self._run_expert_evaluation()
        cycle_results["expert_evaluation"] = expert_results

        # ========================================================================
        # 执行所有任务
        # ========================================================================
        logger.info("\n执行优化任务...")

        agent_results = await self.orchestrator.run_optimization_cycle()

        # 收集改进
        for agent_name, result in agent_results.items():
            if isinstance(result, dict) and "improvements" in result:
                cycle_results["improvements"].extend(result["improvements"])

        cycle_results["agent_results"] = agent_results

        # 收集详细统计
        cycle_results["statistics"] = self._collect_statistics()

        return cycle_results

    async def _run_expert_evaluation(self) -> Dict[str, Any]:
        """运行专家团队评估"""

        # 使用专家团队的模拟评估方法
        evaluation = self.expert_team.simulate_expert_evaluation()

        expert_results = {
            "experts_evaluated": len(evaluation.get("expert_results", [])),
            "test_scenarios": len(evaluation.get("test_scenarios", [])),
            "overall_scores": evaluation.get("overall_scores", {}),
            "domain_scores": evaluation.get("domain_scores", {}),
            "critical_issues": [],
            "recommendations": evaluation.get("recommendations", [])
        }

        # 提取关键问题
        for result in evaluation.get("expert_results", []):
            if result.get("confidence_score", 1.0) < 0.7:
                expert_results["critical_issues"].append({
                    "expert": result.get("expert_name", "Unknown"),
                    "domain": result.get("domain", "Unknown"),
                    "issue": result.get("overall_assessment", "Low confidence"),
                    "recommendation": result.get("recommendations", ["Review needed"])
                })

        return expert_results

    def _collect_statistics(self) -> Dict[str, Any]:
        """收集知识库统计信息"""

        stats = {
            "documents_processed": 0,
            "total_sections": 0,
            "total_clauses": 0,
            "cross_mappings": 0,
            "domain_coverage": {},
            "term_count": 0,
            "linkage_count": 0
        }

        # 统计文档
        for json_file in self.kb_path.glob("*_structure.json"):
            stats["documents_processed"] += 1

        # 从 agent 收集统计
        interp_agent = self.orchestrator.agents.get("EnhancedDeepInterpretationAgent")
        if interp_agent and hasattr(interp_agent, "interpretations"):
            stats["total_clauses"] = len(interp_agent.interpretations)

            # 领域分布
            domain_count = defaultdict(int)
            for interp in interp_agent.interpretations:
                domain = interp.get("domain", "未分类")
                domain_count[domain] += 1
            stats["domain_coverage"] = dict(domain_count)

        mapper_agent = self.orchestrator.agents.get("EnhancedCrossMappingAgent")
        if mapper_agent and hasattr(mapper_agent, "mappings"):
            for group_mappings in mapper_agent.mappings.values():
                stats["cross_mappings"] += len(group_mappings)

        return stats

    async def run_continuous_optimization(self, cycles: int = 3) -> Dict[str, Any]:
        """运行连续优化周期"""

        logger.info(f"\n{'='*80}")
        logger.info(f"开始持续优化 ({cycles} 个周期)")
        logger.info(f"{'='*80}\n")

        all_results = {
            "optimization_session": {
                "start_time": datetime.now().isoformat(),
                "total_cycles": cycles,
                "cycles": []
            }
        }

        for cycle in range(1, cycles + 1):
            cycle_results = await self.run_single_cycle(cycle)

            # 保存周期结果
            cycle_file = self.output_dir / f"cycle_{cycle}_results.json"
            with open(cycle_file, 'w', encoding='utf-8') as f:
                json.dump(cycle_results, f, ensure_ascii=False, indent=2, default=str)

            all_results["optimization_session"]["cycles"].append(cycle_results)
            self.cycle_count += 1

            # 显示周期摘要
            self._print_cycle_summary(cycle_results)

            # 如果不是最后一个周期，等待一小段时间
            if cycle < cycles:
                await asyncio.sleep(1)

        # 生成最终报告
        final_report = self._generate_final_report(all_results)

        # 保存最终报告
        report_file = self.output_dir / f"optimization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"\n最终报告已保存到: {report_file}")

        return final_report

    def _print_cycle_summary(self, cycle_results: Dict[str, Any]):
        """打印周期摘要"""

        print(f"\n{'─'*80}")
        print(f"周期 #{cycle_results['cycle_num']} 完成")
        print(f"{'─'*80}")

        stats = cycle_results.get("statistics", {})

        if stats:
            print(f"📊 知识库统计:")
            if stats.get("total_clauses"):
                print(f"   - 条款解读: {stats['total_clauses']} 条")
            if stats.get("cross_mappings"):
                print(f"   - 跨机构映射: {stats['cross_mappings']} 个")
            if stats.get("domain_coverage"):
                print(f"   - 领域分布:")
                for domain, count in stats["domain_coverage"].items():
                    if domain and domain != "null":
                        print(f"      * {domain}: {count}")

        expert_eval = cycle_results.get("expert_evaluation", {})
        if expert_eval.get("critical_issues"):
            print(f"\n⚠️  发现 {len(expert_eval['critical_issues'])} 个关键问题")

        improvements = cycle_results.get("improvements", [])
        if improvements:
            print(f"\n✅ 改进项: {len(improvements)}")
            for imp in improvements[:5]:
                print(f"   - {imp}")

    def _generate_final_report(self, all_results: Dict) -> Dict[str, Any]:
        """生成最终报告"""

        session = all_results["optimization_session"]
        cycles = session["cycles"]

        # 聚合统计
        total_clauses = 0
        total_mappings = 0
        total_improvements = 0
        all_critical_issues = []

        for cycle in cycles:
            stats = cycle.get("statistics", {})
            total_clauses = max(total_clauses, stats.get("total_clauses", 0))
            total_mappings = max(total_mappings, stats.get("cross_mappings", 0))
            total_improvements += len(cycle.get("improvements", []))

            expert_eval = cycle.get("expert_evaluation", {})
            all_critical_issues.extend(expert_eval.get("critical_issues", []))

        final_report = {
            "report_type": "Continuous Optimization Report",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "cycles_completed": len(cycles),
                "total_improvements": total_improvements,
                "critical_issues_found": len(all_critical_issues),
                "knowledge_base_health": self._calculate_health_score(all_critical_issues)
            },
            "knowledge_base_stats": {
                "total_clauses_analyzed": total_clauses,
                "cross_agency_mappings": total_mappings,
                "documents_processed": session.get("cycles", [{}])[0].get("statistics", {}).get("documents_processed", 0)
            },
            "expert_evaluation_summary": {
                "total_critical_issues": len(all_critical_issues),
                "issues_by_domain": self._group_issues_by_domain(all_critical_issues),
                "top_recommendations": self._get_top_recommendations(all_critical_issues)
            },
            "detailed_cycles": cycles
        }

        return final_report

    def _calculate_health_score(self, issues: List[Dict]) -> str:
        """计算知识库健康评分"""

        if len(issues) == 0:
            return "优秀"
        elif len(issues) < 5:
            return "良好"
        elif len(issues) < 15:
            return "中等"
        else:
            return "需要改进"

    def _group_issues_by_domain(self, issues: List[Dict]) -> Dict[str, int]:
        """按领域分组问题"""

        domain_count = defaultdict(int)
        for issue in issues:
            domain = issue.get("domain", "未知")
            domain_count[domain] += 1
        return dict(domain_count)

    def _get_top_recommendations(self, issues: List[Dict]) -> List[str]:
        """获取主要建议"""

        recommendations = []
        seen = set()

        for issue in issues[:10]:
            for rec in issue.get("recommendation", []):
                if isinstance(rec, list):
                    for r in rec:
                        if r not in seen:
                            recommendations.append(f"[{issue.get('domain', '未知')}] {r}")
                            seen.add(r)
                elif rec not in seen:
                    recommendations.append(f"[{issue.get('domain', '未知')}] {rec}")
                    seen.add(rec)

        return recommendations[:10]


async def main():
    """主程序"""

    kb_path = "data/processed"
    output_dir = "data/processed/optimization_reports"

    optimizer = ContinuousKnowledgeBaseOptimizer(kb_path, output_dir)

    # 显示初始化信息
    print(f"\n{'='*80}")
    title = " "*20 + "AIAeroPlaneRag 持续深度优化系统"
    print(title)
    print(f"{'='*80}")
    print(f"\n已初始化 {len(optimizer.orchestrator.agents)} 个 Agent:")
    for name in optimizer.orchestrator.agents.keys():
        print(f"  - {name}")

    print(f"\n专家团队: {len(optimizer.expert_team.experts)} 位专家")
    for expert in optimizer.expert_team.experts:
        print(f"  - {expert.name} ({expert.title}) - {', '.join(expert.expertise[:2])}")

    # 运行持续优化
    results = await optimizer.run_continuous_optimization(cycles=3)

    # 显示最终摘要
    print(f"\n{'='*80}")
    print(f"优化完成！")
    print(f"{'='*80}")
    print(f"\n总改进项: {results['summary']['total_improvements']}")
    print(f"知识库健康: {results['summary']['knowledge_base_health']}")
    print(f"发现问题: {results['summary']['critical_issues_found']}")

    print(f"\n知识库统计:")
    print(f"  - 条款分析: {results['knowledge_base_stats']['total_clauses_analyzed']}")
    print(f"  - 跨机构映射: {results['knowledge_base_stats']['cross_agency_mappings']}")

    if results['expert_evaluation_summary']['top_recommendations']:
        print(f"\n主要建议:")
        for rec in results['expert_evaluation_summary']['top_recommendations'][:5]:
            print(f"  - {rec}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
