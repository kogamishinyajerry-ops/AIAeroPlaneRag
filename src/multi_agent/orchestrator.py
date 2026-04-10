"""
多Agent知识库优化系统 - 主程序

演示如何使用多个专业Agent协同工作，持续优化知识库
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

from .agent_base import AgentOrchestrator, TaskPriority
from .specialized_agents import (
    TerminologyAgent,
    QualityAgent,
    LinkageAgent,
    QueryAgent,
    DocumentAgent
)
from .parser_fixer_agent import ParserFixerAgent
from .cross_mapping_agent import CrossMappingAgent
from .deep_interpretation_agent import DeepInterpretationAgent
from .enhanced_cross_mapping_agent import EnhancedCrossMappingAgent
from .enhanced_deep_interpretation_agent import EnhancedDeepInterpretationAgent
from .usability_enhancer_agent import UsabilityEnhancerAgent
from .fact_verification_agent import FactVerificationAgent
from .knowledge_linker_agent import KnowledgeLinkerAgent
from .knowledge_graph_agent import KnowledgeGraphAgent
from .enhanced_terminology_agent import EnhancedTerminologyAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class KnowledgeBaseOptimizer:
    """
    知识库优化器

    协调多个Agent执行优化任务
    """

    def __init__(self, knowledge_base_path: str):
        self.kb_path = Path(knowledge_base_path)
        self.orchestrator = AgentOrchestrator(str(self.kb_path))
        self._initialize_agents()

    def _initialize_agents(self):
        """初始化所有Agent"""
        # 注册核心专业Agent
        self.orchestrator.register_agent(
            TerminologyAgent(str(self.kb_path))
        )
        self.orchestrator.register_agent(
            QualityAgent(str(self.kb_path))
        )
        self.orchestrator.register_agent(
            LinkageAgent(str(self.kb_path))
        )
        self.orchestrator.register_agent(
            QueryAgent(str(self.kb_path))
        )
        self.orchestrator.register_agent(
            DocumentAgent(str(self.kb_path))
        )

        # 注册新增Agent
        self.orchestrator.register_agent(
            ParserFixerAgent(str(self.kb_path))
        )
        self.orchestrator.register_agent(
            CrossMappingAgent(str(self.kb_path))
        )
        self.orchestrator.register_agent(
            DeepInterpretationAgent(str(self.kb_path))
        )

        # 注册增强版Agent（新增）
        try:
            self.orchestrator.register_agent(
                EnhancedCrossMappingAgent(str(self.kb_path))
            )
            logger.info("EnhancedCrossMappingAgent registered")
        except Exception as e:
            logger.warning(f"Could not register EnhancedCrossMappingAgent: {e}")

        try:
            self.orchestrator.register_agent(
                EnhancedDeepInterpretationAgent(str(self.kb_path))
            )
            logger.info("EnhancedDeepInterpretationAgent registered")
        except Exception as e:
            logger.warning(f"Could not register EnhancedDeepInterpretationAgent: {e}")

        # 注册性能优化Agent（新增）
        try:
            self.orchestrator.register_agent(
                UsabilityEnhancerAgent(str(self.kb_path))
            )
            logger.info("UsabilityEnhancerAgent registered")
        except Exception as e:
            logger.warning(f"Could not register UsabilityEnhancerAgent: {e}")

        try:
            self.orchestrator.register_agent(
                FactVerificationAgent(str(self.kb_path))
            )
            logger.info("FactVerificationAgent registered")
        except Exception as e:
            logger.warning(f"Could not register FactVerificationAgent: {e}")

        try:
            self.orchestrator.register_agent(
                KnowledgeLinkerAgent(str(self.kb_path))
            )
            logger.info("KnowledgeLinkerAgent registered")
        except Exception as e:
            logger.warning(f"Could not register KnowledgeLinkerAgent: {e}")

        # 注册知识图谱和术语增强Agent（新增）
        try:
            self.orchestrator.register_agent(
                KnowledgeGraphAgent(str(self.kb_path))
            )
            logger.info("KnowledgeGraphAgent registered")
        except Exception as e:
            logger.warning(f"Could not register KnowledgeGraphAgent: {e}")

        try:
            self.orchestrator.register_agent(
                EnhancedTerminologyAgent(str(self.kb_path))
            )
            logger.info("EnhancedTerminologyAgent registered")
        except Exception as e:
            logger.warning(f"Could not register EnhancedTerminologyAgent: {e}")

        logger.info(f"Initialized {len(self.orchestrator.agents)} agents")

    async def run_full_optimization(self) -> Dict[str, Any]:
        """运行完整优化周期"""
        logger.info("="*70)
        logger.info("Starting Full Knowledge Base Optimization")
        logger.info("="*70)

        # 0. 解析问题修复
        logger.info("\n[0/10] Parser Fixing")
        fixer_agent = self.orchestrator.agents.get("ParserFixerAgent")
        if fixer_agent:
            fixer_agent.add_task("detect_issues", priority=TaskPriority.CRITICAL)
            fixer_agent.add_task("fix_missing_fields", priority=TaskPriority.CRITICAL)

        # 1. 文档检测
        logger.info("\n[1/10] Document Detection")
        doc_agent = self.orchestrator.agents.get("DocumentAgent")
        if doc_agent:
            doc_agent.add_task("detect_new_documents", priority=TaskPriority.HIGH)

        # 2. 质量检查
        logger.info("\n[2/10] Quality Assessment")
        quality_agent = self.orchestrator.agents.get("QualityAgent")
        if quality_agent:
            quality_agent.add_task("check_completeness", priority=TaskPriority.HIGH)
            quality_agent.add_task("detect_gaps", priority=TaskPriority.MEDIUM)

        # 3. 术语管理
        logger.info("\n[3/10] Terminology Management")
        term_agent = self.orchestrator.agents.get("TerminologyAgent")
        if term_agent:
            term_agent.add_task("discover_new_terms", priority=TaskPriority.MEDIUM)
            term_agent.add_task("validate_terms", {"terms": ["测试", "OEI", "防火墙"]}, priority=TaskPriority.LOW)

        # 4. 关联分析
        logger.info("\n[4/10] Linkage Analysis")
        link_agent = self.orchestrator.agents.get("LinkageAgent")
        if link_agent:
            link_agent.add_task("discover_cross_references", priority=TaskPriority.HIGH)
            link_agent.add_task("build_topic_clusters", priority=TaskPriority.MEDIUM)

        # 5. 跨机构映射 (基础版)
        logger.info("\n[5/10] Cross-Agency Mapping (Basic)")
        mapper_agent = self.orchestrator.agents.get("CrossMappingAgent")
        if mapper_agent:
            mapper_agent.add_task("build_section_mappings", priority=TaskPriority.HIGH)

        # 6. 增强跨机构映射
        logger.info("\n[6/10] Cross-Agency Mapping (Enhanced)")
        enh_mapper_agent = self.orchestrator.agents.get("EnhancedCrossMappingAgent")
        if enh_mapper_agent:
            enh_mapper_agent.add_task("build_comprehensive_mappings", {"max_mappings": 500}, priority=TaskPriority.HIGH)
            enh_mapper_agent.add_task("analyze_differences", priority=TaskPriority.MEDIUM)
            enh_mapper_agent.add_task("verify_equivalence", priority=TaskPriority.MEDIUM)
            enh_mapper_agent.add_task("find_terminology_differences", priority=TaskPriority.MEDIUM)
            enh_mapper_agent.add_task("generate_mapping_summary_report", priority=TaskPriority.LOW)

        # 7. 深度解读 (基础版)
        logger.info("\n[7/10] Deep Interpretation (Basic)")
        interp_agent = self.orchestrator.agents.get("DeepInterpretationAgent")
        if interp_agent:
            interp_agent.add_task("interpret_clauses", {"max_clauses": 100}, priority=TaskPriority.HIGH)

        # 8. 增强深度解读
        logger.info("\n[8/10] Deep Interpretation (Enhanced)")
        enh_interp_agent = self.orchestrator.agents.get("EnhancedDeepInterpretationAgent")
        if enh_interp_agent:
            enh_interp_agent.add_task("deep_interpret_clauses", {"max_clauses": 200, "doc_filter": "CCAR-33"}, priority=TaskPriority.HIGH)
            enh_interp_agent.add_task("find_cross_clause_references", priority=TaskPriority.HIGH)
            enh_interp_agent.add_task("build_clause_dependency_graph", priority=TaskPriority.MEDIUM)
            enh_interp_agent.add_task("extract_compliance_methods", priority=TaskPriority.MEDIUM)
            enh_interp_agent.add_task("generate_design_review_checklist", priority=TaskPriority.LOW)
            enh_interp_agent.add_task("export_detailed_interpretations", priority=TaskPriority.LOW)

        # 9. 查询优化
        logger.info("\n[9/13] Query Analysis")
        query_agent = self.orchestrator.agents.get("QueryAgent")
        if query_agent:
            query_agent.add_task("analyze_patterns", priority=TaskPriority.MEDIUM)
            query_agent.add_task("detect_low_score_queries", {"threshold": 50}, priority=TaskPriority.HIGH)

        # 10. 可用性增强
        logger.info("\n[10/13] Usability Enhancement")
        usability_agent = self.orchestrator.agents.get("UsabilityEnhancerAgent")
        if usability_agent:
            usability_agent.add_task("enrich_metadata", {}, TaskPriority.HIGH)
            usability_agent.add_task("expand_citations", {"min_length": 500}, TaskPriority.HIGH)
            usability_agent.add_task("generate_visualizations", {}, TaskPriority.MEDIUM)

        # 11. 事实验证
        logger.info("\n[11/13] Fact Verification")
        fact_agent = self.orchestrator.agents.get("FactVerificationAgent")
        if fact_agent:
            fact_agent.add_task("verify_citations", {}, TaskPriority.HIGH)
            fact_agent.add_task("mark_uncertainty", {}, TaskPriority.HIGH)
            fact_agent.add_task("fact_check", {}, TaskPriority.HIGH)
            fact_agent.add_task("generate_report", {}, TaskPriority.MEDIUM)

        # 12. 知识关联
        logger.info("\n[12/15] Knowledge Linking")
        linker_agent = self.orchestrator.agents.get("KnowledgeLinkerAgent")
        if linker_agent:
            linker_agent.add_task("build_cross_links", {}, TaskPriority.HIGH)
            linker_agent.add_task("expand_terminology", {}, TaskPriority.HIGH)
            linker_agent.add_task("optimize_relevance", {}, TaskPriority.HIGH)
            linker_agent.add_task("create_clusters", {}, TaskPriority.MEDIUM)

        # 13. 知识图谱构建
        logger.info("\n[13/15] Knowledge Graph Building")
        graph_agent = self.orchestrator.agents.get("KnowledgeGraphAgent")
        if graph_agent:
            graph_agent.add_task("build_graph", {"max_docs": 15}, TaskPriority.HIGH)
            graph_agent.add_task("analyze_clusters", {}, TaskPriority.MEDIUM)
            graph_agent.add_task("graph_insights", {}, TaskPriority.MEDIUM)

        # 14. 增强术语提取
        logger.info("\n[14/15] Enhanced Terminology Extraction")
        term_agent = self.orchestrator.agents.get("EnhancedTerminologyAgent")
        if term_agent:
            term_agent.add_task("extract_comprehensive_terms", {"min_freq": 2}, TaskPriority.HIGH)
            term_agent.add_task("build_semantic_network", {}, TaskPriority.HIGH)
            term_agent.add_task("detect_abbreviations", {}, TaskPriority.MEDIUM)
            term_agent.add_task("generate_domain_ontology", {}, TaskPriority.MEDIUM)

        # 15. 导出结果
        logger.info("\n[15/15] Export Results")

        # 执行所有任务
        results = await self.orchestrator.run_optimization_cycle()

        return results

    async def run_continuous_optimization(self, cycles: int = 3, interval: int = 10):
        """连续运行多个优化周期"""
        logger.info(f"Starting continuous optimization ({cycles} cycles)")

        for i in range(cycles):
            logger.info(f"\n{'='*70}")
            logger.info(f"Cycle {i+1}/{cycles}")
            logger.info(f"{'='*70}")

            await self.run_full_optimization()

            if i < cycles - 1:
                logger.info(f"Waiting {interval}s before next cycle...")
                await asyncio.sleep(interval)

    def get_optimization_report(self) -> str:
        """获取优化报告"""
        return self.orchestrator.generate_optimization_report()

    def save_results(self, results: Dict, output_path: str = None):
        """保存优化结果"""
        if output_path is None:
            output_path = self.kb_path / "../reports/optimization_results.json"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Results saved to: {output_path}")


async def main():
    """主程序入口"""
    # 知识库路径
    kb_path = "/Users/Zhuanz/AIAeroPlaneRag/data/processed"

    # 创建优化器
    optimizer = KnowledgeBaseOptimizer(kb_path)

    # 显示系统状态
    print("\n" + "="*70)
    print("知识库优化系统 - Agent状态")
    print("="*70)

    status = optimizer.orchestrator.get_system_status()
    for agent_name, agent_status in status["agents"].items():
        print(f"\n🤖 {agent_name}:")
        print(f"   能力: {', '.join(agent_status['capabilities'])}")

    # 运行优化
    print("\n" + "="*70)
    print("开始优化周期...")
    print("="*70)

    results = await optimizer.run_full_optimization()

    # 保存结果
    optimizer.save_results(results)

    # 显示报告
    print("\n" + optimizer.get_optimization_report())

    return results


def run_optimization_cli():
    """CLI入口"""
    import argparse

    parser = argparse.ArgumentParser(description="知识库多Agent优化系统")
    parser.add_argument("--cycles", type=int, default=1, help="优化周期数")
    parser.add_argument("--continuous", action="store_true", help="连续运行模式")
    parser.add_argument("--kb-path", default="/Users/Zhuanz/AIAeroPlaneRag/data/processed",
                        help="知识库路径")

    args = parser.parse_args()

    async def run():
        optimizer = KnowledgeBaseOptimizer(args.kb_path)

        if args.continuous:
            await optimizer.run_continuous_optimization(cycles=args.cycles, interval=30)
        else:
            for _ in range(args.cycles):
                await optimizer.run_full_optimization()

        print("\n" + optimizer.get_optimization_report())

    asyncio.run(run())


if __name__ == "__main__":
    # 运行单次优化
    asyncio.run(main())
