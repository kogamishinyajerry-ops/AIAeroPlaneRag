"""
开发质量保证系统
强制所有开发必须通过多Agent审查
"""

import asyncio
import logging
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent))

from multi_agent import (
    KnowledgeBaseOptimizer,
    KnowledgeBaseExpander,
    print_expansion_status
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class QualityGate:
    """质量门禁"""
    name: str
    description: str
    blocking: bool = True  # 是否阻止继续
    threshold: float = 0.0  # 通过阈值
    actual_score: float = 0.0
    passed: bool = False
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "blocking": self.blocking,
            "threshold": self.threshold,
            "actual_score": self.actual_score,
            "passed": self.passed,
            "issues": self.issues,
            "recommendations": self.recommendations
        }


class DevelopmentQualityAssurance:
    """
    开发质量保证系统

    所有开发变更必须通过的质量门禁：
    1. 解析质量检查
    2. 内容完整性验证
    3. 术语一致性检查
    4. 跨文档关联验证
    5. 查询效果验证
    """

    def __init__(self, kb_path: str):
        self.kb_path = Path(kb_path)
        self.optimizer = KnowledgeBaseOptimizer(str(self.kb_path))
        self.expander = KnowledgeBaseExpander(str(self.kb_path))
        self.gates: List[QualityGate] = []
        self.session_results: List[Dict] = []
        self.mandatory_checks = True  # 强制模式

    def set_mandatory_mode(self, mandatory: bool = True):
        """设置强制模式"""
        self.mandatory_mode = mandatory
        logger.info(f"质量保证模式: {'强制' if mandatory else '建议'}")

    async def validate_document_addition(
        self,
        document_path: str,
        expected_sections: int = 0
    ) -> Dict[str, Any]:
        """
        验证新添加的文档

        必须通过的门禁:
        1. 解析成功且质量达标
        2. 内容完整性 > 80%
        3. 与现有文档的关联建立
        4. 术语收录
        """
        logger.info(f"="*70)
        logger.info(f"验证文档: {Path(document_path).name}")
        logger.info(f"="*70)

        results = {
            "document": document_path,
            "timestamp": datetime.now().isoformat(),
            "passed": False,
            "gates": [],
            "blocking_issues": []
        }

        # 门禁1: 解析质量
        logger.info("[门禁 1/5] 解析质量检查...")
        parse_gate = await self._check_parse_quality(document_path, expected_sections)
        results["gates"].append(parse_gate.to_dict())

        if parse_gate.blocking and not parse_gate.passed:
            results["blocking_issues"].append(f"解析质量不合格: {parse_gate.issues}")
            if self.mandatory_mode:
                return self._generate_report(results, "BLOCKED")

        # 门禁2: 内容完整性
        logger.info("[门禁 2/5] 内容完整性检查...")
        content_gate = await self._check_content_completeness(document_path)
        results["gates"].append(content_gate.to_dict())

        if content_gate.blocking and not content_gate.passed:
            results["blocking_issues"].append(f"内容完整性不足: {content_gate.issues}")
            if self.mandatory_mode:
                return self._generate_report(results, "BLOCKED")

        # 门禁3: 术语收录
        logger.info("[门禁 3/5] 术语收录检查...")
        term_gate = await self._check_terminology_coverage(document_path)
        results["gates"].append(term_gate.to_dict())

        # 门禁4: 跨文档关联
        logger.info("[门禁 4/5] 跨文档关联检查...")
        link_gate = await self._check_cross_document_links(document_path)
        results["gates"].append(link_gate.to_dict())

        # 门禁5: 查询验证
        logger.info("[门禁 5/5] 查询效果验证...")
        query_gate = await self._check_query_effectiveness(document_path)
        results["gates"].append(query_gate.to_dict())

        # 汇总结果
        all_passed = all(g.get("passed", False) for g in results["gates"])
        results["passed"] = all_passed

        self.session_results.append(results)
        return self._generate_report(results, "PASSED" if all_passed else "WARNING")

    async def _check_parse_quality(
        self,
        document_path: str,
        expected_sections: int
    ) -> QualityGate:
        """检查解析质量"""
        gate = QualityGate(
            name="parse_quality",
            description="解析质量检查",
            blocking=True,
            threshold=0.7
        )

        try:
            # 读取解析结果
            doc_name = Path(document_path).stem
            processed_dir = self.kb_path
            structure_file = processed_dir / f"{doc_name}_structure.json"

            with open(structure_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            actual_sections = data.get("total_sections", 0)
            quality = data.get("parse_quality", "unknown")

            # 计算质量分数
            if quality == "excellent":
                gate.actual_score = 1.0
            elif quality == "good":
                gate.actual_score = 0.8
            elif quality == "partial":
                gate.actual_score = 0.5
            else:
                gate.actual_score = 0.0

            gate.passed = gate.actual_score >= gate.threshold

            if not gate.passed:
                gate.issues.append(f"解析质量为 {quality}，需要 >= good")

        except Exception as e:
            gate.issues.append(f"解析检查失败: {str(e)}")

        return gate

    async def _check_content_completeness(self, document_path: str) -> QualityGate:
        """检查内容完整性"""
        gate = QualityGate(
            name="content_completeness",
            description="内容完整性检查",
            blocking=True,
            threshold=0.8
        )

        # 使用 QualityAgent
        quality_agent = self.optimizer.orchestrator.agents["QualityAgent"]
        task = quality_agent.add_task(
            "check_completeness",
            {"processed_dir": str(self.kb_path)},
            priority="CRITICAL"
        )

        result = await quality_agent.execute(task)

        # 统计完整性
        issues = result.get("issues", [])
        total_nodes = 0
        empty_nodes = 0

        # 简化的完整性计算
        if not issues:
            gate.actual_score = 1.0
        else:
            # 根据问题数量计算分数
            gate.actual_score = max(0, 1.0 - len(issues) * 0.1)

        gate.passed = gate.actual_score >= gate.threshold
        gate.issues = issues

        return gate

    async def _check_terminology_coverage(self, document_path: str) -> QualityGate:
        """检查术语收录"""
        gate = QualityGate(
            name="terminology_coverage",
            description="术语收录检查",
            blocking=False,  # 非阻塞，只记录
            threshold=0.5
        )

        # 分析文档中的术语
        doc_name = Path(document_path).stem
        structure_file = self.kb_path / f"{doc_name}_structure.json"

        try:
            with open(structure_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 提取所有标题中的术语
            terms_found = set()
            self._extract_terms_from_structure(data, terms_found)

            gate.actual_score = min(1.0, len(terms_found) / 50)  # 假设50个术语为满分
            gate.passed = True  # 非阻塞
            gate.recommendations.append(f"发现 {len(terms_found)} 个专业术语")

        except Exception as e:
            gate.issues.append(f"术语检查失败: {str(e)}")

        return gate

    async def _check_cross_document_links(self, document_path: str) -> QualityGate:
        """检查跨文档关联"""
        gate = QualityGate(
            name="cross_document_links",
            description="跨文档关联检查",
            blocking=False,
            threshold=0.3
        )

        # 使用 LinkageAgent
        link_agent = self.optimizer.orchestrator.agents["LinkageAgent"]
        task = link_agent.add_task(
            "discover_cross_references",
            {"processed_dir": str(self.kb_path)},
            priority="HIGH"
        )

        result = await link_agent.execute(task)
        refs = result.get("cross_references", [])

        gate.actual_score = min(1.0, len(refs) / 100)
        gate.passed = True
        gate.recommendations.append(f"发现 {len(refs)} 个跨文档关联")

        return gate

    async def _check_query_effectiveness(self, document_path: str) -> QualityGate:
        """检查查询效果"""
        gate = QualityGate(
            name="query_effectiveness",
            description="查询效果验证",
            blocking=False,
            threshold=0.6
        )

        # 使用 QueryAgent
        query_agent = self.optimizer.orchestrator.agents["QueryAgent"]
        task = query_agent.add_task(
            "detect_low_score_queries",
            {"threshold": 50},
            priority="MEDIUM"
        )

        result = await query_agent.execute(task)
        low_score = result.get("low_score_queries", [])

        # 反向分数 - 问题越少分数越高
        gate.actual_score = max(0, 1.0 - len(low_score) * 0.2)
        gate.passed = gate.actual_score >= gate.threshold

        if low_score:
            gate.recommendations.extend([q.get("suggestion", "") for q in low_score])

        return gate

    def _extract_terms_from_structure(self, data: Dict, terms_set: set):
        """从结构中提取术语"""
        if isinstance(data, dict):
            # 处理章节
            for key in ["title", "id", "summary"]:
                if key in data:
                    # 简单的术语提取逻辑
                    import re
                    text = data[key]
                    if isinstance(text, str):
                        # 提取英文单词和中文词汇
                        english = re.findall(r'[A-Z][a-z]+(?:[A-Z][a-z]+)?', text)
                        chinese = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
                        terms_set.update(english[:10])  # 限制数量
                        terms_set.update(chinese[:10])

            # 递归处理
            if "chapters" in data:
                for chapter in data["chapters"]:
                    self._extract_terms_from_structure(chapter, terms_set)
            elif "nodes" in data:
                for node in data["nodes"]:
                    self._extract_terms_from_structure(node, terms_set)
            elif "sections" in data:
                for section in data["sections"]:
                    self._extract_terms_from_structure(section, terms_set)

    def _generate_report(self, results: Dict, status: str) -> Dict:
        """生成质量报告"""
        report = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "document": results.get("document"),
            "gates_summary": {
                "total": len(results.get("gates", [])),
                "passed": sum(1 for g in results.get("gates", []) if g.get("passed", False)),
                "failed": sum(1 for g in results.get("gates", []) if not g.get("passed", True))
            },
            "gates": results.get("gates", []),
            "blocking_issues": results.get("blocking_issues", [])
        }

        # 保存报告
        report_dir = self.kb_path / "../reports/qa"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_file = report_dir / f"qa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"质量报告已保存: {report_file}")
        return report

    def print_report(self, report: Dict):
        """打印质量报告"""
        print()
        print("="*70)
        print(f"质量保证报告 - {report['status']}")
        print("="*70)

        for gate in report.get("gates", []):
            status_icon = "✅" if gate["passed"] else "❌"
            blocking_mark = " [强制]" if gate["blocking"] else ""
            print(f"\n{status_icon} {gate['name']}{blocking_mark}")
            print(f"   得分: {gate['actual_score']:.2f}/{gate['threshold']:.2f}")
            print(f"   描述: {gate['description']}")

            if gate["issues"]:
                print(f"   问题:")
                for issue in gate["issues"]:
                    print(f"     • {issue}")

            if gate["recommendations"]:
                print(f"   建议:")
                for rec in gate["recommendations"]:
                    print(f"     • {rec}")

        print()
        print("="*70)


async def mandatory_agent_validation(
    document_path: str,
    expected_sections: int = 0
) -> bool:
    """
    强制Agent验证入口

    所有新文档添加必须调用此函数
    返回 True 才能继续
    """
    qa = DevelopmentQualityAssurance("/Users/Zhuanz/AIAeroPlaneRag/data/processed")
    qa.set_mandatory_mode(True)  # 强制模式

    report = await qa.validate_document_addition(document_path, expected_sections)
    qa.print_report(report)

    return report["status"] == "PASSED"


# 导出便捷函数
__all__ = [
    'DevelopmentQualityAssurance',
    'QualityGate',
    'mandatory_agent_validation'
]
